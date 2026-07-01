#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulvz_mesh_viz.data import PlotDataError, load_metadata, load_points, present_fields, write_json
from ulvz_mesh_viz.plotting import add_common_args
from ulvz_mesh_viz.schema import validate_duplicate_consistency


POINT_ARRAYS = [
    "w_expected",
    "category_code",
    "material_changed",
    "cmb_boundary_noncomparable",
    "rho_ratio",
    "vsv_ratio",
    "vsh_ratio",
    "vpv_ratio",
    "vph_ratio",
    "rho_residual",
    "vsv_residual",
    "vsh_residual",
    "vpv_residual",
    "vph_residual",
    "height_above_cmb_km",
    "lateral_distance_km",
    "section_distance_km",
    "cross_section_offset_km",
    "rank",
    "ispec",
    "iglob",
    "x_norm",
    "y_norm",
    "z_norm",
]
CATEGORY_CODES = {"outside": 0, "taper": 1, "core": 2}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Task 3F ULVZ GLL points to ParaView VTP.")
    add_common_args(parser)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--records",
        action="store_true",
        help="Preserve duplicate element-GLL records. This is the default.",
    )
    mode.add_argument(
        "--unique-points",
        action="store_true",
        help="Deduplicate by (rank, iglob) after duplicate consistency checks.",
    )
    return parser


def _import_vtk():
    try:
        from vtkmodules.vtkCommonCore import vtkDoubleArray, vtkIntArray, vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
        from vtkmodules.vtkIOXML import vtkXMLPolyDataWriter
        from vtkmodules.vtkCommonCore import vtkIdList
    except Exception as exc:  # pragma: no cover - exercised when optional VTK is absent
        raise PlotDataError(
            "VTK is required for export_paraview_points.py. "
            "Activate an environment with vtk or pyvista installed."
        ) from exc
    return vtkDoubleArray, vtkIntArray, vtkPoints, vtkCellArray, vtkPolyData, vtkXMLPolyDataWriter, vtkIdList


def _load(args: argparse.Namespace) -> tuple[dict, object, dict[str, Path]]:
    base = Path(args.data_dir)
    metadata_path = Path(args.metadata) if args.metadata else base / "mesh_visualization_metadata.json"
    points_path = Path(args.points) if args.points else _first_existing(
        base / "mesh_gll_points.csv.gz", base / "mesh_gll_points.csv"
    )
    metadata = load_metadata(metadata_path)
    points = load_points(points_path)
    return metadata, points, {"metadata": metadata_path, "points": points_path}


def _first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _prepare_points(metadata: dict, points, unique_points: bool):
    if "category" in points.columns:
        points = points.copy()
        points["category_code"] = points["category"].map(CATEGORY_CODES).fillna(-1).astype(int)
    if unique_points:
        fields = present_fields(metadata)
        validate_duplicate_consistency(metadata, points, fields)
        sort_cols = [col for col in ["rank", "ispec", "k", "j", "i"] if col in points.columns]
        ordered = points.sort_values(sort_cols) if sort_cols else points
        points = ordered.drop_duplicates(["rank", "iglob"], keep="first").reset_index(drop=True)
    return points


def _add_array(point_data, name: str, values, vtk_double_array, vtk_int_array) -> None:
    is_integer = name in {
        "category_code",
        "material_changed",
        "cmb_boundary_noncomparable",
        "rank",
        "ispec",
        "iglob",
    }
    array = vtk_int_array() if is_integer else vtk_double_array()
    array.SetName(name)
    for value in values:
        if is_integer:
            if isinstance(value, str):
                value = value.strip().lower() == "true"
            array.InsertNextValue(int(value))
        else:
            array.InsertNextValue(float(value))
    point_data.AddArray(array)


def write_vtp(metadata: dict, points, out_dir: Path) -> Path:
    vtkDoubleArray, vtkIntArray, vtkPoints, vtkCellArray, vtkPolyData, vtkXMLPolyDataWriter, vtkIdList = _import_vtk()
    out_dir.mkdir(parents=True, exist_ok=True)
    r_planet_km = float(metadata["r_planet_km"])

    vtk_points = vtkPoints()
    vertices = vtkCellArray()
    for _, row in points.iterrows():
        point_id = vtk_points.InsertNextPoint(
            float(row["x_norm"]) * r_planet_km,
            float(row["y_norm"]) * r_planet_km,
            float(row["z_norm"]) * r_planet_km,
        )
        ids = vtkIdList()
        ids.InsertNextId(point_id)
        vertices.InsertNextCell(ids)

    poly = vtkPolyData()
    poly.SetPoints(vtk_points)
    poly.SetVerts(vertices)
    point_data = poly.GetPointData()
    for name in POINT_ARRAYS:
        if name in points.columns:
            _add_array(point_data, name, points[name].to_numpy(), vtkDoubleArray, vtkIntArray)

    output = out_dir / "ulvz_gll_points.vtp"
    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(output))
    writer.SetInputData(poly)
    if writer.Write() != 1:
        raise PlotDataError(f"failed writing VTP file: {output}")
    return output


def run(args: argparse.Namespace) -> dict:
    metadata, points, paths = _load(args)
    points = _prepare_points(metadata, points, bool(args.unique_points))
    out_dir = Path(args.out_dir)
    vtp_path = write_vtp(metadata, points, out_dir)
    sidecar = {
        "schema_version": metadata.get("schema_version"),
        "output": str(vtp_path),
        "coordinate_units": "km",
        "coordinate_conversion": "x/y/z = x_norm/y_norm/z_norm * r_planet_km",
        "records_mode": "unique-points" if args.unique_points else "records",
        "point_count": int(len(points)),
        "point_data_arrays": [name for name in POINT_ARRAYS if name in points.columns],
        "inputs": {name: str(path) for name, path in paths.items()},
        "fixture_disclaimer": metadata.get("fixture_disclaimer", ""),
    }
    write_json(out_dir / "ulvz_gll_points_metadata.json", sidecar)
    return sidecar


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (PlotDataError, ValueError, KeyError) as exc:
        print(f"export_paraview_points: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
