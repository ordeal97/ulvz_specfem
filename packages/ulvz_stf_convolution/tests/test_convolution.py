from __future__ import annotations

import numpy as np
import pytest

from ulvz_stf_convolution.convolution import convolve_waveform
from ulvz_stf_convolution.models import SourceTimeFunction, Waveform
from ulvz_stf_convolution.stf import builtin_stf


def _waveform(values: list[float]) -> Waveform:
    return Waveform(np.arange(len(values), dtype=float), np.array(values, dtype=float), 1.0, "ascii")


def _stf(times: list[float], values: list[float]) -> SourceTimeFunction:
    return SourceTimeFunction(np.array(times, dtype=float), np.array(values, dtype=float), "numeric", 1.0, 1.0)


def test_full_and_same_respect_stf_time_coordinate() -> None:
    waveform = _waveform([1.0, 2.0, 3.0])
    causal = _stf([0.0, 1.0], [1.0, 1.0])
    full = convolve_waveform(waveform, causal, mode="full", method="direct")
    same = convolve_waveform(waveform, causal, mode="same", method="direct")
    assert full.waveform.times.tolist() == pytest.approx([0.0, 1.0, 2.0, 3.0])
    assert full.waveform.amplitudes.tolist() == pytest.approx([1.0, 3.0, 5.0, 3.0])
    assert same.waveform.amplitudes.tolist() == pytest.approx([1.0, 3.0, 5.0])

    acausal = _stf([-1.0, 0.0], [1.0, 1.0])
    acausal_same = convolve_waveform(waveform, acausal, mode="same", method="direct")
    assert acausal_same.waveform.amplitudes.tolist() == pytest.approx([3.0, 5.0, 3.0])


def test_dt_is_applied_exactly_once() -> None:
    waveform = Waveform(np.array([0.0, 0.25]), np.array([1.0, 0.0]), 0.25, "ascii")
    stf = SourceTimeFunction(np.array([0.0, 0.25]), np.array([4.0, 0.0]), "numeric", 1.0, 1.0)
    result = convolve_waveform(waveform, stf, mode="full", method="direct")
    assert result.waveform.amplitudes.tolist() == pytest.approx([1.0, 0.0, 0.0])


def test_direct_fft_and_auto_agree() -> None:
    waveform = _waveform(list(np.sin(np.arange(37))))
    stf = builtin_stf("gaussian", 2.0, 1.0)
    direct = convolve_waveform(waveform, stf, mode="full", method="direct")
    fft = convolve_waveform(waveform, stf, mode="full", method="fft")
    auto = convolve_waveform(waveform, stf, mode="full", method="auto")
    np.testing.assert_allclose(direct.waveform.amplitudes, fft.waveform.amplitudes, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(direct.waveform.amplitudes, auto.waveform.amplitudes, rtol=1e-12, atol=1e-12)
    assert auto.method in {"direct", "fft"}


def test_fortran_mode_has_legacy_output_trimming() -> None:
    waveform = _waveform(list(range(20)))
    stf = builtin_stf("triangle", 2.0, 1.0, modern=False)
    result = convolve_waveform(waveform, stf, mode="fortran")
    assert result.waveform.amplitudes.size == 17  # npts - (ceil(H/dt) + 1)
    assert result.waveform.times[0] == pytest.approx(0.0)


def test_zero_and_short_waveforms_are_linear_and_finite() -> None:
    stf = _stf([0.0, 1.0], [1.0, 1.0])
    zero = convolve_waveform(_waveform([0.0, 0.0]), stf, mode="full")
    short = convolve_waveform(_waveform([1.0, -1.0]), stf, mode="full")
    assert zero.waveform.amplitudes.tolist() == pytest.approx([0.0, 0.0, 0.0])
    assert short.waveform.amplitudes.tolist() == pytest.approx([1.0, 0.0, -1.0])
