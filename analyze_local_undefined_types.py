"""Helper methods for extracting undefined types from a Joern local CPG."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List


DEFAULT_LOCAL_CPG = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/local.bin")

# C/C++ primitive/builtin-like names that are commonly marked external in Joern CPGs.
BUILTIN_TYPE_NAMES = {
    "void",
    "bool",
    "char",
    "signed char",
    "unsigned char",
    "short",
    "short int",
    "unsigned short",
    "unsigned short int",
    "int",
    "unsigned",
    "unsigned int",
    "long",
    "long int",
    "unsigned long",
    "unsigned long int",
    "long long",
    "long long int",
    "unsigned long long",
    "unsigned long long int",
    "float",
    "double",
    "long double",
    "size_t",
    "ssize_t",
    "wchar_t",
}


def _run_joern_with_fallback(script_path: Path, cpg_path: Path, joern_bin: str) -> subprocess.CompletedProcess[str]:
    """Run Joern script, trying both --params and --param forms."""
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
    stderr = (last_error.stderr or "").strip()
    stdout = (last_error.stdout or "").strip()
    raise RuntimeError(
        "Joern execution failed."
        f"\nCommand: {' '.join(last_error.cmd)}"
        f"\nExit code: {last_error.returncode}"
        f"\nSTDERR:\n{stderr or '<empty>'}"
        f"\nSTDOUT:\n{stdout or '<empty>'}"
    )


def _normalize_type_name(type_name: str) -> str:
    """Normalize a C/C++ type name for easier filtering/deduplication."""
    normalized = type_name.strip()
    normalized = re.sub(r"\b(const|volatile)\b", "", normalized)
    normalized = normalized.replace("*", " ").replace("&", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _remove_builtin_types(type_names: Iterable[str]) -> List[str]:
    """Remove builtin/primitive C/C++ types from undefined type output."""
    filtered = []
    seen = set()

    for original in type_names:
        normalized = _normalize_type_name(original)
        if not normalized:
            continue
        if normalized in BUILTIN_TYPE_NAMES:
            continue

        if normalized not in seen:
            seen.add(normalized)
            filtered.append(normalized)

    return sorted(filtered)


def find_undefined_types(local_cpg_path: str | Path = DEFAULT_LOCAL_CPG) -> List[str]:
    """Analyze local.bin and return undefined/external non-builtin type names."""
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
  val undefinedTypes = cpg.typeDecl
    .filter(td => td.isExternal)
    .name
    .filterNot(n => n == "<global>" || n == "ANY")
    .l
    .distinct
    .sorted

  undefinedTypes.foreach(t => println(s"UT:$t"))
}
""".strip()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "list_undefined_types.sc"
        script_path.write_text(joern_script, encoding="utf-8")
        result = _run_joern_with_fallback(script_path, local_cpg_path, joern_bin)

    raw_undefined_types = []
    for line in result.stdout.splitlines():
        if line.startswith("UT:"):
            raw_undefined_types.append(line[3:].strip())

    return _remove_builtin_types(raw_undefined_types)