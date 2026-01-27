import os
import subprocess
from pathlib import Path


class JoernQueryError(RuntimeError):
    pass


def run_joern_debug_script(
    script_path: str,
    cpg_path: str,
    extracted_root: str,
    joern_cmd: str = "joern",
) -> str:
    script_path = str(Path(script_path).resolve())
    cpg_path = str(Path(cpg_path).resolve())
    extracted_root = str(Path(extracted_root).resolve())

    env = dict(os.environ)
    env["CPG_PATH"] = cpg_path
    env["EXTRACTED_ROOT"] = extracted_root

    cmd = [joern_cmd, "--script", script_path]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    if proc.returncode != 0:
        raise JoernQueryError(
            f"Joern debug script failed.\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )

    # Return stdout; you can also save it to a file if you want.
    return proc.stdout


if __name__ == "__main__":
    # Example usage (assuming you already generated cpg.bin)
    out = run_joern_debug_script(
        script_path="debug.sc",
        cpg_path="./joern-out/cpg.bin",
        extracted_root="/home/mushfiqur/Desktop/Github/EXTRACTED",
        joern_cmd="joern",
    )
    print(out)
