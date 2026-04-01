"""Analyze method information from the local CPG."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List


DEFAULT_LOCAL_CPG = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/local.bin")


def _run_joern_with_fallback(script_path: Path, cpg_path: Path, joern_bin: str) -> subprocess.CompletedProcess[str]:
    commands = [
        [joern_bin, "--script", str(script_path), "--params", f"cpgFile={cpg_path}"],
        [joern_bin, "--script", str(script_path), "--param", f"cpgFile={cpg_path}"],
    ]

    last_error: subprocess.CalledProcessError | None = None
    for cmd in commands:
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


def find_missing_methods_with_usage(local_cpg_path: str | Path = DEFAULT_LOCAL_CPG) -> List[dict]:
    """Return unresolved method usages in local CPG.

    Filters out obvious noise such as:
      - <global>
      - main
      - SetShapeFn (explicitly requested)
    """
    local_cpg_path = Path(local_cpg_path)
    if not local_cpg_path.exists():
        raise FileNotFoundError(f"CPG file not found: {local_cpg_path}")

    joern_bin = shutil.which("joern")
    if not joern_bin:
        raise RuntimeError("`joern` is not installed or not available in PATH.")

    joern_script = """
import io.shiftleft.semanticcpg.language.*
import io.shiftleft.semanticcpg.language.locationCreator

@main def run(cpgFile: String): Unit = {
  importCpg(cpgFile)

  val ignoredNames = Set("<global>", "main", "SetShapeFn")

  val missingCalls = cpg.call
    .filter { c =>
      val callName = Option(c.name).getOrElse("")
      val methodFullName = Option(c.methodFullName).getOrElse("")
      val hasConcreteDefByFullName =
        methodFullName.nonEmpty && cpg.method.fullNameExact(methodFullName).filter(m => !m.isExternal).nonEmpty
      val hasConcreteDefByName =
        callName.nonEmpty && cpg.method.nameExact(callName).filter(m => !m.isExternal).nonEmpty

      val unresolvedByFullName = methodFullName.isEmpty || !hasConcreteDefByFullName
      val unresolvedByName = callName.nonEmpty && !hasConcreteDefByName

      !ignoredNames.contains(callName) &&
      callName.nonEmpty &&
      (unresolvedByFullName || unresolvedByName)
    }
    .map { c =>
      val methodName = Option(c.name).getOrElse("")
      val fileName = c.location.filename
      val lineNo = c.location.lineNumber.getOrElse(-1)
      val code = Option(c.code).getOrElse("")
      val methodFullName = Option(c.methodFullName).getOrElse("")
      (methodName, methodFullName, fileName, lineNo, code)
    }
    .l
    .distinct
    .sortBy(x => (x._3, x._4, x._1))

  missingCalls.foreach { case (name, fullName, fileName, lineNo, code) =>
    println(s"MM:${name}\t${fullName}\t${fileName}\t${lineNo}\t${code}")
  }
}
""".strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "list_missing_methods.sc"
        script_path.write_text(joern_script, encoding="utf-8")
        result = _run_joern_with_fallback(script_path, local_cpg_path, joern_bin)

    missing_methods = []
    for line in result.stdout.splitlines():
        if not line.startswith("MM:"):
            continue

        payload = line[3:]
        parts = payload.split("\t", maxsplit=4)
        if len(parts) != 5:
            continue

        method_name, full_name, file_name, line_no_str, code = parts
        try:
            line_no = int(line_no_str)
        except ValueError:
            line_no = -1

        class_name = ""
        if "." in full_name:
            class_name = full_name.rsplit(".", 1)[0]
        elif "::" in full_name:
            class_name = full_name.rsplit("::", 1)[0]

        missing_methods.append(
            {
                "method_name": method_name,
                "class_name": class_name,
                "file": file_name,
                "usage_line": line_no,
                "usage_code": code,
            }
        )

    return missing_methods


def list_methods_with_details(local_cpg_path: str | Path = DEFAULT_LOCAL_CPG) -> List[dict]:
    """Return methods in a concise, human-readable format.

    Output schema per entry:
      - method_name
      - class_name (empty if not a class member)
      - definition_line
      - signature_line
      - file
    """
    local_cpg_path = Path(local_cpg_path)
    if not local_cpg_path.exists():
        raise FileNotFoundError(f"CPG file not found: {local_cpg_path}")

    joern_bin = shutil.which("joern")
    if not joern_bin:
        raise RuntimeError("`joern` is not installed or not available in PATH.")

    joern_script = """
import io.shiftleft.semanticcpg.language.*

@main def run(cpgFile: String): Unit = {
  importCpg(cpgFile)

  val methods = cpg.method
    .filter(m => !m.isExternal)
    .map { m =>
      val name = Option(m.name).getOrElse("")
      val fullName = Option(m.fullName).getOrElse("")
      val fileName = Option(m.filename).getOrElse("")
      val defLine = m.lineNumber.getOrElse(-1)
      val sigLine = m.lineNumber.getOrElse(-1)
      (name, fullName, fileName, defLine, sigLine)
    }
    .l
    .distinct
    .sortBy(x => (x._3, x._4, x._1))

  methods.foreach { case (name, fullName, fileName, defLine, sigLine) =>
    println(s"MD:${name}\t${fullName}\t${fileName}\t${defLine}\t${sigLine}")
  }
}
""".strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "list_methods_with_details.sc"
        script_path.write_text(joern_script, encoding="utf-8")
        result = _run_joern_with_fallback(script_path, local_cpg_path, joern_bin)

    method_rows: List[dict] = []
    for line in result.stdout.splitlines():
        if not line.startswith("MD:"):
            continue
        payload = line[3:]
        parts = payload.split("\t", maxsplit=4)
        if len(parts) != 5:
            continue

        method_name, full_name, file_name, def_line_str, sig_line_str = parts
        try:
            definition_line = int(def_line_str)
        except ValueError:
            definition_line = -1
        try:
            signature_line = int(sig_line_str)
        except ValueError:
            signature_line = -1

        class_name = ""
        if "." in full_name:
            class_name = full_name.rsplit(".", 1)[0]
        elif "::" in full_name:
            class_name = full_name.rsplit("::", 1)[0]

        method_rows.append(
            {
                "method_name": method_name,
                "class_name": class_name,
                "definition_line": definition_line,
                "signature_line": signature_line,
                "file": file_name,
            }
        )

    return method_rows
