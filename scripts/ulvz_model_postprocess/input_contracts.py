from __future__ import annotations

import re
from pathlib import Path

from scripts.ulvz_model_postprocess.errors import ModelPostprocessError


MODEL_RE = re.compile(r"^proc(?P<rank>\d{6})_reg(?P<region>\d)_solver_data\.bin$")


def parse_labeled_path(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ModelPostprocessError("model argument must use LABEL=PATH")
    label, path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ModelPostprocessError("model label must not be empty")
    return label, Path(path)


def validate_databases_mpi(path: Path) -> list[dict[str, int]]:
    if not path.exists():
        raise ModelPostprocessError(f"model path does not exist: {path}")
    if not path.is_dir():
        raise ModelPostprocessError(
            "v1 input must be a complete DATABASES_MPI directory, not a bare model file"
        )
    inventory = []
    for file_path in sorted(path.glob("proc*_reg*_solver_data.bin")):
        match = MODEL_RE.match(file_path.name)
        if match:
            inventory.append(
                {
                    "rank": int(match.group("rank")),
                    "region": int(match.group("region")),
                    "path": str(file_path),
                }
            )
    if not inventory:
        raise ModelPostprocessError(
            f"no proc*_reg*_solver_data.bin files found in DATABASES_MPI directory: {path}"
        )
    return inventory
