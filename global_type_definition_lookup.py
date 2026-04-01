"""Lookup source definitions for type names in a global Joern CPG."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional


DEFAULT_GLOBAL_CPG = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/global.bin")
DEFAULT_TF_ROOT = Path("/home/mushfiqur/Desktop/Github/tensorflow/tensorflow")

# Optional canonical targets for known classes to avoid picking unrelated namespaces.
PREFERRED_CLASS_FILES = {
    "InferenceContext": "core/framework/shape_inference.h",
    "Status": "core/platform/status.h",
    "Tensor": "core/framework/tensor.h",
}


def _run_joern_with_fallback(cmds: List[List[str]]) -> subprocess.CompletedProcess[str]:
    last_error: subprocess.CalledProcessError | None = None
    for cmd in cmds:
        try:
            return subprocess.run(cmd, check=True, text=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            last_error = exc

    assert last_error is not None
    raise RuntimeError(
        "Joern execution failed."
        f"\nCommand: {' '.join(last_error.cmd)}"
        f"\nExit code: {last_error.returncode}"
        f"\nSTDERR:\n{(last_error.stderr or '').strip() or '<empty>'}"
        f"\nSTDOUT:\n{(last_error.stdout or '').strip() or '<empty>'}"
    )


def _find_class_definition_line(type_name: str, relative_file: str, repo_root: Path = DEFAULT_TF_ROOT) -> Optional[int]:
    """Return the source line where `class <TypeName> {` starts, if found."""
    if not relative_file or relative_file.startswith("<"):
        return None

    file_path = repo_root / relative_file
    if not file_path.exists():
        return None

    class_start_pattern = re.compile(rf"^\s*class\s+{re.escape(type_name)}\b")

    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return None

    for idx, line in enumerate(lines, start=1):
        if not class_start_pattern.search(line):
            continue

        # Case 1: brace on same line -> class InferenceContext {
        if "{" in line and ";" not in line:
            return idx

        # Case 2: brace on following lines.
        for look_ahead in range(idx + 1, min(idx + 6, len(lines) + 1)):
            next_line = lines[look_ahead - 1].strip()
            if not next_line:
                continue
            if next_line.startswith("//"):
                continue
            if next_line.startswith(":"):
                continue
            if next_line.startswith("{"):
                return look_ahead
            if next_line.endswith(";"):
                break

    return None


def _lookup_single_type_definition(type_name: str, global_cpg_path: Path, joern_bin: str) -> List[dict]:
    joern_script = """
import io.shiftleft.semanticcpg.language.*

@main def run(cpgFile: String, typeName: String): Unit = {
  importCpg(cpgFile)

  def isMatch(td: io.shiftleft.codepropertygraph.generated.nodes.TypeDecl): Boolean = {
    val name = Option(td.name).getOrElse("")
    val fullName = Option(td.fullName).getOrElse("")
    name == typeName ||
    name.endsWith(s"::${typeName}") ||
    fullName.endsWith(s"::${typeName}") ||
    fullName.endsWith(s".${typeName}")
  }

  val matches = cpg.typeDecl.filter(td => isMatch(td)).l

  matches.foreach { td =>
    val tag = if (td.isExternal) "EXT" else "DEF"
    val fileName = Option(td.filename).getOrElse("")
    val lineNo = td.lineNumber.getOrElse(-1)
    val fullName = Option(td.fullName).getOrElse("")
    println(s"${tag}:${td.name}\t${fullName}\t${fileName}\t${lineNo}")
  }
}
""".strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "lookup_type_definition.sc"
        script_path.write_text(joern_script, encoding="utf-8")

        commands = [
            [
                joern_bin,
                "--script",
                str(script_path),
                "--params",
                f"cpgFile={global_cpg_path},typeName={type_name}",
            ],
            [
                joern_bin,
                "--script",
                str(script_path),
                "--param",
                f"cpgFile={global_cpg_path}",
                "--param",
                f"typeName={type_name}",
            ],
        ]
        result = _run_joern_with_fallback(commands)

    definitions = []
    external_only = []

    for line in result.stdout.splitlines():
        if not (line.startswith("DEF:") or line.startswith("EXT:")):
            continue
        tag = line[:3]
        payload = line[4:]
        parts = payload.split("\t")
        if len(parts) != 4:
            continue

        name, full_name, file_name, line_no_str = parts
        try:
            line_no = int(line_no_str)
        except ValueError:
            line_no = -1

        class_definition_line = _find_class_definition_line(type_name, file_name)
        is_precise_definition = class_definition_line is not None and line_no == class_definition_line

        item = {
            "type": name,
            "full_type": full_name,
            "file": file_name,
            "line": line_no,
            "class_definition_line": class_definition_line,
            "is_precise_class_definition": is_precise_definition,
        }

        if tag == "DEF":
            definitions.append(item)
        else:
            item["note"] = "present_only_as_external_in_global_cpg"
            external_only.append(item)

    if definitions:
        definitions.sort(
            key=lambda d: (
                not d["is_precise_class_definition"],
                0 if ".h" in d["file"] else 1,
                d["line"] if d["line"] >= 0 else 10**9,
            )
        )
        return definitions
    return external_only


def find_definitions_for_types(
    type_names: List[str],
    global_cpg_path: str | Path = DEFAULT_GLOBAL_CPG,
) -> List[dict]:
    """Return a concise list: class_name, file, line for each requested type."""
    global_cpg_path = Path(global_cpg_path)
    if not global_cpg_path.exists():
        raise FileNotFoundError(f"Global CPG file not found: {global_cpg_path}")

    joern_bin = shutil.which("joern")
    if not joern_bin:
        raise RuntimeError("`joern` is not installed or not available in PATH.")

    concise_results = []

    for type_name in type_names:
        matches = _lookup_single_type_definition(type_name, global_cpg_path, joern_bin)

        if not matches:
            concise_results.append({"class_name": type_name, "file": None, "line": None})
            continue

        preferred_file = PREFERRED_CLASS_FILES.get(type_name)

        def _rank(item: dict) -> tuple:
            file_name = item.get("file") or ""
            return (
                0 if preferred_file and file_name == preferred_file else 1,
                0 if item.get("is_precise_class_definition") else 1,
                0 if file_name.startswith("core/") else 1,
                1 if file_name.startswith("lite/") else 0,
                item.get("line") if isinstance(item.get("line"), int) and item.get("line") >= 0 else 10**9,
            )

        chosen = sorted(matches, key=_rank)[0]

        line = chosen.get("class_definition_line") or chosen.get("line")
        concise_results.append({"class_name": type_name, "file": chosen.get("file"), "line": line})

    return concise_results
