"""Generate minimal class-definition stubs from class/file lookup results.

Input example:
[
  {'class_name': 'InferenceContext', 'file': 'core/framework/shape_inference.h', 'line': 232},
  {'class_name': 'Status', 'file': 'core/platform/status.h', 'line': 76},
  {'class_name': 'Tensor', 'file': 'core/framework/tensor.h', 'line': 108},
]
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping


DEFAULT_OUTPUT_ROOT = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/EXTRACTED")


def _build_empty_class_definition(class_name: str) -> str:
    return (
        f"class {class_name} {{\n"
        " public:\n"
        " private:\n"
        "};\n"
    )


def generate_class_stubs(
    class_locations: Iterable[Mapping[str, object]],
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> list[Path]:
    """Create replica files under EXTRACTED with only empty class definitions."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    generated_files = []

    for item in class_locations:
        class_name = str(item.get("class_name", "")).strip()
        relative_file = str(item.get("file", "")).strip()

        if not class_name or not relative_file:
            continue

        target_file = output_root / relative_file
        target_file.parent.mkdir(parents=True, exist_ok=True)

        target_file.write_text(_build_empty_class_definition(class_name), encoding="utf-8")
        generated_files.append(target_file)

    return generated_files