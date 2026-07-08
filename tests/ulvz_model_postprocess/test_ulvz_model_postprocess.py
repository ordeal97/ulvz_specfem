import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[2]
TASK3D_FIXTURE = (
    REPO
    / "specfem3d_globe"
    / "tests"
    / "meshfem3D"
    / "s40rts_ulvz_mesh_work_20260702_145132_161444"
)
TASK4_EXTRACTOR = REPO / "specfem3d_globe" / "bin" / "xulvz_model_extract"
PYTHON = os.environ.get(
    "ULVZ_TEST_PYTHON",
    "/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python",
)
if not Path(PYTHON).exists():
    PYTHON = sys.executable


def run_module(*args, env=None):
    full_env = os.environ.copy()
    full_env.setdefault("MPLBACKEND", "Agg")
    full_env.setdefault("MPLCONFIGDIR", str(REPO / ".pytest_cache" / "task4a_mpl"))
    full_env.setdefault("XDG_CACHE_HOME", str(REPO / ".pytest_cache" / "task4a_xdg"))
    if env:
        full_env.update(env)
    return subprocess.run(
        [PYTHON, "-m", "scripts.ulvz_model_postprocess", *map(str, args)],
        cwd=REPO,
        env=full_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_product(root, *, label="model", mode="selected", selection="same", scale=1.0):
    from scripts.ulvz_model_postprocess.rank_store import RankArrays, write_model_product

    arrays = RankArrays(
        rank=0,
        region=1,
        x_km=np.array([0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0], dtype=np.float64),
        y_km=np.array([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float64),
        z_km=np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0], dtype=np.float64),
        x_norm=np.array([0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0], dtype=np.float64),
        y_norm=np.array([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float64),
        z_norm=np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0], dtype=np.float64),
        ibool=np.arange(1, 9, dtype=np.int32).reshape(2, 2, 2, 1),
        idoubling=np.array([1], dtype=np.int32),
        ispec_is_tiso=np.array([False]),
        fields={
            "rho": np.full((2, 2, 2, 1), 3300.0 * scale, dtype=np.float64),
            "vp": np.full((2, 2, 2, 1), 8000.0 * scale, dtype=np.float64),
            "vs": np.full((2, 2, 2, 1), 4500.0 * scale, dtype=np.float64),
        },
    )
    return write_model_product(
        root,
        label=label,
        extraction_mode=mode,
        ranks=[arrays],
        roi={"kind": "near-cmb", "cmb_window_km": [0.0, 160.0]},
        sampling_rule={"kind": "stride", "stride": 2},
        selection_fingerprint=selection,
        provenance={"producer": "pytest"},
    )


def write_tiso_product(root, *, label="model", mode="selected", selection="same", scale=1.0):
    from scripts.ulvz_model_postprocess.rank_store import RankArrays, write_model_product

    arrays = RankArrays(
        rank=0,
        region=1,
        x_km=np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float64),
        y_km=np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float64),
        z_km=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
        x_norm=np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float64),
        y_norm=np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float64),
        z_norm=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
        ibool=np.arange(1, 5, dtype=np.int32).reshape(2, 2, 1, 1),
        idoubling=np.array([1], dtype=np.int32),
        ispec_is_tiso=np.array([True]),
        fields={
            "rho": np.full((2, 2, 1, 1), 3300.0 * scale, dtype=np.float64),
            "vpv": np.full((2, 2, 1, 1), 7800.0 * scale, dtype=np.float64),
            "vph": np.full((2, 2, 1, 1), 7900.0 * scale, dtype=np.float64),
            "vsv": np.full((2, 2, 1, 1), 4400.0 * scale, dtype=np.float64),
            "vsh": np.full((2, 2, 1, 1), 4500.0 * scale, dtype=np.float64),
            "eta": np.full((2, 2, 1, 1), 0.98, dtype=np.float64),
        },
    )
    return write_model_product(
        root,
        label=label,
        extraction_mode=mode,
        ranks=[arrays],
        roi={"kind": "none"},
        sampling_rule={"kind": "none"},
        selection_fingerprint=selection,
        provenance={"producer": "pytest"},
    )


def test_module_help_uses_stable_package_entrypoint():
    result = run_module("--help")
    assert result.returncode == 0, result.stderr
    assert "ulvz_model_postprocess" in result.stdout


def test_rank_store_uses_npy_layout_and_supports_mmap(tmp_path):
    manifest = write_product(tmp_path / "product")
    rank_dir = manifest.parent / "ranks" / "rank000000_reg1"
    assert (rank_dir / "metadata.json").exists()
    assert (rank_dir / "x_km.npy").exists()
    assert (rank_dir / "fields" / "rho.npy").exists()
    assert not list(rank_dir.glob("*.npz"))

    mmap = np.load(rank_dir / "fields" / "rho.npy", mmap_mode="r")
    assert isinstance(mmap, np.memmap)
    assert mmap.shape == (2, 2, 2, 1)

    payload = json.loads(manifest.read_text())
    assert payload["schema_version"] == "ulvz_model_postprocess.v1"
    assert payload["field_units"]["rho"] == "kg m^-3"
    assert payload["field_units"]["vp"] == "m s^-1"
    assert "ratio_fields" not in payload


def test_tiso_rank_store_records_native_fields_units_and_no_ratios(tmp_path):
    manifest = write_tiso_product(tmp_path / "product")
    payload = json.loads(manifest.read_text())
    assert payload["field_units"] == {
        "eta": "dimensionless",
        "rho": "kg m^-3",
        "vph": "m s^-1",
        "vsh": "m s^-1",
        "vpv": "m s^-1",
        "vsv": "m s^-1",
    }
    assert "ratio_fields" not in payload
    rank_dir = manifest.parent / "ranks" / "rank000000_reg1"
    assert isinstance(np.load(rank_dir / "fields" / "vsv.npy", mmap_mode="r"), np.memmap)


def test_full_extraction_requires_allow_large(tmp_path):
    db = tmp_path / "DATABASES_MPI"
    db.mkdir()
    (db / "proc000000_reg1_solver_data.bin").write_bytes(b"not-a-real-database")

    result = run_module(
        "extract",
        "--model",
        f"ulvz={db}",
        "--extract-mode",
        "full",
        "--out-dir",
        tmp_path / "out",
    )
    assert result.returncode != 0
    assert "--allow-large" in result.stderr


def test_selected_raw_extraction_rejects_invalid_solver_layout(tmp_path):
    db = tmp_path / "DATABASES_MPI"
    db.mkdir()
    (db / "proc000000_reg1_solver_data.bin").write_bytes(b"not-a-real-database")

    selected = run_module(
        "extract",
        "--model",
        f"ulvz={db}",
        "--extract-mode",
        "selected",
        "--extractor",
        TASK4_EXTRACTOR,
        "--out-dir",
        tmp_path / "selected",
    )
    assert selected.returncode != 0
    assert "unsupported" in selected.stderr.lower() or "incompatible" in selected.stderr.lower()


def test_selected_raw_extraction_rejects_explicit_full_anisotropic_layout(tmp_path):
    case = tmp_path / "case"
    db = case / "DATABASES_MPI"
    output = case / "OUTPUT_FILES"
    db.mkdir(parents=True)
    output.mkdir()
    (db / "proc000000_reg1_solver_data.bin").write_bytes(b"not-a-real-database")
    (output / "values_from_mesher.h").write_text(
        " logical, parameter :: ANISOTROPIC_3D_MANTLE_VAL = .true.\n",
        encoding="utf-8",
    )

    selected = run_module(
        "extract",
        "--model",
        f"ulvz={db}",
        "--extract-mode",
        "selected",
        "--extractor",
        TASK4_EXTRACTOR,
        "--out-dir",
        tmp_path / "selected",
    )
    assert selected.returncode != 0
    assert "full anisotropic mantle" in selected.stderr.lower()
    assert "unsupported" in selected.stderr.lower()


@pytest.mark.skipif(
    not TASK4_EXTRACTOR.exists() or not TASK3D_FIXTURE.exists(),
    reason="Task 4C preserved fixture or extractor is not available",
)
def test_task4c_extracts_preserved_fixture_and_downstream_products(tmp_path):
    ref_db = TASK3D_FIXTURE / "reference_disabled" / "DATABASES_MPI"
    target_db = TASK3D_FIXTURE / "ulvz_enabled" / "DATABASES_MPI"
    ref_out = tmp_path / "reference_product"
    target_out = tmp_path / "target_product"

    ref = run_module(
        "extract",
        "--model",
        f"reference={ref_db}",
        "--extract-mode",
        "selected",
        "--extractor",
        TASK4_EXTRACTOR,
        "--memory-limit-mb",
        "1024",
        "--out-dir",
        ref_out,
    )
    assert ref.returncode == 0, ref.stderr
    manifest = ref_out / "model_manifest.json"
    payload = json.loads(manifest.read_text())
    assert payload["schema_version"] == "ulvz_model_postprocess.v1"
    assert payload["extraction_mode"] == "selected"
    assert not payload.get("summary_only", False)
    assert payload["field_units"] == {
        "eta": "dimensionless",
        "rho": "kg m^-3",
        "vph": "m s^-1",
        "vsh": "m s^-1",
        "vpv": "m s^-1",
        "vsv": "m s^-1",
    }
    assert "ratio_fields" not in payload
    assert "difference_fields" not in payload
    assert payload["provenance"]["source_database_paths"]
    assert payload["provenance"]["extractor_build"]["custom_real_bytes"] in (4, 8)
    assert payload["provenance"]["memory_estimates"]
    rank_memory = payload["provenance"]["memory_estimates"][0]
    assert rank_memory["decision"] == "accepted"
    assert rank_memory["estimated_peak_memory_bytes"] > 0
    assert rank_memory["estimated_peak_memory_mb"] > 0.0
    assert rank_memory["memory_limit_mb"] == 1024
    assert rank_memory["geometry_topology_bytes"] > 0
    assert rank_memory["source_record_payload_bytes"] > 0
    assert rank_memory["physical_field_array_bytes"] > 0
    assert rank_memory["output_buffer_bytes"] > 0
    assert rank_memory["safety_margin_bytes"] > 0

    rank0 = ref_out / payload["rank_store"]["ranks"][0]["path"]
    rho = np.load(rank0 / "fields" / "rho.npy", mmap_mode="r")
    assert isinstance(rho, np.memmap)
    assert rho.shape[-1] == 4320
    assert float(rho.mean()) > 1000.0
    assert not list((rank0 / "fields").glob("*ratio.npy"))
    assert not list((rank0 / "fields").glob("*difference.npy"))

    low_memory = run_module(
        "extract",
        "--model",
        f"reference={ref_db}",
        "--extract-mode",
        "selected",
        "--extractor",
        TASK4_EXTRACTOR,
        "--memory-limit-mb",
        "1",
        "--out-dir",
        tmp_path / "too_small",
    )
    assert low_memory.returncode != 0
    assert "memory" in low_memory.stderr.lower()
    assert not (tmp_path / "too_small" / "model_manifest.json").exists()

    target = run_module(
        "extract",
        "--model",
        f"ulvz={target_db}",
        "--extract-mode",
        "selected",
        "--extractor",
        TASK4_EXTRACTOR,
        "--memory-limit-mb",
        "1024",
        "--out-dir",
        target_out,
    )
    assert target.returncode == 0, target.stderr

    compare = run_module(
        "compare",
        "--reference",
        f"reference={manifest}",
        "--target",
        f"ulvz={target_out / 'model_manifest.json'}",
        "--comparison-name",
        "fixture_ulvz_over_reference",
        "--out-dir",
        tmp_path / "comparison",
    )
    assert compare.returncode == 0, compare.stderr
    assert (
        tmp_path
        / "comparison"
        / "ranks"
        / "rank000000_reg1"
        / "fields"
        / "vsv_ratio.npy"
    ).exists()

    plot = run_module(
        "plot",
        "--input",
        manifest,
        "--field",
        "vsv",
        "--kind",
        "histogram",
        "--out-dir",
        tmp_path / "figures",
    )
    assert plot.returncode == 0, plot.stderr
    assert (tmp_path / "figures" / "histogram_vsv.png").exists()

    paraview = run_module(
        "paraview",
        "--input",
        manifest,
        "--paraview-kind",
        "points",
        "--out-dir",
        tmp_path / "paraview",
    )
    assert paraview.returncode == 0, paraview.stderr
    assert (tmp_path / "paraview" / "points_metadata.json").exists()


def test_validate_accepts_complete_databases_mpi_and_rejects_bare_file(tmp_path):
    db = tmp_path / "DATABASES_MPI"
    db.mkdir()
    (db / "proc000000_reg1_solver_data.bin").write_bytes(b"fixture")
    ok = run_module("validate", "--model", f"ulvz={db}", "--out-dir", tmp_path / "ok")
    assert ok.returncode == 0, ok.stderr
    assert (tmp_path / "ok" / "input_validation.json").exists()

    bare = tmp_path / "rho.bin"
    bare.write_bytes(b"fixture")
    bad = run_module("validate", "--model", f"bad={bare}", "--out-dir", tmp_path / "bad")
    assert bad.returncode != 0
    assert "DATABASES_MPI" in bad.stderr


def test_compare_plot_paraview_reject_raw_databases_mpi_with_rank_store_message(tmp_path):
    db = tmp_path / "DATABASES_MPI"
    db.mkdir()
    (db / "proc000000_reg1_solver_data.bin").write_bytes(b"fixture")
    manifest = write_product(tmp_path / "product")

    compare = run_module(
        "compare",
        "--reference",
        f"reference={db}",
        "--target",
        f"ulvz={manifest}",
        "--comparison-name",
        "bad",
        "--out-dir",
        tmp_path / "comparison",
    )
    assert compare.returncode != 0
    assert "extracted rank-store manifest" in compare.stderr.lower()
    assert "raw databases_mpi" in compare.stderr.lower()

    plot = run_module(
        "plot",
        "--input",
        db,
        "--field",
        "vs",
        "--kind",
        "histogram",
        "--out-dir",
        tmp_path / "figures",
    )
    assert plot.returncode != 0
    assert "extracted rank-store manifest" in plot.stderr.lower()
    assert "raw databases_mpi" in plot.stderr.lower()

    paraview = run_module(
        "paraview",
        "--input",
        db,
        "--paraview-kind",
        "points",
        "--out-dir",
        tmp_path / "paraview",
    )
    assert paraview.returncode != 0
    assert "extracted rank-store manifest" in paraview.stderr.lower()
    assert "raw databases_mpi" in paraview.stderr.lower()


def test_compare_requires_matching_selection_fingerprint(tmp_path):
    ref = write_product(tmp_path / "ref", label="reference", selection="selection-a")
    target = write_product(tmp_path / "target", label="ulvz", selection="selection-b", scale=0.9)

    result = run_module(
        "compare",
        "--reference",
        f"reference={ref}",
        "--target",
        f"ulvz={target}",
        "--comparison-name",
        "bad",
        "--out-dir",
        tmp_path / "comparison",
    )
    assert result.returncode != 0
    assert "selection fingerprint" in result.stderr.lower()


def test_compare_writes_ratio_and_difference_for_compatible_products(tmp_path):
    ref = write_product(tmp_path / "ref", label="reference", selection="selection-a")
    target = write_product(tmp_path / "target", label="ulvz", selection="selection-a", scale=0.9)

    result = run_module(
        "compare",
        "--reference",
        f"reference={ref}",
        "--target",
        f"ulvz={target}",
        "--comparison-name",
        "ulvz_over_reference",
        "--out-dir",
        tmp_path / "comparison",
    )
    assert result.returncode == 0, result.stderr
    manifest = tmp_path / "comparison" / "ulvz_over_reference_manifest.json"
    payload = json.loads(manifest.read_text())
    assert payload["orientation"]["ratio"] == "target / reference"
    ratio = np.load(
        tmp_path
        / "comparison"
        / "ranks"
        / "rank000000_reg1"
        / "fields"
        / "vs_ratio.npy",
        mmap_mode="r",
    )
    assert isinstance(ratio, np.memmap)
    assert float(ratio[0, 0, 0, 0]) == pytest.approx(0.9)


def test_paraview_metadata_separates_points_and_linear_mesh(tmp_path):
    manifest = write_product(tmp_path / "product")
    result = run_module(
        "paraview",
        "--input",
        manifest,
        "--paraview-kind",
        "both",
        "--out-dir",
        tmp_path / "paraview",
    )
    assert result.returncode == 0, result.stderr
    points = json.loads((tmp_path / "paraview" / "points_metadata.json").read_text())
    mesh = json.loads((tmp_path / "paraview" / "linear_mesh_metadata.json").read_text())
    assert points["semantics"] == "rank-piece GLL point cloud with native point fields"
    assert "does not preserve" in mesh["high_order_geometry_warning"]


@pytest.mark.skipif(pytest.importorskip("vtkmodules", reason="VTK is required for ParaView export validation") is None, reason="VTK missing")
def test_paraview_writes_reopenable_rank_pieces_and_wrappers(tmp_path):
    from vtkmodules.vtkCommonDataModel import VTK_HEXAHEDRON
    from vtkmodules.vtkIOXML import (
        vtkXMLPPolyDataReader,
        vtkXMLPUnstructuredGridReader,
        vtkXMLPolyDataReader,
        vtkXMLUnstructuredGridReader,
    )

    manifest = write_product(tmp_path / "product")
    result = run_module(
        "paraview",
        "--input",
        manifest,
        "--paraview-kind",
        "both",
        "--out-dir",
        tmp_path / "paraview",
    )
    assert result.returncode == 0, result.stderr

    pvtp = tmp_path / "paraview" / "model_points.pvtp"
    pvtu = tmp_path / "paraview" / "model_linear_mesh.pvtu"
    point_piece = tmp_path / "paraview" / "rank000000_reg1_points.vtp"
    mesh_piece = tmp_path / "paraview" / "rank000000_reg1_linear_mesh.vtu"
    for path in [pvtp, pvtu, point_piece, mesh_piece]:
        assert path.exists()
        assert path.stat().st_size > 0

    point_sources = _vtk_piece_sources(pvtp, "PPolyData")
    mesh_sources = _vtk_piece_sources(pvtu, "PUnstructuredGrid")
    assert point_sources == ["rank000000_reg1_points.vtp"]
    assert mesh_sources == ["rank000000_reg1_linear_mesh.vtu"]
    for rel in point_sources + mesh_sources:
        assert (tmp_path / "paraview" / rel).exists()

    point_piece_data = _read_vtp(point_piece, vtkXMLPolyDataReader)
    assert point_piece_data.GetNumberOfPoints() == 8
    assert point_piece_data.GetNumberOfCells() == 8
    assert _point_array_names(point_piece_data) == ["rho", "vp", "vs"]
    assert _array_is_finite(point_piece_data.GetPointData().GetArray("vs"))
    assert max(point_piece_data.GetBounds()) <= 1.0

    point_wrapper_data = _read_vtp(pvtp, vtkXMLPPolyDataReader)
    assert point_wrapper_data.GetNumberOfPoints() == 8
    assert point_wrapper_data.GetPointData().GetArray("rho") is not None

    mesh_piece_data = _read_vtu(mesh_piece, vtkXMLUnstructuredGridReader)
    assert mesh_piece_data.GetNumberOfPoints() == 8
    assert mesh_piece_data.GetNumberOfCells() == 1
    assert mesh_piece_data.GetCellType(0) == VTK_HEXAHEDRON
    cell = mesh_piece_data.GetCell(0)
    assert cell.GetNumberOfPoints() == 8
    assert len({cell.GetPointId(i) for i in range(8)}) == 8
    assert mesh_piece_data.GetPointData().GetArray("vs") is not None
    assert mesh_piece_data.GetCellData().GetArray("vs_mean") is not None

    mesh_wrapper_data = _read_vtu(pvtu, vtkXMLPUnstructuredGridReader)
    assert mesh_wrapper_data.GetNumberOfPoints() == 8
    assert mesh_wrapper_data.GetNumberOfCells() == 1
    assert mesh_wrapper_data.GetCellData().GetArray("rho_mean") is not None


def test_paraview_comparison_exports_only_comparison_arrays(tmp_path):
    from vtkmodules.vtkIOXML import vtkXMLPPolyDataReader, vtkXMLPolyDataReader

    ref = write_product(tmp_path / "ref", label="reference", selection="selection-a")
    target = write_product(tmp_path / "target", label="ulvz", selection="selection-a", scale=0.9)
    compare = run_module(
        "compare",
        "--reference",
        f"reference={ref}",
        "--target",
        f"ulvz={target}",
        "--comparison-name",
        "ulvz_over_reference",
        "--out-dir",
        tmp_path / "comparison",
    )
    assert compare.returncode == 0, compare.stderr
    manifest = tmp_path / "comparison" / "ulvz_over_reference_manifest.json"
    result = run_module(
        "paraview",
        "--input",
        manifest,
        "--paraview-kind",
        "points",
        "--out-dir",
        tmp_path / "paraview",
    )
    assert result.returncode == 0, result.stderr
    piece = _read_vtp(tmp_path / "paraview" / "rank000000_reg1_points.vtp", vtkXMLPolyDataReader)
    names = _point_array_names(piece)
    assert "vs_ratio" in names
    assert "vs_difference" in names
    assert "vs" not in names
    wrapper = _read_vtp(tmp_path / "paraview" / "model_points.pvtp", vtkXMLPPolyDataReader)
    assert wrapper.GetPointData().GetArray("vs_ratio") is not None


def _vtk_piece_sources(path, expected_root):
    tree = ET.parse(path)
    root = tree.getroot()
    assert root.tag == "VTKFile"
    assert root.attrib["type"] == expected_root
    container = root.find(expected_root)
    assert container is not None
    return [piece.attrib["Source"] for piece in container.findall("Piece")]


def _read_vtp(path, reader_cls):
    reader = reader_cls()
    reader.SetFileName(str(path))
    assert reader.CanReadFile(str(path)) == 1
    reader.Update()
    return reader.GetOutput()


def _read_vtu(path, reader_cls):
    reader = reader_cls()
    reader.SetFileName(str(path))
    assert reader.CanReadFile(str(path)) == 1
    reader.Update()
    return reader.GetOutput()


def _point_array_names(dataset):
    point_data = dataset.GetPointData()
    return [point_data.GetArrayName(i) for i in range(point_data.GetNumberOfArrays())]


def _array_is_finite(array):
    return all(np.isfinite(array.GetTuple1(i)) for i in range(array.GetNumberOfTuples()))


def test_static_plot_command_does_not_import_vtk(tmp_path):
    manifest = write_product(tmp_path / "product")
    code = (
        "import json, os, runpy, sys; "
        "sys.argv=['-m','plot','--input',os.environ['MANIFEST'],"
        "'--field','vs','--kind','histogram','--out-dir',os.environ['OUT_DIR']]; "
        "runpy.run_module('scripts.ulvz_model_postprocess', run_name='__main__'); "
        "print(json.dumps({k:(k in sys.modules) for k in ['vtk','vtkmodules','pyvista']}))"
    )
    env = os.environ.copy()
    env.update(
        {
            "MANIFEST": str(manifest),
            "OUT_DIR": str(tmp_path / "figures"),
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mpl"),
            "XDG_CACHE_HOME": str(tmp_path / "xdg"),
        }
    )
    result = subprocess.run(
        [PYTHON, "-c", code],
        cwd=REPO,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "figures" / "histogram_vs.png").exists()
    optional = json.loads(result.stdout.strip().splitlines()[-1])
    assert optional == {"vtk": False, "vtkmodules": False, "pyvista": False}
