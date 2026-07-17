from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO / "packages" / "ulvz_model_postprocess"
PACKAGE_SRC = PACKAGE_ROOT / "src"
TASK4_EXTRACTOR = REPO / "specfem3d_globe" / "bin" / "xulvz_model_extract"
PYTHON = os.environ.get(
    "ULVZ_TEST_PYTHON",
    sys.executable,
)
if not Path(PYTHON).exists():
    PYTHON = sys.executable


def run_standalone(*args, cwd=None, env=None):
    full_env = os.environ.copy()
    full_env.setdefault("MPLBACKEND", "Agg")
    full_env.setdefault("MPLCONFIGDIR", str(Path(cwd or REPO) / ".mpl"))
    full_env.setdefault("XDG_CACHE_HOME", str(Path(cwd or REPO) / ".xdg"))
    full_env["PYTHONPATH"] = str(PACKAGE_SRC)
    if env:
        full_env.update(env)
    return subprocess.run(
        [PYTHON, "-m", "ulvz_model_postprocess", *map(str, args)],
        cwd=cwd or REPO,
        env=full_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_old(*args):
    full_env = os.environ.copy()
    full_env.setdefault("MPLBACKEND", "Agg")
    full_env.setdefault("MPLCONFIGDIR", str(REPO / ".pytest_cache" / "standalone_old_mpl"))
    full_env.setdefault("XDG_CACHE_HOME", str(REPO / ".pytest_cache" / "standalone_old_xdg"))
    return subprocess.run(
        [PYTHON, "-m", "scripts.ulvz_model_postprocess", *map(str, args)],
        cwd=REPO,
        env=full_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def make_databases_mpi(root: Path) -> Path:
    db = root / "DATABASES_MPI"
    db.mkdir()
    (db / "proc000000_reg1_solver_data.bin").write_bytes(b"fixture")
    return db


def make_fake_extractor(root: Path) -> Path:
    extractor = root / "xulvz_model_extract"
    extractor.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, pathlib, sys",
                "if len(sys.argv) > 1 and sys.argv[1] == '--help':",
                "    print('Usage: xulvz_model_extract --inspect DATABASES_MPI OUT_DIR')",
                "    raise SystemExit(2)",
                "if len(sys.argv) >= 4 and sys.argv[1] == '--inspect':",
                "    out = pathlib.Path(sys.argv[3])",
                "    out.mkdir(parents=True, exist_ok=True)",
                "    (out / 'extractor_layout_manifest.json').write_text(json.dumps({'schema_version': 'fake'}))",
                "    raise SystemExit(0)",
                "print('unsupported fake extractor invocation', file=sys.stderr)",
                "raise SystemExit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    extractor.chmod(extractor.stat().st_mode | stat.S_IXUSR)
    return extractor


def import_standalone():
    sys.path.insert(0, str(PACKAGE_SRC))
    import ulvz_model_postprocess

    return ulvz_model_postprocess


def write_product(root: Path, *, label="model", selection="same", scale=1.0) -> Path:
    sys.path.insert(0, str(PACKAGE_SRC))
    from ulvz_model_postprocess.rank_store import RankArrays, write_model_product

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
        extraction_mode="selected",
        ranks=[arrays],
        roi={"kind": "none"},
        sampling_rule={"kind": "none"},
        selection_fingerprint=selection,
        provenance={"producer": "pytest"},
    )


def test_import_module_entrypoint_and_script_metadata():
    package = import_standalone()
    assert package.SCHEMA_VERSION == "ulvz_model_postprocess.v1"

    result = run_standalone("--help")
    assert result.returncode == 0, result.stderr
    assert "validate" in result.stdout
    assert "paraview" in result.stdout

    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["scripts"]["ulvz-model-postprocess"] == "ulvz_model_postprocess.cli:main"


def test_old_in_repository_entrypoint_still_works():
    result = run_old("--help")
    assert result.returncode == 0, result.stderr
    assert "validate" in result.stdout


def test_validate_requires_explicit_extractor_and_is_cwd_independent(tmp_path):
    db = make_databases_mpi(tmp_path)
    missing = run_standalone(
        "validate",
        "--model",
        f"ulvz={db}",
        "--out-dir",
        tmp_path / "missing",
        cwd=tmp_path,
    )
    assert missing.returncode != 0
    assert "--extractor" in missing.stderr

    extractor = make_fake_extractor(tmp_path)
    ok = run_standalone(
        "validate",
        "--model",
        f"ulvz={db}",
        "--extractor",
        extractor,
        "--out-dir",
        tmp_path / "validate_out",
        cwd=tmp_path,
    )
    assert ok.returncode == 0, ok.stderr
    assert (tmp_path / "validate_out" / "input_validation.json").exists()
    assert (tmp_path / "validate_out" / "extractor_inspect" / "extractor_layout_manifest.json").exists()
    assert not (tmp_path / "input_validation.json").exists()
    assert not (tmp_path / "model_manifest.json").exists()


def test_extract_summary_and_physical_modes_require_explicit_extractor(tmp_path):
    db = make_databases_mpi(tmp_path)
    summary = run_standalone(
        "extract",
        "--model",
        f"ulvz={db}",
        "--out-dir",
        tmp_path / "summary",
        cwd=tmp_path,
    )
    assert summary.returncode != 0
    assert "--extractor" in summary.stderr

    selected = run_standalone(
        "extract",
        "--model",
        f"ulvz={db}",
        "--extract-mode",
        "selected",
        "--out-dir",
        tmp_path / "selected",
        cwd=tmp_path,
    )
    assert selected.returncode != 0
    assert "--extractor" in selected.stderr


def test_compare_plot_and_paraview_reject_raw_databases_mpi(tmp_path):
    db = make_databases_mpi(tmp_path)
    manifest = write_product(tmp_path / "product")

    compare = run_standalone(
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
    assert "raw databases_mpi" in compare.stderr.lower()

    plot = run_standalone(
        "plot",
        "--input",
        db,
        "--field",
        "vs",
        "--out-dir",
        tmp_path / "figures",
    )
    assert plot.returncode != 0
    assert "raw databases_mpi" in plot.stderr.lower()

    paraview = run_standalone(
        "paraview",
        "--input",
        db,
        "--out-dir",
        tmp_path / "paraview",
    )
    assert paraview.returncode != 0
    assert "raw databases_mpi" in paraview.stderr.lower()


def test_compare_plot_paraview_synthetic_products_from_standalone_package(tmp_path):
    pytest.importorskip("vtkmodules", reason="VTK is required for ParaView export validation")
    ref = write_product(tmp_path / "ref", label="reference", selection="selection-a")
    target = write_product(tmp_path / "target", label="ulvz", selection="selection-a", scale=0.9)

    compare = run_standalone(
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
    comparison_manifest = tmp_path / "comparison" / "ulvz_over_reference_manifest.json"
    payload = json.loads(comparison_manifest.read_text(encoding="utf-8"))
    assert payload["orientation"]["ratio"] == "target / reference"
    assert payload["orientation"]["difference"] == "target - reference"

    plot = run_standalone(
        "plot",
        "--input",
        target,
        "--field",
        "vs",
        "--kind",
        "histogram",
        "--out-dir",
        tmp_path / "figures",
    )
    assert plot.returncode == 0, plot.stderr
    assert (tmp_path / "figures" / "histogram_vs.png").exists()

    paraview = run_standalone(
        "paraview",
        "--input",
        target,
        "--paraview-kind",
        "both",
        "--out-dir",
        tmp_path / "paraview",
    )
    assert paraview.returncode == 0, paraview.stderr
    assert (tmp_path / "paraview" / "model_points.pvtp").exists()
    assert (tmp_path / "paraview" / "model_linear_mesh.pvtu").exists()


def test_installer_dry_run_is_non_mutating_and_missing_rules_is_reported(tmp_path):
    specfem = tmp_path / "specfem3d_globe"
    aux = specfem / "src" / "auxiliaries"
    aux.mkdir(parents=True)
    rules = aux / "rules.mk"
    original_rules = "\n".join(
        [
            "auxiliaries_TARGETS = \\",
            "\t$E/xextract_database \\",
            "\t$E/xwrite_profile \\",
            "\t$(EMPTY_MACRO)",
            "",
            "auxiliaries_OBJECTS = \\",
            "\t$(xextract_database_OBJECTS) \\",
            "\t$(xwrite_profile_OBJECTS) \\",
            "\t$(EMPTY_MACRO)",
            "",
            "${E}/xextract_database: $(xextract_database_OBJECTS) $(xextract_database_SHARED_OBJECTS)",
            "\t${MPIFCCOMPILE_CHECK} -o $@ $+ $(MPILIBS)",
            "",
            "xwrite_profile_OBJECTS = \\",
            "\t$O/write_profile.aux.o \\",
            "\t$(EMPTY_MACRO)",
            "",
        ]
    )
    rules.write_text(original_rules, encoding="utf-8")
    installer = PACKAGE_ROOT / "specfem_extension" / "install_extractor.py"

    dry_run = subprocess.run(
        [PYTHON, str(installer), "--specfem-root", specfem, "--dry-run"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "DRY RUN" in dry_run.stdout
    assert rules.read_text(encoding="utf-8") == original_rules
    assert not (aux / "ulvz_model_extract.f90").exists()

    missing_root = tmp_path / "missing_rules"
    missing_root.mkdir()
    missing = subprocess.run(
        [PYTHON, str(installer), "--specfem-root", missing_root, "--dry-run"],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert missing.returncode != 0
    assert "rules.mk" in missing.stderr


@pytest.mark.skipif(not TASK4_EXTRACTOR.exists(), reason="verified Task 4C extractor is not available")
def test_verified_fortran_extractor_help_is_safe_usage_diagnostic():
    result = subprocess.run(
        [str(TASK4_EXTRACTOR), "--help"],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode in {0, 2}
    assert "Usage:" in result.stdout
