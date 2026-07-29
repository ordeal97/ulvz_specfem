"""Optional deterministic comparison with the independent SPECFEM utility source."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from ulvz_stf_convolution.convolution import convolve_waveform
from ulvz_stf_convolution.models import Waveform
from ulvz_stf_convolution.stf import fortran_compatible_stf


def _specfem_root() -> Path | None:
    configured = os.environ.get("SPECFEM3D_GLOBE_ROOT")
    if configured:
        return Path(configured)
    candidate = Path(__file__).resolve().parents[4] / "specfem3d_globe"
    return candidate if candidate.exists() else None


@pytest.mark.parametrize("kind", ["gaussian", "triangle"])
def test_matches_current_fortran_utility(tmp_path, kind: str) -> None:
    root = _specfem_root()
    compiler = shutil.which("gfortran")
    if root is None or compiler is None:
        pytest.skip("SPECFEM source root or gfortran is unavailable")
    source = root / "src" / "auxiliaries" / "convolve_source_timefunction.f90"
    shared = root / "src" / "shared" / "shared_par.f90"
    setup = root / "setup"
    if not source.is_file() or not shared.is_file() or not setup.is_dir():
        pytest.skip("current SPECFEM Fortran utility source is unavailable")
    executable = tmp_path / "convolve_source_timefunction"
    shared_object = tmp_path / "shared_par.o"
    shared_build = subprocess.run(
        [compiler, "-I", str(setup), "-J", str(tmp_path), "-c", "-o", str(shared_object), str(shared)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    if shared_build.returncode:
        pytest.skip(f"reference constants module did not compile here: {shared_build.stderr[-300:]}")
    build = subprocess.run(
        [compiler, "-I", str(setup), "-I", str(tmp_path), "-J", str(tmp_path), "-o", str(executable), str(source), str(shared_object)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    if build.returncode:
        pytest.skip(f"reference Fortran source did not compile here: {build.stderr[-300:]}")

    dt, half_duration = 0.2, 0.7
    data = np.cos(np.arange(24) * 0.31)
    waveform_text = "\n".join(
        f"{time:.17g} {value:.17g}" for time, value in zip(np.arange(data.size) * dt, data, strict=True)
    ) + "\n"
    triangle_flag = ".true." if kind == "triangle" else ".false."
    (tmp_path / "input_convolve_code.txt").write_text(
        f"{data.size}\n{half_duration}\n{triangle_flag}\n", encoding="utf-8"
    )
    run = subprocess.run(
        [str(executable)],
        cwd=tmp_path,
        input=waveform_text,
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr + run.stdout
    reference = np.loadtxt(run.stdout.splitlines())
    python_result = convolve_waveform(
        Waveform(np.arange(data.size) * dt, data, dt, "ascii"),
        fortran_compatible_stf(kind, half_duration, dt),
        mode="fortran",
    )
    np.testing.assert_allclose(python_result.waveform.times, reference[:, 0], rtol=0.0, atol=2e-7)
    np.testing.assert_allclose(python_result.waveform.amplitudes, reference[:, 1], rtol=2e-6, atol=2e-7)
