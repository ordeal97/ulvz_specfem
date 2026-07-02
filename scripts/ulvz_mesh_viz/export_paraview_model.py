#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulvz_mesh_viz.data import PlotDataError, write_json


REQUIRED_COLUMNS = {
    "rank",
    "ispec",
    "i",
    "j",
    "k",
    "iglob",
    "x_norm",
    "y_norm",
    "z_norm",
    "vp",
    "vs",
    "rho",
}
POINT_ARRAYS = [
    "rank",
    "iglob",
    "x_norm",
    "y_norm",
    "z_norm",
    "radius_km",
    "depth_km",
    "height_above_cmb_km",
    "latitude_deg",
    "longitude_deg",
    "vp",
    "vs",
    "rho",
    "vpv",
    "vph",
    "vsv",
    "vsh",
    "eta",
    "vp_ratio",
    "vs_ratio",
    "rho_ratio",
    "vpv_ratio",
    "vph_ratio",
    "vsv_ratio",
    "vsh_ratio",
    "is_tiso",
]
MATERIAL_ARRAYS = ["vp", "vs", "rho", "vpv", "vph", "vsv", "vsh", "eta"]
RATIO_ARRAYS = [
    "vp_ratio",
    "vs_ratio",
    "rho_ratio",
    "vpv_ratio",
    "vph_ratio",
    "vsv_ratio",
    "vsh_ratio",
]
CELL_ARRAYS = [
    "rank",
    "ispec",
    "subcell_i",
    "subcell_j",
    "subcell_k",
    "vp_mean",
    "vs_mean",
    "rho_mean",
    "vp_ratio_mean",
    "vs_ratio_mean",
    "rho_ratio_mean",
    "vpv_ratio_mean",
    "vph_ratio_mean",
    "vsv_ratio_mean",
    "vsh_ratio_mean",
]
INT_ARRAYS = {"rank", "iglob", "ispec", "subcell_i", "subcell_j", "subcell_k", "is_tiso"}


@dataclass(frozen=True)
class MergeCandidate:
    rank: int
    iglob: int
    x_km: float
    y_km: float
    z_km: float
    fields: tuple[tuple[str, float], ...]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export final SPECFEM GLL-node model records to ParaView VTP/VTU/PVTU."
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--weld-coordinates", action="store_true")
    parser.add_argument("--weld-tolerance", type=float, default=1.0e-6)
    return parser


def _import_vtk():
    try:
        from vtkmodules.vtkCommonCore import vtkDoubleArray, vtkIntArray, vtkPoints
        from vtkmodules.vtkCommonDataModel import (
            VTK_HEXAHEDRON,
            vtkCellArray,
            vtkPolyData,
            vtkUnstructuredGrid,
        )
        from vtkmodules.vtkIOXML import vtkXMLPolyDataWriter, vtkXMLUnstructuredGridWriter
    except Exception as exc:  # pragma: no cover - exercised when optional VTK is absent
        raise PlotDataError(
            "VTK is required for export_paraview_model.py. "
            "Activate an environment with vtk installed."
        ) from exc
    return (
        vtkDoubleArray,
        vtkIntArray,
        vtkPoints,
        vtkCellArray,
        vtkPolyData,
        vtkXMLPolyDataWriter,
        VTK_HEXAHEDRON,
        vtkUnstructuredGrid,
        vtkXMLUnstructuredGridWriter,
    )


def load_metadata(path: Path) -> dict:
    if not path.exists():
        raise PlotDataError(f"missing ParaView model metadata: {path}")
    with path.open(encoding="utf-8") as handle:
        metadata = json.load(handle)
    if metadata.get("schema_version") != "ulvz_paraview_model.v1":
        raise PlotDataError(
            f"unsupported paraview model schema_version {metadata.get('schema_version')!r}"
        )
    return metadata


def rank_record_files(data_dir: Path) -> list[tuple[int, Path]]:
    files = sorted(data_dir.glob("paraview_model_records_rank*.csv.gz"))
    if not files:
        files = sorted(data_dir.glob("paraview_model_records_rank*.csv"))
    result = []
    for path in files:
        match = re.search(r"rank(\d{6})", path.name)
        if match:
            result.append((int(match.group(1)), path))
    if not result:
        raise PlotDataError(f"no rank-local ParaView model record CSV files found in {data_dir}")
    return result


def _tolerances(metadata: dict) -> tuple[float, float]:
    tolerances = metadata.get("merge_tolerances", {})
    coord_tol = float(tolerances.get("coordinate_abs_km", 1.0e-9))
    field_tol = float(tolerances.get("field_abs", 1.0e-8))
    if coord_tol < 0.0 or field_tol < 0.0:
        raise PlotDataError("merge tolerances must be non-negative")
    return coord_tol, field_tol


def _ngll(metadata: dict, records: pd.DataFrame) -> tuple[int, int, int]:
    ngll = metadata.get("ngll", {})
    nx = int(ngll.get("x", records["i"].max()))
    ny = int(ngll.get("y", records["j"].max()))
    nz = int(ngll.get("z", records["k"].max()))
    if nx < 2 or ny < 2 or nz < 2:
        raise PlotDataError(f"invalid NGLL dimensions: {(nx, ny, nz)}")
    return nx, ny, nz


def _prepare_records(metadata: dict, records: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(records.columns))
    if missing:
        raise PlotDataError(f"model records missing required columns: {', '.join(missing)}")
    records = records.copy()
    r_planet_km = float(metadata["r_planet_km"])
    records["x_km"] = records["x_norm"].astype(float) * r_planet_km
    records["y_km"] = records["y_norm"].astype(float) * r_planet_km
    records["z_km"] = records["z_norm"].astype(float) * r_planet_km
    if "radius_km" not in records.columns:
        records["radius_km"] = (
            records["x_km"] ** 2 + records["y_km"] ** 2 + records["z_km"] ** 2
        ) ** 0.5
    if "depth_km" not in records.columns:
        records["depth_km"] = r_planet_km - records["radius_km"]
    if "height_above_cmb_km" not in records.columns and "rcmb_km" in metadata:
        records["height_above_cmb_km"] = records["radius_km"] - float(metadata["rcmb_km"])
    if "is_tiso" in records.columns:
        records["is_tiso"] = records["is_tiso"].map(_to_int_bool)
    return records


def _to_int_bool(value) -> int:
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes", "y"}:
        return 1
    if text in {"false", "f", "0", "no", "n"}:
        return 0
    raise PlotDataError(f"invalid is_tiso boolean value: {value!r}")


def _field_names(records: pd.DataFrame) -> list[str]:
    merge_fields = MATERIAL_ARRAYS + RATIO_ARRAYS
    return [name for name in merge_fields if name in records.columns]


def _candidate_from_row(row: pd.Series, field_names: list[str]) -> MergeCandidate:
    return MergeCandidate(
        rank=int(row["rank"]),
        iglob=int(row["iglob"]),
        x_km=float(row["x_km"]),
        y_km=float(row["y_km"]),
        z_km=float(row["z_km"]),
        fields=tuple((name, float(row[name])) for name in field_names),
    )


def _compatible(a: MergeCandidate, b: MergeCandidate, coord_tol: float, field_tol: float) -> bool:
    if a.rank != b.rank or a.iglob != b.iglob:
        return False
    if max(abs(a.x_km - b.x_km), abs(a.y_km - b.y_km), abs(a.z_km - b.z_km)) > coord_tol:
        return False
    return all(abs(avalue - bvalue) <= field_tol for (_, avalue), (_, bvalue) in zip(a.fields, b.fields))


def build_rank_nodes_and_cells(
    metadata: dict, records: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    records = _prepare_records(metadata, records)
    nx, ny, nz = _ngll(metadata, records)
    coord_tol, field_tol = _tolerances(metadata)
    field_names = _field_names(records)
    buckets: dict[tuple[int, int], list[tuple[int, MergeCandidate]]] = defaultdict(list)
    node_rows: list[dict] = []
    record_to_node: dict[int, int] = {}
    split_keys: set[tuple[int, int]] = set()

    for row_index, row in records.sort_values(["rank", "ispec", "k", "j", "i"]).iterrows():
        candidate = _candidate_from_row(row, field_names)
        key = (candidate.rank, candidate.iglob)
        node_id = None
        for existing_id, existing_candidate in buckets[key]:
            if _compatible(candidate, existing_candidate, coord_tol, field_tol):
                node_id = existing_id
                break
        if node_id is None:
            if buckets[key]:
                split_keys.add(key)
            node_id = len(node_rows) + 1
            buckets[key].append((node_id, candidate))
            node_row = {
                "node_id": node_id,
                "rank": candidate.rank,
                "iglob": candidate.iglob,
                "x_km": candidate.x_km,
                "y_km": candidate.y_km,
                "z_km": candidate.z_km,
            }
            for name in POINT_ARRAYS:
                if name in records.columns and name not in {"rank", "iglob"}:
                    node_row[name] = row[name]
            node_rows.append(node_row)
        record_to_node[int(row_index)] = node_id

    cells: list[dict] = []
    grouped = records.groupby(["rank", "ispec"], sort=True)
    for (rank, ispec), element in grouped:
        element_lookup = {}
        for row_index, row in element.iterrows():
            element_lookup[(int(row["i"]), int(row["j"]), int(row["k"]))] = (
                record_to_node[int(row_index)],
                row,
            )
        for k in range(1, nz):
            for j in range(1, ny):
                for i in range(1, nx):
                    corners = [
                        (i, j, k),
                        (i + 1, j, k),
                        (i + 1, j + 1, k),
                        (i, j + 1, k),
                        (i, j, k + 1),
                        (i + 1, j, k + 1),
                        (i + 1, j + 1, k + 1),
                        (i, j + 1, k + 1),
                    ]
                    missing = [corner for corner in corners if corner not in element_lookup]
                    if missing:
                        raise PlotDataError(
                            f"element rank={rank} ispec={ispec} missing GLL corners {missing}"
                        )
                    corner_nodes = [element_lookup[corner][0] for corner in corners]
                    if len(set(corner_nodes)) != 8:
                        raise PlotDataError(
                            f"element rank={rank} ispec={ispec} subcell {(i, j, k)} "
                            "does not have eight distinct node ids"
                        )
                    corner_rows = [element_lookup[corner][1] for corner in corners]
                    cell = {
                        "rank": int(rank),
                        "ispec": int(ispec),
                        "subcell_i": i,
                        "subcell_j": j,
                        "subcell_k": k,
                    }
                    for idx, node_id in enumerate(corner_nodes):
                        cell[f"node{idx}"] = node_id
                    for name in ["vp", "vs", "rho"]:
                        cell[f"{name}_mean"] = float(
                            sum(float(row[name]) for row in corner_rows) / len(corner_rows)
                        )
                    for name in RATIO_ARRAYS:
                        if name in records.columns:
                            cell[f"{name}_mean"] = float(
                                sum(float(row[name]) for row in corner_rows) / len(corner_rows)
                            )
                    cells.append(cell)

    stats = {
        "field_aware_split_count": len(split_keys),
        "coincident_split_keys": [{"rank": rank, "iglob": iglob} for rank, iglob in sorted(split_keys)],
    }
    return pd.DataFrame(node_rows), pd.DataFrame(cells), stats


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
    (
        vtkDoubleArray,
        vtkIntArray,
        vtkPoints,
        _vtkCellArray,
        _vtkPolyData,
        _vtkXMLPolyDataWriter,
        VTK_HEXAHEDRON,
        vtkUnstructuredGrid,
        _vtkXMLUnstructuredGridWriter,
    ) = _import_vtk()
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


def write_vtp(nodes: pd.DataFrame, path: Path) -> None:
    (
        vtkDoubleArray,
        vtkIntArray,
        vtkPoints,
        vtkCellArray,
        vtkPolyData,
        vtkXMLPolyDataWriter,
        *_rest,
    ) = _import_vtk()
    from vtkmodules.vtkCommonCore import vtkIdList

    vtk_points = vtkPoints()
    vertices = vtkCellArray()
    for _, row in nodes.iterrows():
        point_id = vtk_points.InsertNextPoint(
            float(row["x_km"]), float(row["y_km"]), float(row["z_km"])
        )
        ids = vtkIdList()
        ids.InsertNextId(point_id)
        vertices.InsertNextCell(ids)

    poly = vtkPolyData()
    poly.SetPoints(vtk_points)
    poly.SetVerts(vertices)
    point_data = poly.GetPointData()
    for name in POINT_ARRAYS:
        if name in nodes.columns:
            _add_data_array(point_data, name, nodes[name].to_numpy(), vtkDoubleArray, vtkIntArray)

    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(poly)
    if writer.Write() != 1:
        raise PlotDataError(f"failed writing VTP file: {path}")


def _array_type(name: str) -> str:
    return "Int32" if name in INT_ARRAYS else "Float64"


def write_pvtu(path: Path, piece_names: list[str], point_arrays: list[str], cell_arrays: list[str]) -> None:
    lines = [
        '<?xml version="1.0"?>',
        '<VTKFile type="PUnstructuredGrid" version="0.1" byte_order="LittleEndian">',
        '  <PUnstructuredGrid GhostLevel="0">',
        "    <PPoints>",
        '      <PDataArray type="Float32" NumberOfComponents="3" Name="Points"/>',
        "    </PPoints>",
        "    <PPointData>",
    ]
    for name in point_arrays:
        lines.append(f'      <PDataArray type="{_array_type(name)}" Name="{escape(name)}"/>')
    lines.extend(["    </PPointData>", "    <PCellData>"])
    for name in cell_arrays:
        lines.append(f'      <PDataArray type="{_array_type(name)}" Name="{escape(name)}"/>')
    lines.append("    </PCellData>")
    for piece in piece_names:
        lines.append(f'    <Piece Source="{escape(piece)}"/>')
    lines.extend(["  </PUnstructuredGrid>", "</VTKFile>", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def weld_coordinate_field_nodes(
    rank_tables: list[tuple[int, pd.DataFrame, pd.DataFrame]],
    tolerance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if tolerance <= 0.0:
        raise PlotDataError("--weld-tolerance must be positive")
    representatives: dict[tuple, int] = {}
    welded_rows: list[dict] = []
    remap: dict[tuple[int, int], int] = {}

    for rank, nodes, _ in rank_tables:
        for _, row in nodes.iterrows():
            key = [
                int(round(float(row["x_km"]) / tolerance)),
                int(round(float(row["y_km"]) / tolerance)),
                int(round(float(row["z_km"]) / tolerance)),
            ]
            for name in MATERIAL_ARRAYS:
                if name in nodes.columns:
                    key.append((name, int(round(float(row[name]) / tolerance))))
            for name in RATIO_ARRAYS:
                if name in nodes.columns:
                    key.append((name, int(round(float(row[name]) / tolerance))))
            key_tuple = tuple(key)
            if key_tuple not in representatives:
                welded_id = len(welded_rows) + 1
                representatives[key_tuple] = welded_id
                new_row = row.to_dict()
                new_row["node_id"] = welded_id
                welded_rows.append(new_row)
            else:
                welded_id = representatives[key_tuple]
            remap[(rank, int(row["node_id"]))] = welded_id

    welded_cells = []
    for rank, _nodes, cells in rank_tables:
        for _, row in cells.iterrows():
            new_row = row.to_dict()
            for idx in range(8):
                new_row[f"node{idx}"] = remap[(rank, int(row[f"node{idx}"]))]
            welded_cells.append(new_row)
    return pd.DataFrame(welded_rows), pd.DataFrame(welded_cells)


def run(args: argparse.Namespace) -> dict:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = Path(args.metadata) if args.metadata else data_dir / "paraview_model_metadata.json"
    metadata = load_metadata(metadata_path)

    rank_tables = []
    split_count = 0
    split_keys = []
    total_records = 0
    for rank, path in rank_record_files(data_dir):
        records = pd.read_csv(path)
        total_records += len(records)
        nodes, cells, stats = build_rank_nodes_and_cells(metadata, records)
        rank_tables.append((rank, nodes, cells))
        split_count += int(stats["field_aware_split_count"])
        split_keys.extend(stats["coincident_split_keys"])

    all_nodes = pd.concat([nodes for _, nodes, _ in rank_tables], ignore_index=True)
    write_vtp(all_nodes, out_dir / "ulvz_model_gll_points.vtp")

    if args.weld_coordinates:
        total_rank_local_nodes = sum(len(nodes) for _, nodes, _ in rank_tables)
        welded_nodes, welded_cells = weld_coordinate_field_nodes(rank_tables, args.weld_tolerance)
        output = out_dir / "ulvz_model_mesh_welded.vtu"
        write_vtu(welded_nodes, welded_cells, output)
        sidecar = dict(metadata)
        sidecar.update(
            {
                "node_merge_policy": "coordinate-field-aware-welded",
                "weld_tolerance_km": float(args.weld_tolerance),
                "number_of_input_records": int(total_records),
                "number_of_rank_local_nodes": int(total_rank_local_nodes),
                "number_of_welded_nodes": int(len(welded_nodes)),
                "number_of_exported_cells": int(len(welded_cells)),
                "field_aware_split_count": int(split_count),
                "coincident_split_keys": split_keys,
                "outputs": [str(out_dir / "ulvz_model_gll_points.vtp"), str(output)],
            }
        )
        write_json(out_dir / "ulvz_model_metadata.json", sidecar)
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
        piece = f"ulvz_model_mesh_rank{rank:06d}.vtu"
        write_vtu(nodes, cells, out_dir / piece)
        piece_names.append(piece)

    pvtu = out_dir / "ulvz_model_mesh.pvtu"
    write_pvtu(
        pvtu,
        piece_names,
        [name for name in POINT_ARRAYS if name in point_arrays_seen],
        [name for name in CELL_ARRAYS if name in cell_arrays_seen],
    )
    sidecar = dict(metadata)
    sidecar.update(
        {
            "node_merge_policy": "rank-local-field-aware",
            "weld_tolerance_km": None,
            "number_of_input_records": int(total_records),
            "number_of_rank_local_nodes": int(total_nodes),
            "number_of_welded_nodes": None,
            "number_of_exported_cells": int(total_cells),
            "field_aware_split_count": int(split_count),
            "coincident_split_keys": split_keys,
            "outputs": [str(out_dir / "ulvz_model_gll_points.vtp")]
            + [str(out_dir / name) for name in piece_names]
            + [str(pvtu)],
        }
    )
    write_json(out_dir / "ulvz_model_metadata.json", sidecar)
    return sidecar


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (PlotDataError, KeyError, ValueError) as exc:
        print(f"export_paraview_model: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
