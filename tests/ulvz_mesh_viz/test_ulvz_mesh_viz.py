import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


REPO = Path(__file__).resolve().parents[2]
PYTHON = os.environ.get("ULVZ_TEST_PYTHON", sys.executable)
SCRIPTS = REPO / "scripts" / "ulvz_mesh_viz"


def metadata(fields_present=None):
    return {
        "schema_version": "ulvz_mesh_viz.v1",
        "producer": "pytest",
        "created_utc": "2026-06-30T00:00:00Z",
        "specfem_version": "test",
        "git_commit": "test",
        "mpi_command": "not-run",
        "nproc": 2,
        "omp_num_threads": 1,
        "r_planet_km": 6371.0,
        "rcmb_km": 3480.0,
        "coordinate_convention": {
            "cartesian": "SPECFEM normalized x/y/z",
            "latitude": "geographic",
            "longitude": "degrees east, [-180, 180)",
        },
        "ulvz": {
            "center_latitude_deg": 45.0,
            "center_longitude_deg": 140.0,
            "thickness_km": 80.0,
            "lateral_radius_km": 400.0,
            "lateral_taper_km": 100.0,
            "top_taper_km": 20.0,
            "dVp": -0.10,
            "dVs": -0.20,
            "dRho": 0.05,
        },
        "fields_present": fields_present
        or {"rho": True, "vsv": True, "vsh": True, "vpv": True, "vph": True},
        "sampling_rule": {
            "full_source_count": 6,
            "exported_count": 6,
            "outside_stride": 1,
            "retained_counts_by_category": {"outside": 2, "taper": 2, "core": 2},
        },
        "duplicate_policy": {"unique_plotting_key": ["rank", "iglob"]},
        "fixture_disclaimer": (
            "S40RTS ULVZ mesher validation fixture; NEX_XI=32, "
            "NEX_ETA=32, NPROC=2; Not a production waveform-resolution mesh"
        ),
        "tolerances": {
            "coordinate_abs": 1.0e-9,
            "w_expected_abs": 1.0e-9,
            "ratio_abs": 5.0e-5,
            "residual_abs": 5.0e-5,
        },
        "default_section_azimuth_deg": 0.0,
    }


def base_points(include_vsh_vph=True, duplicate_consistent=True):
    rows = [
        (1, "outside", 0.0, 0.0, 1.0, 3480.0, 0.0, 0.0, 0.0),
        (2, "taper", 0.5, 0.0, 1.0, 3500.0, 20.0, 0.0, 20.0),
        (3, "core", 1.0, 0.0, 1.0, 3520.0, 40.0, 0.0, 40.0),
        (4, "outside", 0.0, 120.0, 1.0, 3485.0, 5.0, 120.0, 5.0),
        (5, "taper", 0.25, 40.0, 1.0, 3510.0, 30.0, 40.0, 30.0),
        (6, "core", 1.0, -40.0, 1.0, 3525.0, 45.0, -40.0, 45.0),
    ]
    records = []
    for record_id, category, w, section_dist, radius_norm, radius_km, height, lateral, depth in rows:
        rho_expected = 1.0 + w * 0.05
        vs_expected = 1.0 + w * -0.20
        vp_expected = 1.0 + w * -0.10
        record = {
            "record_id": record_id,
            "record_kind": "element_gll",
            "rank": 0,
            "ispec": record_id,
            "i": 1,
            "j": 1,
            "k": 1,
            "iglob": record_id,
            "is_shared_duplicate": False,
            "x_norm": 0.1 * record_id,
            "y_norm": 0.2 * record_id,
            "z_norm": 0.3 * record_id,
            "radius_norm": radius_norm,
            "radius_km": radius_km,
            "depth_km": depth,
            "height_above_cmb_km": height,
            "latitude_deg": 45.0 + record_id * 0.01,
            "longitude_deg": 140.0 + record_id * 0.01,
            "point_azimuth_deg": 0.0 if section_dist >= 0 else 180.0,
            "angular_distance_deg": lateral / 3480.0 * 57.29577951308232,
            "lateral_distance_km": abs(lateral),
            "section_azimuth_deg": 0.0,
            "section_distance_km": section_dist,
            "cross_section_offset_km": 0.0,
            "w_expected": w,
            "category": category,
            "rho_expected": rho_expected,
            "rho_ratio": rho_expected,
            "rho_residual": 0.0,
            "vsv_expected": vs_expected,
            "vsv_ratio": vs_expected,
            "vsv_residual": 0.0,
            "vpv_expected": vp_expected,
            "vpv_ratio": vp_expected,
            "vpv_residual": 0.0,
            "cmb_boundary_noncomparable": False,
            "material_changed": w > 0,
            "is_tiso": include_vsh_vph,
        }
        if include_vsh_vph:
            record.update(
                {
                    "vsh_expected": vs_expected,
                    "vsh_ratio": vs_expected,
                    "vsh_residual": 0.0,
                    "vph_expected": vp_expected,
                    "vph_ratio": vp_expected,
                    "vph_residual": 0.0,
                }
            )
        records.append(record)

    duplicate = dict(records[0])
    duplicate["record_id"] = 7
    duplicate["ispec"] = 7
    duplicate["is_shared_duplicate"] = True
    if not duplicate_consistent:
        duplicate["w_expected"] = 0.25
    records.append(duplicate)
    return pd.DataFrame(records)


def comparison_summary():
    rows = [
        ("tolerance", "ratio", "all", 5.0e-5),
        ("geometry_tolerance_km", "geometry", "all", 1.0e-3),
    ]
    for category, count in [("outside", 2), ("taper", 2), ("core", 2)]:
        rows.append(("category_count", "w", category, count))
    for field in ["rho", "vsv", "vsh", "vpv", "vph"]:
        rows.append(("max_residual", field, "all", 0.0))
    return pd.DataFrame(rows, columns=["record", "field", "category", "value"])


def write_fixture(tmp_path, *, gzip_points=False, fields_present=None, points=None):
    data_dir = tmp_path / "reports"
    data_dir.mkdir()
    meta = metadata(fields_present=fields_present)
    (data_dir / "mesh_visualization_metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    df = points if points is not None else base_points()
    csv_text = df.to_csv(index=False)
    if gzip_points:
        with gzip.open(data_dir / "mesh_gll_points.csv.gz", "wt", encoding="utf-8") as handle:
            handle.write(csv_text)
    else:
        (data_dir / "mesh_gll_points.csv").write_text(csv_text, encoding="utf-8")
    comparison_summary().to_csv(data_dir / "comparison_summary.csv", index=False)
    return data_dir


def run_script(name, *args):
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    env["MPLCONFIGDIR"] = str(REPO / ".pytest_cache" / "mplconfig")
    env["XDG_CACHE_HOME"] = str(REPO / ".pytest_cache" / "xdg")
    return subprocess.run(
        [PYTHON, str(SCRIPTS / name), *map(str, args)],
        cwd=REPO,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_validator_accepts_plain_csv_and_writes_summary(tmp_path):
    data_dir = write_fixture(tmp_path, gzip_points=False)
    out_dir = tmp_path / "figures"
    result = run_script("validate_plot_data.py", "--data-dir", data_dir, "--out-dir", out_dir)
    assert result.returncode == 0, result.stderr
    summary = json.loads((out_dir / "plot_data_validation_summary.json").read_text())
    assert summary["status"] == "PASS"
    assert summary["category_counts"]["core"] >= 1


def test_validator_accepts_gzip_csv(tmp_path):
    data_dir = write_fixture(tmp_path, gzip_points=True)
    out_dir = tmp_path / "figures"
    result = run_script("validate_plot_data.py", "--data-dir", data_dir, "--out-dir", out_dir)
    assert result.returncode == 0, result.stderr
    assert (out_dir / "plot_data_validation_summary.txt").exists()


def test_validator_rejects_duplicate_inconsistency(tmp_path):
    points = base_points(duplicate_consistent=False)
    data_dir = write_fixture(tmp_path, points=points)
    result = run_script("validate_plot_data.py", "--data-dir", data_dir, "--out-dir", tmp_path / "figures")
    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower()


def test_validator_allows_absent_vsh_vph_when_metadata_marks_absent(tmp_path):
    fields = {"rho": True, "vsv": True, "vsh": False, "vpv": True, "vph": False}
    points = base_points(include_vsh_vph=False)
    data_dir = write_fixture(tmp_path, fields_present=fields, points=points)
    result = run_script("validate_plot_data.py", "--data-dir", data_dir, "--out-dir", tmp_path / "figures")
    assert result.returncode == 0, result.stderr


def test_validator_rejects_present_field_with_missing_columns(tmp_path):
    points = base_points(include_vsh_vph=False)
    data_dir = write_fixture(tmp_path, points=points)
    result = run_script("validate_plot_data.py", "--data-dir", data_dir, "--out-dir", tmp_path / "figures")
    assert result.returncode != 0
    assert "vsh" in result.stderr.lower()


def test_make_all_figures_writes_required_outputs_without_optional_imports(tmp_path):
    data_dir = write_fixture(tmp_path, gzip_points=True)
    out_dir = tmp_path / "figures"
    code = (
        "import json, os, runpy, sys; "
        "sys.argv=['make_all_figures.py','--data-dir',os.environ['DATA_DIR'],"
        "'--out-dir',os.environ['OUT_DIR'],'--formats','png']; "
        "runpy.run_path('scripts/ulvz_mesh_viz/make_all_figures.py', run_name='__main__'); "
        "print(json.dumps({k:(k in sys.modules) for k in ['pyvista','vtk','cartopy','meshio']}))"
    )
    env = os.environ.copy()
    env.update(
        {
            "DATA_DIR": str(data_dir),
            "OUT_DIR": str(out_dir),
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(tmp_path / "mplconfig"),
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
    manifest = json.loads((out_dir / "all_figures_manifest.json").read_text())
    assert len(manifest["figures"]) == 5
    for stem in [
        "01_fixture_domain_ulvz_footprint",
        "02_cmb_ulvz_sampling",
        "03_vertical_ulvz_section",
        "04_material_ratio_validation",
        "05_mesh_sampling_resolution",
    ]:
        assert (out_dir / f"{stem}.png").exists()
        assert (out_dir / f"{stem}_summary.json").exists()
    optional_imports = json.loads(result.stdout.strip().splitlines()[-1])
    assert optional_imports == {"pyvista": False, "vtk": False, "cartopy": False, "meshio": False}


def require_vtk():
    pytest.importorskip("vtk")
    from vtkmodules.vtkCommonDataModel import VTK_HEXAHEDRON
    from vtkmodules.vtkIOXML import vtkXMLPolyDataReader, vtkXMLPUnstructuredGridReader

    return VTK_HEXAHEDRON, vtkXMLPolyDataReader, vtkXMLPUnstructuredGridReader


def test_export_paraview_points_writes_vtp_and_rejects_bad_unique_duplicates(tmp_path):
    _, vtkXMLPPolyDataReader, _ = require_vtk()
    data_dir = write_fixture(tmp_path, gzip_points=True)
    out_dir = tmp_path / "paraview"

    result = run_script("export_paraview_points.py", "--data-dir", data_dir, "--out-dir", out_dir)
    assert result.returncode == 0, result.stderr
    vtp = out_dir / "ulvz_gll_points.vtp"
    sidecar = out_dir / "ulvz_gll_points_metadata.json"
    assert vtp.exists()
    assert sidecar.exists()

    reader = vtkXMLPPolyDataReader()
    reader.SetFileName(str(vtp))
    reader.Update()
    cloud = reader.GetOutput()
    assert cloud.GetNumberOfPoints() == len(base_points())
    assert cloud.GetPointData().HasArray("w_expected")
    assert cloud.GetPointData().HasArray("rho_ratio")
    assert cloud.GetPointData().HasArray("category_code")
    assert cloud.GetPointData().HasArray("x_norm")
    assert cloud.GetPoint(0)[2] == pytest.approx(0.3 * 6371.0)

    bad_root = tmp_path / "bad"
    bad_root.mkdir()
    bad_data = write_fixture(bad_root, points=base_points(duplicate_consistent=False))
    bad_result = run_script(
        "export_paraview_points.py",
        "--data-dir",
        bad_data,
        "--out-dir",
        tmp_path / "bad_out",
        "--unique-points",
    )
    assert bad_result.returncode != 0
    assert "duplicate" in bad_result.stderr.lower()


def paraview_mesh_metadata():
    return {
        "schema_version": "ulvz_paraview_mesh.v1",
        "producer": "pytest",
        "coordinate_units": "km",
        "cell_type": "VTK_HEXAHEDRON",
        "corner_ordering": [
            "ibool(1,1,1)",
            "ibool(NGLLX,1,1)",
            "ibool(NGLLX,NGLLY,1)",
            "ibool(1,NGLLY,1)",
            "ibool(1,1,NGLLZ)",
            "ibool(NGLLX,1,NGLLZ)",
            "ibool(NGLLX,NGLLY,NGLLZ)",
            "ibool(1,NGLLY,NGLLZ)",
        ],
        "node_merge_policy": "rank-local",
        "weld_tolerance": None,
        "number_of_rank_local_nodes": 8,
        "number_of_welded_nodes": None,
        "number_of_exported_cells": 1,
    }


def write_mesh_fixture(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "paraview_mesh_metadata.json").write_text(
        json.dumps(paraview_mesh_metadata(), indent=2), encoding="utf-8"
    )
    nodes = pd.DataFrame(
        [
            (0, 1, 1, 0.0, 0.0, 0.0),
            (0, 2, 2, 1.0, 0.0, 0.0),
            (0, 3, 3, 1.0, 1.0, 0.0),
            (0, 4, 4, 0.0, 1.0, 0.0),
            (0, 5, 5, 0.0, 0.0, 1.0),
            (0, 6, 6, 1.0, 0.0, 1.0),
            (0, 7, 7, 1.0, 1.0, 1.0),
            (0, 8, 8, 0.0, 1.0, 1.0),
        ],
        columns=["rank", "node_id", "iglob", "x_km", "y_km", "z_km"],
    )
    nodes["x_norm"] = nodes["x_km"] / 6371.0
    nodes["y_norm"] = nodes["y_km"] / 6371.0
    nodes["z_norm"] = nodes["z_km"] / 6371.0
    nodes["radius_km"] = (nodes["x_km"] ** 2 + nodes["y_km"] ** 2 + nodes["z_km"] ** 2) ** 0.5
    nodes["height_above_cmb_km"] = nodes["radius_km"] - 3480.0
    nodes["latitude_deg"] = 0.0
    nodes["longitude_deg"] = 0.0
    cells = pd.DataFrame(
        [
            {
                "rank": 0,
                "cell_id": 1,
                "ispec": 1,
                "node0": 1,
                "node1": 2,
                "node2": 3,
                "node3": 4,
                "node4": 5,
                "node5": 6,
                "node6": 7,
                "node7": 8,
                "cell_center_radius_km": 0.866025403784,
                "cell_center_height_above_cmb_km": -3479.133974596216,
                "cell_w_expected_mean": 1.0,
                "cell_w_expected_min": 1.0,
                "cell_w_expected_max": 1.0,
                "cell_has_outside": 0,
                "cell_has_taper": 0,
                "cell_has_core": 1,
                "cell_category_code": 2,
                "material_changed_fraction": 1.0,
                "rho_ratio_mean": 1.05,
                "rho_ratio_min": 1.05,
                "rho_ratio_max": 1.05,
                "vsv_ratio_mean": 0.8,
                "vsv_ratio_min": 0.8,
                "vsv_ratio_max": 0.8,
                "vsh_ratio_mean": 0.8,
                "vsh_ratio_min": 0.8,
                "vsh_ratio_max": 0.8,
                "vpv_ratio_mean": 0.9,
                "vpv_ratio_min": 0.9,
                "vpv_ratio_max": 0.9,
                "vph_ratio_mean": 0.9,
                "vph_ratio_min": 0.9,
                "vph_ratio_max": 0.9,
            }
        ]
    )
    nodes.to_csv(reports / "paraview_mesh_nodes_rank000000.csv.gz", index=False)
    cells.to_csv(reports / "paraview_mesh_cells_rank000000.csv.gz", index=False)
    return reports


def test_export_paraview_mesh_writes_pvtu_unit_cube_with_positive_hex_volume(tmp_path):
    VTK_HEXAHEDRON, _, vtkXMLPUnstructuredGridReader = require_vtk()
    data_dir = write_mesh_fixture(tmp_path)
    out_dir = tmp_path / "paraview"

    result = run_script("export_paraview_mesh.py", "--data-dir", data_dir, "--out-dir", out_dir)
    assert result.returncode == 0, result.stderr
    pvtu = out_dir / "ulvz_mesh.pvtu"
    sidecar = out_dir / "ulvz_mesh_metadata.json"
    assert pvtu.exists()
    assert sidecar.exists()

    reader = vtkXMLPUnstructuredGridReader()
    reader.SetFileName(str(pvtu))
    reader.Update()
    grid = reader.GetOutput()
    assert grid.GetNumberOfPoints() == 8
    assert grid.GetNumberOfCells() == 1
    assert grid.GetCellType(0) == VTK_HEXAHEDRON
    assert grid.GetCellData().HasArray("cell_w_expected_mean")
    assert grid.GetPointData().HasArray("iglob")

    cell = grid.GetCell(0)
    p0 = grid.GetPoint(cell.GetPointId(0))
    p1 = grid.GetPoint(cell.GetPointId(1))
    p3 = grid.GetPoint(cell.GetPointId(3))
    p4 = grid.GetPoint(cell.GetPointId(4))
    signed_volume = (
        (p1[0] - p0[0]) * ((p3[1] - p0[1]) * (p4[2] - p0[2]))
    )
    assert signed_volume == pytest.approx(1.0)


def test_export_paraview_mesh_writes_coordinate_welded_single_vtu(tmp_path):
    VTK_HEXAHEDRON, _, _ = require_vtk()
    from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridReader

    data_dir = write_mesh_fixture(tmp_path)
    out_dir = tmp_path / "paraview_welded"

    result = run_script(
        "export_paraview_mesh.py",
        "--data-dir",
        data_dir,
        "--out-dir",
        out_dir,
        "--weld-coordinates",
        "--weld-tolerance",
        "1.0e-6",
    )
    assert result.returncode == 0, result.stderr
    vtu = out_dir / "ulvz_mesh_welded.vtu"
    metadata_path = out_dir / "ulvz_mesh_metadata.json"
    assert vtu.exists()
    metadata_payload = json.loads(metadata_path.read_text())
    assert metadata_payload["node_merge_policy"] == "coordinate-welded"
    assert metadata_payload["number_of_welded_nodes"] == 8

    reader = vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(vtu))
    reader.Update()
    grid = reader.GetOutput()
    assert grid.GetNumberOfPoints() == 8
    assert grid.GetNumberOfCells() == 1
    assert grid.GetCellType(0) == VTK_HEXAHEDRON


@pytest.mark.parametrize(
    "script",
    [
        "validate_plot_data.py",
        "plot_fixture_overview.py",
        "plot_cmb_sampling.py",
        "plot_vertical_section.py",
        "plot_material_response.py",
        "plot_mesh_resolution.py",
        "make_all_figures.py",
        "view_mesh_3d.py",
        "export_paraview_points.py",
        "export_paraview_mesh.py",
    ],
)
def test_scripts_support_help(script):
    result = run_script(script, "--help")
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
