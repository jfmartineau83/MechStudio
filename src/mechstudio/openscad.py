from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OpenScadNotFoundError(FileNotFoundError):
    pass


def discover_openscad(configured: str | None = None) -> Path | None:
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    if os.environ.get("OPENSCAD_EXECUTABLE"):
        candidates.append(Path(os.environ["OPENSCAD_EXECUTABLE"]))
    found = shutil.which("openscad") or shutil.which("openscad.exe")
    if found:
        candidates.append(Path(found))
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "OpenSCAD" / "openscad.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def scad_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(scad_literal(item) for item in value) + "]"
    if isinstance(value, (int, float)):
        return format(value, ".15g")
    raise TypeError(f"Cannot pass {type(value).__name__} to OpenSCAD")


@dataclass(slots=True)
class OpenScadCommand:
    executable: Path
    arguments: list[str]
    output_path: Path


def build_generation_command(
    executable: Path | None,
    source: Path,
    output: Path,
    parameters: dict[str, Any],
) -> OpenScadCommand:
    if executable is None:
        raise OpenScadNotFoundError(
            "OpenSCAD was not found. Install it or select openscad.exe in Edit → Preferences."
        )
    if not source.is_file():
        raise FileNotFoundError(f"Module source is missing: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    arguments = ["-o", str(output)]
    for name, value in sorted(parameters.items()):
        arguments.extend(["-D", f"{name}={scad_literal(value)}"])
    arguments.append(str(source))
    return OpenScadCommand(executable, arguments, output)

