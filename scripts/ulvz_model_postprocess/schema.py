from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from scripts.ulvz_model_postprocess import SCHEMA_VERSION
from scripts.ulvz_model_postprocess.errors import ModelPostprocessError


COORDINATE_UNITS = {"x_km": "km", "y_km": "km", "z_km": "km"}
NORMALIZED_COORDINATE_UNITS = {"x_norm": "dimensionless", "y_norm": "dimensionless", "z_norm": "dimensionless"}
FIELD_UNITS = {
    "rho": "kg m^-3",
    "vp": "m s^-1",
    "vs": "m s^-1",
    "vpv": "m s^-1",
    "vph": "m s^-1",
    "vsv": "m s^-1",
    "vsh": "m s^-1",
    "eta": "dimensionless",
}
MODEL_FIELD_SCALING = (
    "stored physical SI model fields; velocities are m s^-1, density is kg m^-3; "
    "plotting may display velocities in km s^-1"
)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def read_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_dir():
        if _looks_like_databases_mpi(path):
            raise ModelPostprocessError(
                "raw DATABASES_MPI input is not supported here; provide an extracted "
                "rank-store manifest (model_manifest.json) produced by the extract command."
            )
        raise ModelPostprocessError(f"expected a JSON manifest file, got directory: {path}")
    if not path.exists():
        raise ModelPostprocessError(f"missing JSON file: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _looks_like_databases_mpi(path: Path) -> bool:
    return path.name == "DATABASES_MPI" or any(path.glob("proc*_reg*_solver_data.bin"))


def ensure_schema(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ModelPostprocessError(
            f"unsupported schema_version {payload.get('schema_version')!r}; expected {SCHEMA_VERSION}"
        )


def array_fingerprint(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("utf-8"))
        digest.update(str(contiguous.shape).encode("utf-8"))
        digest.update(contiguous.view(np.uint8))
    return digest.hexdigest()


def stable_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
