"""Lookup source definitions for type names in a global Joern CPG."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List


DEFAULT_GLOBAL_CPG = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/global.bin")


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

        item = {
            "type": name,
            "full_type": full_name,
            "file": file_name,
            "line": line_no,
        }

        if tag == "DEF":
            definitions.append(item)
        else:
            item["note"] = "present_only_as_external_in_global_cpg"
            external_only.append(item)

    return definitions if definitions else external_only


def find_definitions_for_types(
    type_names: List[str],
    global_cpg_path: str | Path = DEFAULT_GLOBAL_CPG,
) -> Dict[str, List[dict]]:
    """Find definition locations (file, line) for each type in global.bin."""
    global_cpg_path = Path(global_cpg_path)
    if not global_cpg_path.exists():
        raise FileNotFoundError(f"Global CPG file not found: {global_cpg_path}")

    joern_bin = shutil.which("joern")
    if not joern_bin:
        raise RuntimeError("`joern` is not installed or not available in PATH.")

    output: Dict[str, List[dict]] = {}
    for type_name in type_names:
        output[type_name] = _lookup_single_type_definition(type_name, global_cpg_path, joern_bin)

    return output