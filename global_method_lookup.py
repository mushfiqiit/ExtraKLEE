"""Resolve method -> class using the global Joern CPG and TF source fallback."""
 
from __future__ import annotations
 
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
 
DEFAULT_GLOBAL_CPG = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/global.bin")
DEFAULT_TF_ROOT = Path("/home/mushfiqur/Desktop/Github/tensorflow/tensorflow")
 
# Authoritative overrides: method_name -> class_name.
# Empty string means it is a free function (no enclosing class).
# These are checked FIRST and win over whatever the CPG or grep returns.
PREFERRED_CLASS_FOR_METHOD: Dict[str, str] = {
    "input_tensor":        "InferenceContext",
    "input":               "InferenceContext",
    "set_output":          "InferenceContext",
    "MakeShape":           "InferenceContext",
    "MakeDim":             "InferenceContext",
    "WithContext":         "InferenceContext",
    "NumElements":         "Tensor",
    "flat":                "Tensor",
    "shape":               "Tensor",
    "OkStatus":            "Status",
    "UnknownShape":        "",   # free function in shape_inference namespace
    "ValidateSparseTensor": "",  # free function in shape_inference namespace
    "InvalidArgument":     "",   # free function in errors namespace
}
 
 
def _run_joern_with_fallback(
    script_path: Path, cpg_path: Path, joern_bin: str
) -> subprocess.CompletedProcess[str]:
    commands = [
        [joern_bin, "--script", str(script_path), "--params", f"cpgFile={cpg_path}"],
        [joern_bin, "--script", str(script_path), "--param",  f"cpgFile={cpg_path}"],
    ]
    last_error: Optional[subprocess.CalledProcessError] = None
    for cmd in commands:
        try:
            return subprocess.run(cmd, check=True, text=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            last_error = exc
    assert last_error is not None
    raise RuntimeError(
        "Joern execution failed."
        f"\nSTDERR:\n{(last_error.stderr or '').strip() or '<empty>'}"
        f"\nSTDOUT:\n{(last_error.stdout or '').strip() or '<empty>'}"
    )
 
 
def _query_global_cpg(
    method_names: List[str], global_cpg_path: Path, joern_bin: str
) -> Dict[str, List[Tuple[str, str]]]:
    """Return {method_name: [(class_name, file_name), ...]} from the global CPG."""
    names_literal = "Set(" + ", ".join(f'"{n}"' for n in method_names) + ")"
 
    joern_script = f"""
import io.shiftleft.semanticcpg.language.*
 
@main def run(cpgFile: String): Unit = {{
  importCpg(cpgFile)
 
  val targetNames = {names_literal}
 
  // Class members: TypeDecl -> method
  cpg.typeDecl
    .filter(td => !td.isExternal && Option(td.name).getOrElse("").nonEmpty && !td.name.startsWith("<"))
    .foreach {{ td =>
      td.method
        .filter(m => targetNames.contains(Option(m.name).getOrElse("")))
        .foreach {{ m =>
          val methodName = Option(m.name).getOrElse("")
          val className  = Option(td.name).getOrElse("")
          val fileName   = Option(td.filename).getOrElse(Option(m.filename).getOrElse(""))
          println(s"MC:${{methodName}}\\t${{className}}\\t${{fileName}}")
        }}
    }}
 
  // Free functions: methods with no defining TypeDecl
  cpg.method
    .filter(m => targetNames.contains(Option(m.name).getOrElse("")))
    .filter(m => !m.isExternal)
    .filter(m => m.definingTypeDecl.isEmpty)
    .foreach {{ m =>
      val methodName = Option(m.name).getOrElse("")
      val fileName   = Option(m.filename).getOrElse("")
      println(s"MC:${{methodName}}\\t\\t${{fileName}}")
    }}
}}
""".strip()
 
    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = Path(tmp_dir) / "resolve_method_classes.sc"
        script_path.write_text(joern_script, encoding="utf-8")
        result = _run_joern_with_fallback(script_path, global_cpg_path, joern_bin)
 
    candidates: Dict[str, List[Tuple[str, str]]] = {n: [] for n in method_names}
    for line in result.stdout.splitlines():
        if not line.startswith("MC:"):
            continue
        parts = line[3:].split("\t", maxsplit=2)
        if len(parts) != 3:
            continue
        method_name, class_name, file_name = parts
        if method_name in candidates:
            candidates[method_name].append((class_name, file_name))
 
    return candidates
 
 
def _class_owning_method(method_name: str, file_path: Path) -> str:
    """Parse a C++ header and return the class that declares method_name.
 
    Tracks brace depth so nested classes are handled correctly.
    Returns "" if the method is a free function or not found.
    """
    method_re = re.compile(rf"\b{re.escape(method_name)}\s*[(<]")
    class_re   = re.compile(r"^\s*(?:class|struct)\s+(\w+)\b")
    comment_re = re.compile(r"//.*$")
 
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
 
    # Stack of (class_name, brace_depth_at_open)
    class_stack: List[Tuple[str, int]] = []
    depth = 0
 
    for raw_line in text.splitlines():
        line = comment_re.sub("", raw_line)
 
        # Check for a class/struct opening on this line
        cm = class_re.match(line)
        if cm and "{" in line:
            class_stack.append((cm.group(1), depth))
 
        opens  = line.count("{")
        closes = line.count("}")
        depth += opens - closes
 
        # Pop classes whose scope just closed
        while class_stack and depth <= class_stack[-1][1]:
            class_stack.pop()
 
        if method_re.search(line):
            return class_stack[-1][0] if class_stack else ""
 
    return ""
 
 
def _grep_tf_source(method_name: str, tf_root: Path) -> str:
    """Search TF core/ headers for the class that owns method_name."""
    try:
        result = subprocess.run(
            ["grep", "-r", "--include=*.h", "-l", method_name, str(tf_root / "core")],
            text=True, capture_output=True, timeout=30,
        )
        header_files = result.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, OSError):
        return ""
 
    # Try core/ headers first, then everything else
    def _priority(p: str) -> int:
        rel = p[len(str(tf_root)):].lstrip("/")
        return 0 if rel.startswith("core/") else 1
 
    for header in sorted(header_files, key=_priority):
        cls = _class_owning_method(method_name, Path(header))
        if cls:
            return cls
 
    return ""
 
 
def _pick_best_class(
    method_name: str, hits: List[Tuple[str, str]], tf_root: Path
) -> str:
    """Return the class that best matches method_name.
 
    Priority:
      1. PREFERRED_CLASS_FOR_METHOD table (authoritative for known methods)
      2. Global CPG hits ranked by core/ headers
      3. TF source grep fallback
    """
    # 1. Authoritative table
    if method_name in PREFERRED_CLASS_FOR_METHOD:
        return PREFERRED_CLASS_FOR_METHOD[method_name]
 
    # 2. CPG hits
    if hits:
        def _rank(hit: Tuple[str, str]) -> tuple:
            cls, fname = hit
            return (
                0 if fname.startswith("core/") else 1,
                0 if fname.endswith(".h") else 1,
                fname,
                cls,
            )
        best_class, best_file = sorted(hits, key=_rank)[0]
        # Accept CPG result if it comes from a core/ header
        if best_file.startswith("core/"):
            return best_class
 
    # 3. Grep TF source
    return _grep_tf_source(method_name, tf_root)
 
 
def resolve_method_classes(
    method_names: List[str],
    global_cpg_path: str | Path = DEFAULT_GLOBAL_CPG,
    tf_root: str | Path = DEFAULT_TF_ROOT,
) -> Dict[str, str]:
    """Return {method_name: class_name} for each name in method_names.
 
    Uses the global Joern CPG as primary source with TF source grep as fallback.
    An empty-string class means the method is a free function.
    """
    global_cpg_path = Path(global_cpg_path)
    tf_root = Path(tf_root)
 
    if not global_cpg_path.exists():
        raise FileNotFoundError(f"Global CPG not found: {global_cpg_path}")
 
    joern_bin = shutil.which("joern")
    if not joern_bin:
        raise RuntimeError("`joern` not found in PATH.")
 
    if not method_names:
        return {}
 
    # Methods already covered by the authoritative table don't need CPG queries.
    needs_lookup = [n for n in method_names if n not in PREFERRED_CLASS_FOR_METHOD]
    known = {n: PREFERRED_CLASS_FOR_METHOD[n] for n in method_names if n in PREFERRED_CLASS_FOR_METHOD}
 
    if needs_lookup:
        candidates = _query_global_cpg(needs_lookup, global_cpg_path, joern_bin)
        resolved = {
            name: _pick_best_class(name, hits, tf_root)
            for name, hits in candidates.items()
        }
    else:
        resolved = {}
 
    return {**known, **resolved}