#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulvz_mesh_viz.data import PlotDataError, write_json


POINT_ARRAYS = [
    "rank",
    "iglob",
    "node_id",
    "x_norm",
    "y_norm",
    "z_norm",
    "radius_km",
    "height_above_cmb_km",
    "latitude_deg",
    "longitude_deg",
]
CELL_ARRAYS = [
    "rank",
    "ispec",
    "cell_id",
    "cell_center_radius_km",
    "cell_center_height_above_cmb_km",
    "cell_w_expected_mean",
    "cell_w_expected_min",
    "cell_w_expected_max",
    "cell_has_outside",
    "cell_has_taper",
    "cell_has_core",
    "cell_category_code",
    "material_changed_fraction",
    "rho_ratio_mean",
    "rho_ratio_min",
    "rho_ratio_max",
    "vsv_ratio_mean",
    "vsv_ratio_min",
    "vsv_ratio_max",
    "vsh_ratio_mean",
    "vsh_ratio_min",
    "vsh_ratio_max",
    "vpv_ratio_mean",
    "vpv_ratio_min",
    "vpv_ratio_max",
    "vph_ratio_mean",
    "vph_ratio_min",
    "vph_ratio_max",
]
INT_ARRAYS = {
    "rank",
    "iglob",
    "node_id",
    "ispec",
    "cell_id",
    "cell_has_outside",
    "cell_has_taper",
    "cell_has_core",
    "cell_category_code",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Task 3F rank-local ULVZ mesh CSV files to VTU/PVTU.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--weld-coordinates", action="store_true")
    parser.add_argument("--weld-tolerance", type=float, default=1.0e-6)
    return parser


def _import_vtk():
    try:
        from vtkmodules.vtkCommonCore import vtkDoubleArray, vtkIntArray, vtkPoints
        from vtkmodules.vtkCommonDataModel import VTK_HEXAHEDRON, vtkUnstructuredGrid
        from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridWriter
    except Exception as exc:  # pragma: no cover - exercised when optional VTK is absent
        raise PlotDataError(
            "VTK is required for export_paraview_mesh.py. "
            "Activate an environment with vtk or pyvista installed."
        ) from exc
    return vtkDoubleArray, vtkIntArray, vtkPoints, VTK_HEXAHEDRON, vtkUnstructuredGrid, vtkXMLUnstructuredGridWriter


def load_metadata(path: Path) -> dict:
    if not path.exists():
        raise PlotDataError(f"missing ParaView mesh metadata: {path}")
    with path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("schema_version") != "ulvz_paraview_mesh.v1":
        raise PlotDataError(
            f"unsupported paraview mesh schema_version {metadata.get('schema_version')!r}"
        )
    return metadata


def rank_files(data_dir: Path) -> list[tuple[int, Path, Path]]:
    nodes = sorted(data_dir.glob("paraview_mesh_nodes_rank*.csv.gz"))
    if not nodes:
        nodes = sorted(data_dir.glob("paraview_mesh_nodes_rank*.csv"))
    result = []
    for node_path in nodes:
        match = re.search(r"rank(\d{6})", node_path.name)
        if not match:
            continue
        rank = int(match.group(1))
        cell_gz = data_dir / f"paraview_mesh_cells_rank{rank:06d}.csv.gz"
        cell_csv = data_dir / f"paraview_mesh_cells_rank{rank:06d}.csv"
        cell_path = cell_gz if cell_gz.exists() else cell_csv
        if not cell_path.exists():
            raise PlotDataError(f"missing cell CSV for rank {rank}: {cell_path}")
        result.append((rank, node_path, cell_path))
    if not result:
        raise PlotDataError(f"no rank-local ParaView mesh CSV files found in {data_dir}")
    return result


def _add_data_array(data, name: str, values, vtk_double_array, vtk_int_array) -> None:
    array = vtk_int_array() if name in INT_ARRAYS else vtk_double_array()
    array.SetName(name)
    for value in values:
        if name in INT_ARRAYS:
            array.InsertNextValue(int(value))
        else:
            array.InsertNextValue(float(value))
    data.AddArray(array)


def build_grid(nodes: pd.DataFrame, cells: pd.DataFrame):
    vtkDoubleArray, vtkIntArray, vtkPoints, VTK_HEXAHEDRON, vtkUnstructuredGrid, _ = _import_vtk()
    required_nodes = {"node_id", "x_km", "y_km", "z_km"}
    required_cells = {"node0", "node1", "node2", "node3", "node4", "node5", "node6", "node7"}
    missing_nodes = sorted(required_nodes - set(nodes.columns))
    missing_cells = sorted(required_cells - set(cells.columns))
    if missing_nodes:
        raise PlotDataError(f"nodes missing required columns: {', '.join(missing_nodes)}")
    if missing_cells:
        raise PlotDataError(f"cells missing required columns: {', '.join(missing_cells)}")

    vtk_points = vtkPoints()
    id_to_point = {}
    for point_index, row in nodes.reset_index(drop=True).iterrows():
        node_id = int(row["node_id"])
        id_to_point[node_id] = point_index
        vtk_points.InsertNextPoint(float(row["x_km"]), float(row["y_km"]), float(row["z_km"]))

    grid = vtkUnstructuredGrid()
    grid.SetPoints(vtk_points)
    for _, row in cells.iterrows():
        point_ids = [id_to_point[int(row[f"node{idx}"])] for idx in range(8)]
        grid.InsertNextCell(VTK_HEXAHEDRON, 8, point_ids)

    point_data = grid.GetPointData()
    for name in POINT_ARRAYS:
        if name in nodes.columns:
            _add_data_array(point_data, name, nodes[name].to_numpy(), vtkDoubleArray, vtkIntArray)
    cell_data = grid.GetCellData()
    for name in CELL_ARRAYS:
        if name in cells.columns:
            _add_data_array(cell_data, name, cells[name].to_numpy(), vtkDoubleArray, vtkIntArray)
    return grid


def write_vtu(nodes: pd.DataFrame, cells: pd.DataFrame, path: Path) -> None:
    *_, vtkXMLUnstructuredGridWriter = _import_vtk()
    grid = build_grid(nodes, cells)
    writer = vtkXMLUnstructuredGridWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(grid)
    if writer.Write() != 1:
        raise PlotDataError(f"failed writing VTU file: {path}")


def weld_coordinate_nodes(
    rank_tables: list[tuple[int, pd.DataFrame, pd.DataFrame]],
    tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if tolerance <= 0.0:
        raise PlotDataError("--weld-tolerance must be positive")
    representatives: dict[tuple[int, int, int], int] = {}
    welded_rows: list[dict] = []
    remap: dict[tuple[int, int], int] = {}

    for rank, nodes, _ in rank_tables:
        for _, row in nodes.iterrows():
            key = (
                int(round(float(row["x_km"]) / tolerance)),
                int(round(float(row["y_km"]) / tolerance)),
                int(round(float(row["z_km"]) / tolerance)),
            )
            if key not in representatives:
                welded_id = len(welded_rows) + 1
                representatives[key] = welded_id
                new_row = row.to_dict()
                new_row["node_id"] = welded_id
                welded_rows.append(new_row)
            else:
                welded_id = representatives[key]
                rep = welded_rows[welded_id - 1]
                dx = abs(float(row["x_km"]) - float(rep["x_km"]))
                dy = abs(float(row["y_km"]) - float(rep["y_km"]))
                dz = abs(float(row["z_km"]) - float(rep["z_km"]))
                if max(dx, dy, dz) > tolerance:
                    raise PlotDataError("coordinate welding key collision exceeded tolerance")
            remap[(rank, int(row["node_id"]))] = welded_id

    welded_cells = []
    for rank, _, cells in rank_tables:
        for _, row in cells.iterrows():
            new_row = row.to_dict()
            for idx in range(8):
                new_row[f"node{idx}"] = remap[(rank, int(row[f"node{idx}"]))]
            welded_cells.append(new_row)
    return pd.DataFrame(welded_rows), pd.DataFrame(welded_cells)


def _array_type(name: str) -> str:
    return "Int32" if name in INT_ARRAYS else "Float64"


def write_pvtu(path: Path, piece_names: list[str], point_arrays: list[str], cell_arrays: list[str]) -> None:
    lines = [
        '<?xml version="1.0"?>',
        '<VTKFile type="PUnstructuredGrid" version="0.1" byte_order="LittleEndian">',
        '  <PUnstructuredGrid GhostLevel="0">',
        '    <PPoints>',
        '      <PDataArray type="Float32" NumberOfComponents="3" Name="Points"/>',
        '    </PPoints>',
        '    <PPointData>',
    ]
    for name in point_arrays:
        lines.append(f'      <PDataArray type="{_array_type(name)}" Name="{escape(name)}"/>')
    lines.extend(['    </PPointData>', '    <PCellData>'])
    for name in cell_arrays:
        lines.append(f'      <PDataArray type="{_array_type(name)}" Name="{escape(name)}"/>')
    lines.append('    </PCellData>')
    for piece in piece_names:
        lines.append(f'    <Piece Source="{escape(piece)}"/>')
    lines.extend(['  </PUnstructuredGrid>', '</VTKFile>', ''])
    path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = Path(args.metadata) if args.metadata else data_dir / "paraview_mesh_metadata.json"
    metadata = load_metadata(metadata_path)
    rank_tables = []
    for rank, node_path, cell_path in rank_files(data_dir):
        rank_tables.append((rank, pd.read_csv(node_path), pd.read_csv(cell_path)))

    if args.weld_coordinates:
        total_rank_local_nodes = sum(len(nodes) for _, nodes, _ in rank_tables)
        welded_nodes, welded_cells = weld_coordinate_nodes(rank_tables, args.weld_tolerance)
        output = out_dir / "ulvz_mesh_welded.vtu"
        write_vtu(welded_nodes, welded_cells, output)
        sidecar = dict(metadata)
        sidecar.update(
            {
                "node_merge_policy": "coordinate-welded",
                "weld_tolerance": float(args.weld_tolerance),
                "number_of_rank_local_nodes": int(total_rank_local_nodes),
                "number_of_welded_nodes": int(len(welded_nodes)),
                "number_of_exported_cells": int(len(welded_cells)),
                "outputs": [str(output)],
            }
        )
        write_json(out_dir / "ulvz_mesh_metadata.json", sidecar)
        return sidecar

    piece_names = []
    point_arrays_seen: set[str] = set()
    cell_arrays_seen: set[str] = set()
    total_nodes = 0
    total_cells = 0
    for rank, nodes, cells in rank_tables:
        total_nodes += len(nodes)
        total_cells += len(cells)
        point_arrays_seen.update(name for name in POINT_ARRAYS if name in nodes.columns)
        cell_arrays_seen.update(name for name in CELL_ARRAYS if name in cells.columns)
        piece = f"ulvz_mesh_rank{rank:06d}.vtu"
        write_vtu(nodes, cells, out_dir / piece)
        piece_names.append(piece)

    pvtu = out_dir / "ulvz_mesh.pvtu"
    write_pvtu(
        pvtu,
        piece_names,
        [name for name in POINT_ARRAYS if name in point_arrays_seen],
        [name for name in CELL_ARRAYS if name in cell_arrays_seen],
    )
    sidecar = dict(metadata)
    sidecar.update(
        {
            "node_merge_policy": "rank-local",
            "weld_tolerance": None,
            "number_of_rank_local_nodes": int(total_nodes),
            "number_of_welded_nodes": None,
            "number_of_exported_cells": int(total_cells),
            "outputs": [str(out_dir / name) for name in piece_names] + [str(pvtu)],
        }
    )
    write_json(out_dir / "ulvz_mesh_metadata.json", sidecar)
    return sidecar


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (PlotDataError, KeyError, ValueError) as exc:
        print(f"export_paraview_mesh: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
