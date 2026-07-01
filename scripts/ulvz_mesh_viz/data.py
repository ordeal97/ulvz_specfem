from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ulvz_mesh_viz import SCHEMA_VERSION


class PlotDataError(RuntimeError):
    """Raised when exported plotting data are missing or inconsistent."""


def resolve_input_paths(
    data_dir: str | Path,
    metadata: str | Path | None = None,
    points: str | Path | None = None,
    comparison_summary: str | Path | None = None,
) -> dict[str, Path]:
    base = Path(data_dir)
    meta_path = Path(metadata) if metadata else base / "mesh_visualization_metadata.json"
    points_path = Path(points) if points else _first_existing(
        base / "mesh_gll_points.csv.gz", base / "mesh_gll_points.csv"
    )
    comparison_path = (
        Path(comparison_summary) if comparison_summary else base / "comparison_summary.csv"
    )
    return {"metadata": meta_path, "points": points_path, "comparison": comparison_path}


def _first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def load_metadata(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        raise PlotDataError(f"missing metadata file: {path}")
    with path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise PlotDataError(
            f"unsupported schema_version {metadata.get('schema_version')!r}; "
            f"expected {SCHEMA_VERSION}"
        )
    return metadata


def load_points(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise PlotDataError(f"missing point CSV file: {path}")
    return pd.read_csv(path)


def load_comparison(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise PlotDataError(f"missing comparison summary: {path}")
    return pd.read_csv(path)


def load_dataset(
    data_dir: str | Path,
    metadata: str | Path | None = None,
    points: str | Path | None = None,
    comparison_summary: str | Path | None = None,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, dict[str, Path]]:
    paths = resolve_input_paths(data_dir, metadata, points, comparison_summary)
    meta = load_metadata(paths["metadata"])
    point_df = load_points(paths["points"])
    comparison_df = load_comparison(paths["comparison"])
    return meta, point_df, comparison_df, paths


def write_json(path: str | Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def category_counts(points: pd.DataFrame) -> dict[str, int]:
    counts = points["category"].value_counts().to_dict()
    return {name: int(counts.get(name, 0)) for name in ["outside", "taper", "core"]}


def present_fields(metadata: dict) -> list[str]:
    fields = metadata.get("fields_present", {})
    return [field for field in ["rho", "vsv", "vsh", "vpv", "vph"] if bool(fields.get(field))]


def unique_points(points: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [col for col in ["rank", "ispec", "k", "j", "i"] if col in points.columns]
    ordered = points.sort_values(sort_cols) if sort_cols else points
    return ordered.drop_duplicates(["rank", "iglob"], keep="first").reset_index(drop=True)
