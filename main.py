from cpg_generator import generate_cpg
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
import os


class JoernQueryError(RuntimeError):
    pass


def run_joern_missing_deps(cpg_bin: str, out_json: str, joern_cmd: str = "joern"):
    cpg_bin = str(Path(cpg_bin).expanduser().resolve())
    out_json = str(Path(out_json).expanduser().resolve())

    env = dict(os.environ)
    env["OUT_JSON"] = out_json
    env["EXTRACTED_ROOT"] = str(Path("/home/mushfiqur/Desktop/Github/EXTRACTED").resolve())

    cmd = [
        joern_cmd,
        "--cpg", cpg_bin,
        "--script", "find_missing.sc",
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    
    print("=== JOERN STDOUT ===")
    print(proc.stdout)
    print("=== JOERN STDERR ===")
    print(proc.stderr)
    if proc.returncode != 0:
        raise JoernQueryError(
            f"Joern query failed.\nCommand: {' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n"
        )

    if not Path(out_json).exists():
        raise JoernQueryError(f"Expected output JSON not found: {out_json}")

    with open(out_json, "r", encoding="utf-8") as f:
        return json.load(f)


def summarize_missing(items: List[Dict[str, Any]]) -> Tuple[int, int]:
    calls = sum(1 for x in items if x.get("kind") == "call")
    types = sum(1 for x in items if x.get("kind") == "type")
    return calls, types

if __name__ == "__main__":
    cpg = generate_cpg("/home/mushfiqur/Desktop/Github/ExtraKLEE/EXTRACTED")
    print("Generated CPG:", cpg)
    missing = run_joern_missing_deps(
        cpg_bin="./joern-out/cpg.bin",
        out_json="./joern-out/missing.json",
        joern_cmd="joern"
    )

    calls, types = summarize_missing(missing)
    print(f"Missing frontier: {calls} unresolved calls, {types} unresolved types")
    print("First 20 items:")
    for x in missing[:20]:
        print(f"- [{x['kind']}] {x.get('name')} @ {x.get('file')}:{x.get('line')}  code={x.get('code')}")
