from __future__ import annotations

import numpy as np
import pytest

from ulvz_stf_convolution.errors import StfConvolutionError
from ulvz_stf_convolution.stf import builtin_stf, read_numeric_stf, resample_stf


def test_builtin_gaussian_modern_area_and_fortran_kernel_are_distinct() -> None:
    modern = builtin_stf("gaussian", 1.0, 0.2, modern=True)
    legacy = builtin_stf("gaussian", 1.0, 0.2, modern=False)
    assert modern.metadata["truncation"] == "plus_minus_1.5H"
    assert np.trapezoid(modern.amplitudes, modern.times) == pytest.approx(1.0)
    assert np.trapezoid(legacy.amplitudes, legacy.times) != pytest.approx(1.0)
    assert legacy.amplitudes[len(legacy.amplitudes) // 2] == pytest.approx(1.628 / np.sqrt(np.pi))


def test_builtin_triangle_matches_fortran_discrete_definition() -> None:
    stf = builtin_stf("triangle", 1.0, 0.3, modern=False)
    assert stf.times.tolist() == pytest.approx([-1.2, -0.9, -0.6, -0.3, 0.0, 0.3, 0.6, 0.9, 1.2])
    assert stf.amplitudes.tolist() == pytest.approx([0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0])


def test_numeric_nonuniform_times_normalize_and_grid_origin(tmp_path) -> None:
    path = tmp_path / "source.txt"
    path.write_text("-0.09 0\n0.00 2\n0.07 1\n0.16 0\n", encoding="utf-8")
    raw = read_numeric_stf(path)
    sampled = resample_stf(raw, 0.1)
    assert sampled.times.tolist() == pytest.approx([-0.1, 0.0, 0.1, 0.2])
    assert np.trapezoid(sampled.amplitudes, sampled.times) == pytest.approx(1.0)
    assert sampled.metadata["resampling_method"].startswith("PCHIP")


def test_numeric_coarse_and_large_gap_are_explicit(tmp_path) -> None:
    coarse = tmp_path / "coarse.txt"
    coarse.write_text("0 0\n0.25 1\n0.5 0\n", encoding="utf-8")
    stf = read_numeric_stf(coarse)
    with pytest.raises(StfConvolutionError, match="coarser"):
        resample_stf(stf, 0.1)
    allowed = resample_stf(stf, 0.1, allow_coarse_stf=True)
    assert allowed.metadata["warnings"]
    large = tmp_path / "large-gap.txt"
    large.write_text("0 0\n0.5 1\n", encoding="utf-8")
    with pytest.raises(StfConvolutionError, match="unacceptable gap"):
        resample_stf(read_numeric_stf(large), 0.1, allow_coarse_stf=True)


def test_numeric_rejects_zero_integral(tmp_path) -> None:
    path = tmp_path / "zero.txt"
    path.write_text("-1 -1\n0 0\n1 1\n", encoding="utf-8")
    with pytest.raises(StfConvolutionError, match="zero or too small"):
        read_numeric_stf(path)
