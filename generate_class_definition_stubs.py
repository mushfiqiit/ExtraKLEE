"""Generate minimal class-definition stubs from class/file lookup results."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Iterable


DEFAULT_OUTPUT_ROOT = Path("/home/mushfiqur/Desktop/Github/ExtraKLEE/EXTRACTED")


def _build_empty_class_definition(class_name: str) -> str:
    return (
        f"class {class_name} {{\n"
        " public:\n"
        " private:\n"
        "};\n"
    )


def _normalize_class_locations(class_locations: Iterable[object] | Mapping[str, object]) -> list[dict]:
    """Support both old dict output and new list-of-dicts output."""
    normalized: list[dict] = []

    # Backward compatibility: old lookup format was {class_name: [candidate_dicts...]}
    if isinstance(class_locations, Mapping):
        for class_name, candidates in class_locations.items():
            file_name = None
            line = None
            if isinstance(candidates, list) and candidates and isinstance(candidates[0], Mapping):
                file_name = candidates[0].get("file")
                line = candidates[0].get("line")
            normalized.append({"class_name": str(class_name), "file": file_name, "line": line})
        return normalized

    for item in class_locations:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
            continue

        # Guard against accidental string-only items to avoid runtime crash.
        if isinstance(item, str):
            normalized.append({"class_name": item, "file": None, "line": None})

    return normalized


def generate_class_stubs(
    class_locations: Iterable[object] | Mapping[str, object],
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> list[Path]:
    """Create replica files under EXTRACTED with only empty class definitions."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    generated_files = []

    for item in _normalize_class_locations(class_locations):
        class_name = str(item.get("class_name", "")).strip()
        relative_file = str(item.get("file", "")).strip()

        if not class_name or not relative_file or relative_file in {"None", ""}:
            continue

        target_file = output_root / relative_file
        target_file.parent.mkdir(parents=True, exist_ok=True)

        target_file.write_text(_build_empty_class_definition(class_name), encoding="utf-8")
        generated_files.append(target_file)

    return generated_files
