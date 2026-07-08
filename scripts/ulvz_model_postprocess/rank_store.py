from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from scripts.ulvz_model_postprocess import SCHEMA_VERSION
from scripts.ulvz_model_postprocess.schema import (
    COORDINATE_UNITS,
    FIELD_UNITS,
    MODEL_FIELD_SCALING,
    NORMALIZED_COORDINATE_UNITS,
    array_fingerprint,
    stable_fingerprint,
    write_json,
)


@dataclass
class RankArrays:
    rank: int
    region: int
    x_km: np.ndarray
    y_km: np.ndarray
    z_km: np.ndarray
    x_norm: np.ndarray
    y_norm: np.ndarray
    z_norm: np.ndarray
    ibool: np.ndarray
    idoubling: np.ndarray
    ispec_is_tiso: np.ndarray
    fields: dict[str, np.ndarray]


def rank_dir_name(rank: int, region: int) -> str:
    return f"rank{rank:06d}_reg{region}"


def write_model_product(
    root: str | Path,
    *,
    label: str,
    extraction_mode: str,
    ranks: list[RankArrays],
    roi: dict[str, Any] | None,
    sampling_rule: dict[str, Any] | None,
    selection_fingerprint: str,
    provenance: dict[str, Any] | None = None,
) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rank_entries: list[dict[str, Any]] = []
    field_names: set[str] = set()
    topology_fps: list[str] = []
    geometry_fps: list[str] = []

    for rank in ranks:
        entry = _write_rank(root, rank)
        rank_entries.append(entry)
        field_names.update(rank.fields)
        topology_fps.append(entry["topology_fingerprint"])
        geometry_fps.append(entry["geometry_fingerprint"])

    compatibility_payload = {
        "schema_version": SCHEMA_VERSION,
        "extraction_mode": extraction_mode,
        "roi": roi or {"kind": "none"},
        "sampling_rule": sampling_rule or {"kind": "none"},
        "selection_fingerprint": selection_fingerprint,
        "rank_inventory": [
            {"rank": item["rank"], "region": item["region"], "nspec": item["nspec"], "nglob": item["nglob"]}
            for item in rank_entries
        ],
        "field_units": {name: FIELD_UNITS[name] for name in sorted(field_names)},
        "coordinate_units": COORDINATE_UNITS,
        "model_field_scaling_convention": MODEL_FIELD_SCALING,
        "topology_fingerprint": stable_fingerprint({"ranks": topology_fps}),
        "geometry_fingerprint": stable_fingerprint({"ranks": geometry_fps}),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "model_label": label,
        "extraction_mode": extraction_mode,
        "roi": roi or {"kind": "none"},
        "sampling_rule": sampling_rule or {"kind": "none"},
        "selection_fingerprint": selection_fingerprint,
        "coordinate_units": COORDINATE_UNITS,
        "normalized_coordinate_units": NORMALIZED_COORDINATE_UNITS,
        "field_units": compatibility_payload["field_units"],
        "field_derivations": _field_derivations(sorted(field_names)),
        "model_field_scaling_convention": MODEL_FIELD_SCALING,
        "rank_store": {"layout": "rank-local-directory-npy-v1", "ranks": rank_entries},
        "compatibility_fingerprint": stable_fingerprint(compatibility_payload),
        "compatibility_fingerprint_contents": compatibility_payload,
        "provenance": provenance or {},
    }
    manifest_path = root / "model_manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path


def _write_rank(root: Path, rank: RankArrays) -> dict[str, Any]:
    rank_dir = root / "ranks" / rank_dir_name(rank.rank, rank.region)
    fields_dir = rank_dir / "fields"
    fields_dir.mkdir(parents=True, exist_ok=True)

    arrays = {
        "x_km": rank.x_km,
        "y_km": rank.y_km,
        "z_km": rank.z_km,
        "x_norm": rank.x_norm,
        "y_norm": rank.y_norm,
        "z_norm": rank.z_norm,
        "ibool": rank.ibool,
        "idoubling": rank.idoubling,
        "ispec_is_tiso": rank.ispec_is_tiso,
    }
    for name, array in arrays.items():
        np.save(rank_dir / f"{name}.npy", array)
    for name, array in rank.fields.items():
        if name not in FIELD_UNITS:
            raise ValueError(f"unsupported field name: {name}")
        np.save(fields_dir / f"{name}.npy", array)

    nglob = int(rank.x_km.size)
    nspec = int(rank.ibool.shape[-1])
    topology_fp = array_fingerprint(rank.ibool, rank.idoubling, rank.ispec_is_tiso)
    geometry_fp = array_fingerprint(rank.x_km, rank.y_km, rank.z_km, rank.ibool)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "rank": int(rank.rank),
        "region": int(rank.region),
        "nglob": nglob,
        "nspec": nspec,
        "gll_dimensions": list(rank.ibool.shape[:3]),
        "coordinate_units": COORDINATE_UNITS,
        "field_units": {name: FIELD_UNITS[name] for name in sorted(rank.fields)},
        "array_files": {name: f"{name}.npy" for name in arrays},
        "field_files": {name: f"fields/{name}.npy" for name in sorted(rank.fields)},
        "topology_fingerprint": topology_fp,
        "geometry_fingerprint": geometry_fp,
    }
    write_json(rank_dir / "metadata.json", metadata)
    return {
        "rank": int(rank.rank),
        "region": int(rank.region),
        "path": f"ranks/{rank_dir_name(rank.rank, rank.region)}",
        "nglob": nglob,
        "nspec": nspec,
        "gll_dimensions": list(rank.ibool.shape[:3]),
        "fields": sorted(rank.fields),
        "topology_fingerprint": topology_fp,
        "geometry_fingerprint": geometry_fp,
    }


def _field_derivations(fields: list[str]) -> dict[str, str]:
    derivations = {}
    for field in fields:
        if field == "rho":
            derivations[field] = "rho = rhostore * density_scale_to_kg_m-3"
        elif field == "vp":
            derivations[field] = "isotropic vp = sqrt((kappa + 4*mu/3) / rho) * velocity_scale_to_m_s-1"
        elif field == "vs":
            derivations[field] = "isotropic vs = sqrt(mu / rho) * velocity_scale_to_m_s-1"
        elif field == "vpv":
            derivations[field] = "TISO vpv = sqrt((kappav + 4*muv/3) / rho) * velocity_scale_to_m_s-1"
        elif field == "vph":
            derivations[field] = "TISO vph = sqrt((kappah + 4*muh/3) / rho) * velocity_scale_to_m_s-1"
        elif field == "vsv":
            derivations[field] = "TISO vsv = sqrt(muv / rho) * velocity_scale_to_m_s-1"
        elif field == "vsh":
            derivations[field] = "TISO vsh = sqrt(muh / rho) * velocity_scale_to_m_s-1"
        elif field == "eta":
            derivations[field] = "TISO eta copied from eta_anisostore"
    return derivations
