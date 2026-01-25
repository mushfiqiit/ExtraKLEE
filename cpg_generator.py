import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class JoernError(RuntimeError):
    pass


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def generate_cpg(extracted_dir: str,
                 out_dir: Optional[str] = None,
                 cpg_name: str = "cpg.bin",
                 joern_parse_cmd: str = "joern-parse",
                 overwrite: bool = True) -> str:
    """
    Generate a Joern CPG for the code under `extracted_dir`.

    Typical output is a single file: <out_dir>/<cpg_name> (default: ./joern-out/cpg.bin)

    Requirements:
      - Joern installed and `joern-parse` available on PATH, or pass an absolute path via joern_parse_cmd.
      - The directory contains parsable source code (C/C++ supported by Joern's frontend).

    Returns:
      Absolute path to the generated CPG file.
    """
    src = Path(extracted_dir).expanduser().resolve()
    if not src.exists() or not src.is_dir():
        raise ValueError(f"Not a directory: {src}")

    if _which(joern_parse_cmd) is None and not Path(joern_parse_cmd).exists():
        raise JoernError(
            f"Cannot find '{joern_parse_cmd}'. Put Joern on PATH or pass absolute path.\n"
            f"Example: joern_parse_cmd='/path/to/joern-parse'"
        )

    # Default output directory
    if out_dir is None:
        out = (Path.cwd() / "joern-out").resolve()
    else:
        out = Path(out_dir).expanduser().resolve()

    out.mkdir(parents=True, exist_ok=True)
    cpg_path = out / cpg_name

    if cpg_path.exists():
        if overwrite:
            cpg_path.unlink()
        else:
            raise FileExistsError(f"CPG already exists: {cpg_path}")

    # Build command.
    # joern-parse <src> --output <cpg.bin>
    cmd = [
        joern_parse_cmd,
        str(src),
        "--output",
        str(cpg_path),
    ]

    # Run Joern
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(out),  # keep logs/artifacts local
    )

    if proc.returncode != 0 or not cpg_path.exists():
        raise JoernError(
            "joern-parse failed.\n"
            f"Command: {' '.join(cmd)}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )

    return str(cpg_path)