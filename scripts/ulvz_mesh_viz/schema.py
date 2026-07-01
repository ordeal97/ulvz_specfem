from __future__ import annotations

import numpy as np
import pandas as pd

from ulvz_mesh_viz.data import PlotDataError, category_counts, present_fields


IDENTITY_COLUMNS = {
    "record_id",
    "record_kind",
    "rank",
    "ispec",
    "i",
    "j",
    "k",
    "iglob",
    "is_shared_duplicate",
}
COORDINATE_COLUMNS = {
    "x_norm",
    "y_norm",
    "z_norm",
    "radius_norm",
    "radius_km",
    "depth_km",
    "height_above_cmb_km",
    "latitude_deg",
    "longitude_deg",
}
SECTION_COLUMNS = {
    "point_azimuth_deg",
    "angular_distance_deg",
    "lateral_distance_km",
    "section_azimuth_deg",
    "section_distance_km",
    "cross_section_offset_km",
}
ORACLE_COLUMNS = {"w_expected", "category"}
FLAG_COLUMNS = {"cmb_boundary_noncomparable", "material_changed", "is_tiso"}
BASE_REQUIRED_COLUMNS = IDENTITY_COLUMNS | COORDINATE_COLUMNS | SECTION_COLUMNS | ORACLE_COLUMNS | FLAG_COLUMNS
COMPARISON_COLUMNS = {"record", "field", "category", "value"}


def validate_dataset(metadata: dict, points: pd.DataFrame, comparison: pd.DataFrame) -> dict:
    _require_metadata(metadata)
    _require_columns(points, BASE_REQUIRED_COLUMNS, "points")
    _require_columns(comparison, COMPARISON_COLUMNS, "comparison summary")
    fields = present_fields(metadata)
    if not fields:
        raise PlotDataError("no present material fields recorded in metadata")
    for field in fields:
        _require_columns(
            points,
            {f"{field}_expected", f"{field}_ratio", f"{field}_residual"},
            f"points field {field}",
        )
    counts = category_counts(points)
    missing = [category for category, count in counts.items() if count == 0]
    if missing:
        raise PlotDataError(f"missing required categories: {', '.join(missing)}")
    _validate_comparison(comparison, fields)
    validate_duplicate_consistency(metadata, points, fields)
    return {"status": "PASS", "category_counts": counts, "material_fields": fields}


def _require_metadata(metadata: dict) -> None:
    required = {
        "schema_version",
        "producer",
        "created_utc",
        "specfem_version",
        "git_commit",
        "mpi_command",
        "nproc",
        "omp_num_threads",
        "r_planet_km",
        "rcmb_km",
        "coordinate_convention",
        "ulvz",
        "fields_present",
        "sampling_rule",
        "duplicate_policy",
        "fixture_disclaimer",
        "tolerances",
    }
    missing = sorted(required - set(metadata))
    if missing:
        raise PlotDataError(f"metadata missing required keys: {', '.join(missing)}")


def _require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise PlotDataError(f"{label} missing required columns: {', '.join(missing)}")


def _validate_comparison(comparison: pd.DataFrame, fields: list[str]) -> None:
    records = set(zip(comparison["record"], comparison["field"], comparison["category"]))
    if ("tolerance", "ratio", "all") not in records:
        raise PlotDataError("comparison summary missing tolerance ratio record")
    for field in fields:
        if ("max_residual", field, "all") not in records:
            raise PlotDataError(f"comparison summary missing max_residual for {field}")


def validate_duplicate_consistency(metadata: dict, points: pd.DataFrame, fields: list[str]) -> None:
    tolerances = metadata.get("tolerances", {})
    coord_tol = float(tolerances.get("coordinate_abs", 1.0e-9))
    w_tol = float(tolerances.get("w_expected_abs", 1.0e-9))
    ratio_tol = float(tolerances.get("ratio_abs", 5.0e-5))
    residual_tol = float(tolerances.get("residual_abs", 5.0e-5))
    check_cols = [
        ("x_norm", coord_tol),
        ("y_norm", coord_tol),
        ("z_norm", coord_tol),
        ("radius_norm", coord_tol),
        ("radius_km", coord_tol),
        ("height_above_cmb_km", coord_tol),
        ("latitude_deg", coord_tol),
        ("longitude_deg", coord_tol),
        ("w_expected", w_tol),
    ]
    for field in fields:
        check_cols.extend(
            [
                (f"{field}_ratio", ratio_tol),
                (f"{field}_residual", residual_tol),
                (f"{field}_expected", ratio_tol),
            ]
        )
    grouped = points.groupby(["rank", "iglob"], sort=False)
    for key, group in grouped:
        if len(group) == 1:
            continue
        if group["category"].nunique(dropna=False) != 1:
            raise PlotDataError(f"duplicate (rank, iglob) {key} category mismatch")
        for column, tol in check_cols:
            if column not in group:
                continue
            values = group[column].astype(float).to_numpy()
            if np.nanmax(values) - np.nanmin(values) > tol:
                raise PlotDataError(f"duplicate (rank, iglob) {key} {column} mismatch")
