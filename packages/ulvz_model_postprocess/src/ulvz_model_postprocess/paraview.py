from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ulvz_model_postprocess.errors import ModelPostprocessError
from ulvz_model_postprocess.schema import read_json, write_json


@dataclass(frozen=True)
class RankContext:
    rank: int
    region: int
    name: str
    geometry_dir: Path
    fields_dir: Path
    field_names: list[str]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True)
    parser.add_argument("--paraview-kind", choices=["points", "linear-mesh", "both"], default="points")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--weld-coordinates", action="store_true")
    parser.add_argument("--weld-tolerance-km", type=float, default=1.0e-6)
    parser.add_argument("--max-cells", type=int, default=1_000_000)


def run(args: argparse.Namespace) -> dict:
    input_path = Path(args.input)
    manifest = read_json(input_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    contexts = _rank_contexts(input_path, manifest)
    outputs = {}
    if args.paraview_kind in {"points", "both"}:
        outputs["points"] = _write_points_product(out_dir, manifest, contexts)
    if args.paraview_kind in {"linear-mesh", "both"}:
        outputs["linear_mesh"] = _write_linear_mesh_product(out_dir, manifest, contexts, args)
    return outputs


def _rank_contexts(manifest_path: Path, manifest: dict) -> list[RankContext]:
    root = manifest_path.parent
    if "comparison_name" in manifest:
        reference_path = Path(manifest["reference"]["manifest"])
        reference = read_json(reference_path)
        geometry_root = reference_path.parent
        field_names = sorted(manifest.get("field_units", {}))
        contexts = []
        for rank in manifest["rank_store"]["ranks"]:
            geometry_rank = _matching_rank(reference, rank["rank"], rank["region"])
            fields_dir = root / rank["path"] / "fields"
            contexts.append(
                RankContext(
                    rank=int(rank["rank"]),
                    region=int(rank["region"]),
                    name=Path(rank["path"]).name,
                    geometry_dir=geometry_root / geometry_rank["path"],
                    fields_dir=fields_dir,
                    field_names=field_names,
                )
            )
        return contexts

    contexts = []
    for rank in manifest["rank_store"]["ranks"]:
        rank_dir = root / rank["path"]
        contexts.append(
            RankContext(
                rank=int(rank["rank"]),
                region=int(rank["region"]),
                name=Path(rank["path"]).name,
                geometry_dir=rank_dir,
                fields_dir=rank_dir / "fields",
                field_names=list(rank.get("fields") or sorted(manifest.get("field_units", {}))),
            )
        )
    return contexts


def _matching_rank(manifest: dict, rank_id: int, region: int) -> dict:
    for rank in manifest["rank_store"]["ranks"]:
        if int(rank["rank"]) == int(rank_id) and int(rank["region"]) == int(region):
            return rank
    raise ModelPostprocessError(f"reference manifest lacks geometry for rank {rank_id} region {region}")


def _write_points_product(out_dir: Path, manifest: dict, contexts: list[RankContext]) -> dict:
    _require_vtk()
    piece_paths = []
    field_names: list[str] = []
    for context in contexts:
        piece_path = out_dir / f"{context.name}_points.vtp"
        arrays = _load_rank_arrays(context)
        _write_point_piece(piece_path, arrays, context.field_names)
        _validate_piece(piece_path, "vtp", require_cells=True)
        piece_paths.append(piece_path)
        field_names = _merge_field_names(field_names, context.field_names)

    wrapper = out_dir / "model_points.pvtp"
    _write_parallel_wrapper(
        wrapper,
        vtk_type="PPolyData",
        container_name="PPolyData",
        piece_paths=piece_paths,
        point_fields=field_names,
        cell_fields=[],
    )
    _validate_wrapper(wrapper, "pvtp")
    payload = {
        "schema_version": "ulvz_model_postprocess.paraview_points.v1",
        "source_schema_version": manifest.get("schema_version"),
        "semantics": "rank-piece GLL point cloud with native point fields",
        "wrapper": str(wrapper.name),
        "piece_files": [path.name for path in piece_paths],
        "coordinate_units": "km",
        "point_fields": field_names,
        "rank_piece_policy": "one VTP piece per extracted rank/region",
    }
    write_json(out_dir / "points_metadata.json", payload)
    return payload


def _write_linear_mesh_product(
    out_dir: Path,
    manifest: dict,
    contexts: list[RankContext],
    args: argparse.Namespace,
) -> dict:
    _require_vtk()
    piece_paths = []
    field_names: list[str] = []
    cell_field_names: list[str] = []
    total_cells = 0
    for context in contexts:
        arrays = _load_rank_arrays(context)
        nspec = int(arrays["ibool"].shape[3])
        total_cells += nspec
        if total_cells > int(args.max_cells):
            raise ModelPostprocessError(
                f"linear-mesh export would write {total_cells} cells, exceeding --max-cells={args.max_cells}"
            )
        piece_path = out_dir / f"{context.name}_linear_mesh.vtu"
        _write_linear_mesh_piece(piece_path, arrays, context.field_names)
        _validate_piece(piece_path, "vtu", require_cells=True)
        piece_paths.append(piece_path)
        field_names = _merge_field_names(field_names, context.field_names)
        cell_field_names = _merge_field_names(cell_field_names, [f"{name}_mean" for name in context.field_names])

    wrapper = out_dir / "model_linear_mesh.pvtu"
    _write_parallel_wrapper(
        wrapper,
        vtk_type="PUnstructuredGrid",
        container_name="PUnstructuredGrid",
        piece_paths=piece_paths,
        point_fields=field_names,
        cell_fields=cell_field_names,
    )
    _validate_wrapper(wrapper, "pvtu")
    payload = {
        "schema_version": "ulvz_model_postprocess.paraview_linear_mesh.v1",
        "source_schema_version": manifest.get("schema_version"),
        "semantics": "rank-piece linearized 8-corner hexahedral visualization mesh",
        "wrapper": str(wrapper.name),
        "piece_files": [path.name for path in piece_paths],
        "coordinate_units": "km",
        "point_fields": field_names,
        "cell_fields": cell_field_names,
        "cell_data_rule": "cell arrays are per-element means of native GLL values",
        "point_data_rule": "point arrays are corner-node samples on the linearized mesh",
        "high_order_geometry_warning": (
            "linear-mesh output does not preserve the full high-order GLL field or curved "
            "spectral-element geometry"
        ),
        "weld_coordinates": bool(args.weld_coordinates),
        "weld_tolerance_km": float(args.weld_tolerance_km) if args.weld_coordinates else None,
        "max_cells": int(args.max_cells),
    }
    write_json(out_dir / "linear_mesh_metadata.json", payload)
    return payload


def _require_vtk() -> None:
    try:
        import vtkmodules  # noqa: F401
    except Exception as exc:  # pragma: no cover - exercised only without VTK
        raise ModelPostprocessError("ParaView export requires VTK Python modules") from exc


def _load_rank_arrays(context: RankContext) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {
        "x_km": np.load(context.geometry_dir / "x_km.npy", mmap_mode="r"),
        "y_km": np.load(context.geometry_dir / "y_km.npy", mmap_mode="r"),
        "z_km": np.load(context.geometry_dir / "z_km.npy", mmap_mode="r"),
        "ibool": np.load(context.geometry_dir / "ibool.npy", mmap_mode="r"),
    }
    fields = {}
    for name in context.field_names:
        path = context.fields_dir / f"{name}.npy"
        if not path.exists():
            raise ModelPostprocessError(f"missing rank field array for ParaView export: {path}")
        fields[name] = np.load(path, mmap_mode="r")
    arrays["fields"] = fields
    _validate_rank_shapes(context, arrays)
    return arrays


def _validate_rank_shapes(context: RankContext, arrays: dict[str, np.ndarray]) -> None:
    ibool = arrays["ibool"]
    if ibool.ndim != 4:
        raise ModelPostprocessError(f"rank {context.name} ibool must be 4-D, got shape {ibool.shape}")
    nglob = len(arrays["x_km"])
    if len(arrays["y_km"]) != nglob or len(arrays["z_km"]) != nglob:
        raise ModelPostprocessError(f"rank {context.name} coordinate arrays have inconsistent lengths")
    if int(np.max(ibool)) > nglob or int(np.min(ibool)) < 1:
        raise ModelPostprocessError(f"rank {context.name} ibool contains invalid one-based global indices")
    for name, values in arrays["fields"].items():
        if values.shape != ibool.shape:
            raise ModelPostprocessError(
                f"rank {context.name} field {name} shape {values.shape} does not match ibool {ibool.shape}"
            )


def _write_point_piece(path: Path, arrays: dict[str, np.ndarray], field_names: list[str]) -> None:
    from vtkmodules.vtkCommonCore import vtkPoints
    from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
    from vtkmodules.vtkIOXML import vtkXMLPolyDataWriter

    iglob = np.asarray(arrays["ibool"]).ravel(order="F").astype(np.int64) - 1
    points = vtkPoints()
    points.SetData(_vtk_array(np.column_stack((arrays["x_km"][iglob], arrays["y_km"][iglob], arrays["z_km"][iglob]))))
    verts = vtkCellArray()
    for point_id in range(len(iglob)):
        verts.InsertNextCell(1)
        verts.InsertCellPoint(point_id)

    poly = vtkPolyData()
    poly.SetPoints(points)
    poly.SetVerts(verts)
    for name in field_names:
        values = np.asarray(arrays["fields"][name]).ravel(order="F")
        data = _vtk_array(values)
        data.SetName(name)
        poly.GetPointData().AddArray(data)

    writer = vtkXMLPolyDataWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(poly)
    if writer.Write() != 1:
        raise ModelPostprocessError(f"failed to write VTP piece: {path}")


def _write_linear_mesh_piece(path: Path, arrays: dict[str, np.ndarray], field_names: list[str]) -> None:
    from vtkmodules.vtkCommonCore import vtkPoints
    from vtkmodules.vtkCommonDataModel import VTK_HEXAHEDRON, vtkUnstructuredGrid
    from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridWriter

    x = np.asarray(arrays["x_km"], dtype=np.float64)
    y = np.asarray(arrays["y_km"], dtype=np.float64)
    z = np.asarray(arrays["z_km"], dtype=np.float64)
    ibool = arrays["ibool"]
    points = vtkPoints()
    points.SetData(_vtk_array(np.column_stack((x, y, z))))

    grid = vtkUnstructuredGrid()
    grid.SetPoints(points)
    corner_ids = _corner_global_ids(ibool)
    for ids in corner_ids:
        grid.InsertNextCell(VTK_HEXAHEDRON, 8, ids.astype(np.int64))

    nglob = len(x)
    for name in field_names:
        field = np.asarray(arrays["fields"][name])
        point_values = _corner_point_values(field, corner_ids, nglob)
        point_data = _vtk_array(point_values)
        point_data.SetName(name)
        grid.GetPointData().AddArray(point_data)

        cell_data = _vtk_array(_cell_means(field))
        cell_data.SetName(f"{name}_mean")
        grid.GetCellData().AddArray(cell_data)

    writer = vtkXMLUnstructuredGridWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(grid)
    if writer.Write() != 1:
        raise ModelPostprocessError(f"failed to write VTU piece: {path}")


def _vtk_array(values: np.ndarray):
    from vtkmodules.util.numpy_support import numpy_to_vtk

    contiguous = np.ascontiguousarray(values)
    return numpy_to_vtk(contiguous, deep=True)


def _corner_global_ids(ibool: np.ndarray) -> np.ndarray:
    nx, ny, nz, nspec = ibool.shape
    corners = np.empty((nspec, 8), dtype=np.int64)
    for ispec in range(nspec):
        ids = [
            ibool[0, 0, 0, ispec],
            ibool[nx - 1, 0, 0, ispec],
            ibool[nx - 1, ny - 1, 0, ispec],
            ibool[0, ny - 1, 0, ispec],
            ibool[0, 0, nz - 1, ispec],
            ibool[nx - 1, 0, nz - 1, ispec],
            ibool[nx - 1, ny - 1, nz - 1, ispec],
            ibool[0, ny - 1, nz - 1, ispec],
        ]
        corners[ispec, :] = np.asarray(ids, dtype=np.int64) - 1
    return corners


def _corner_point_values(field: np.ndarray, corner_ids: np.ndarray, nglob: int) -> np.ndarray:
    nx, ny, nz, nspec = field.shape
    values = np.full(nglob, np.nan, dtype=np.float64)
    for ispec in range(nspec):
        corner_values = [
            field[0, 0, 0, ispec],
            field[nx - 1, 0, 0, ispec],
            field[nx - 1, ny - 1, 0, ispec],
            field[0, ny - 1, 0, ispec],
            field[0, 0, nz - 1, ispec],
            field[nx - 1, 0, nz - 1, ispec],
            field[nx - 1, ny - 1, nz - 1, ispec],
            field[0, ny - 1, nz - 1, ispec],
        ]
        values[corner_ids[ispec, :]] = corner_values
    return values


def _cell_means(field: np.ndarray) -> np.ndarray:
    values = np.asarray(field, dtype=np.float64)
    nspec = values.shape[3]
    return values.reshape((values.shape[0] * values.shape[1] * values.shape[2], nspec), order="F").mean(axis=0)


def _write_parallel_wrapper(
    path: Path,
    *,
    vtk_type: str,
    container_name: str,
    piece_paths: list[Path],
    point_fields: list[str],
    cell_fields: list[str],
) -> None:
    root = ET.Element("VTKFile", {"type": vtk_type, "version": "0.1", "byte_order": "LittleEndian"})
    container = ET.SubElement(root, container_name)
    point_data = ET.SubElement(container, "PPointData")
    for name in point_fields:
        ET.SubElement(point_data, "PDataArray", {"type": "Float64", "Name": name})
    if container_name == "PUnstructuredGrid":
        cell_data = ET.SubElement(container, "PCellData")
        for name in cell_fields:
            ET.SubElement(cell_data, "PDataArray", {"type": "Float64", "Name": name})
    points = ET.SubElement(container, "PPoints")
    ET.SubElement(points, "PDataArray", {"type": "Float64", "NumberOfComponents": "3"})
    for piece in piece_paths:
        ET.SubElement(container, "Piece", {"Source": piece.name})
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)
    _validate_wrapper_xml(path, container_name)


def _validate_wrapper_xml(path: Path, container_name: str) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "VTKFile" or root.get("type") != container_name:
        raise ModelPostprocessError(f"invalid VTK wrapper root/type in {path}")
    container = root.find(container_name)
    if container is None:
        raise ModelPostprocessError(f"invalid VTK wrapper {path}: missing {container_name}")
    pieces = container.findall("Piece")
    if not pieces:
        raise ModelPostprocessError(f"invalid VTK wrapper {path}: no Piece references")
    for piece in pieces:
        source = piece.get("Source")
        if not source or Path(source).is_absolute() or not (path.parent / source).exists():
            raise ModelPostprocessError(f"invalid VTK wrapper {path}: unresolved piece Source={source!r}")


def _validate_piece(path: Path, extension: str, *, require_cells: bool) -> None:
    if extension == "vtp":
        from vtkmodules.vtkIOXML import vtkXMLPolyDataReader

        reader = vtkXMLPolyDataReader()
    elif extension == "vtu":
        from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridReader

        reader = vtkXMLUnstructuredGridReader()
    else:
        raise AssertionError(extension)
    reader.SetFileName(str(path))
    if reader.CanReadFile(str(path)) != 1:
        raise ModelPostprocessError(f"VTK cannot read generated {extension.upper()} piece: {path}")
    reader.Update()
    output = reader.GetOutput()
    if output.GetNumberOfPoints() <= 0:
        raise ModelPostprocessError(f"generated VTK piece has no points: {path}")
    if require_cells and output.GetNumberOfCells() <= 0:
        raise ModelPostprocessError(f"generated VTK piece has no cells: {path}")


def _validate_wrapper(path: Path, extension: str) -> None:
    if extension == "pvtp":
        from vtkmodules.vtkIOXML import vtkXMLPPolyDataReader

        reader = vtkXMLPPolyDataReader()
    elif extension == "pvtu":
        from vtkmodules.vtkIOXML import vtkXMLPUnstructuredGridReader

        reader = vtkXMLPUnstructuredGridReader()
    else:
        raise AssertionError(extension)
    reader.SetFileName(str(path))
    if reader.CanReadFile(str(path)) != 1:
        raise ModelPostprocessError(f"VTK cannot read generated {extension.upper()} wrapper: {path}")
    reader.Update()
    output = reader.GetOutput()
    if output.GetNumberOfPoints() <= 0:
        raise ModelPostprocessError(f"generated VTK wrapper has no points: {path}")


def _merge_field_names(existing: list[str], new: list[str]) -> list[str]:
    merged = list(existing)
    for name in new:
        if name not in merged:
            merged.append(name)
    return merged
