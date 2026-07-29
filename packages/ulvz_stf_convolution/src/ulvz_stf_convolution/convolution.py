"""Linear, dt-aware waveform convolution."""

from __future__ import annotations

import numpy as np
from scipy import signal

from .errors import StfConvolutionError
from .models import ConvolutionResult, SourceTimeFunction, Waveform


def _full_convolution(data: np.ndarray, kernel: np.ndarray, dt: float, method: str) -> tuple[np.ndarray, str]:
    if method not in {"auto", "direct", "fft"}:
        raise StfConvolutionError("method must be auto, direct, or fft")
    selected = signal.choose_conv_method(data, kernel, mode="full") if method == "auto" else method
    return signal.convolve(data, kernel, mode="full", method=selected) * dt, selected


def _fortran_convolution(waveform: Waveform, stf: SourceTimeFunction) -> Waveform:
    data, kernel, count = waveform.amplitudes, stf.amplitudes, int(stf.metadata["fortran_sample_count"])
    if len(kernel) != 2 * count + 1:
        raise StfConvolutionError("Fortran mode requires an unshifted builtin STF")
    npts = len(data)
    output_count = npts - (count + 1)
    if output_count < 1:
        raise StfConvolutionError("waveform is too short for Fortran-compatible output trimming")
    output = np.zeros(output_count, dtype=float)
    for i_one in range(1, output_count + 1):
        total = 0.0
        for j in range(-count, count + 1):
            if i_one > j and i_one - j <= npts:
                total += data[i_one - j - 1] * kernel[j + count] * waveform.dt
        output[i_one - 1] = total
    # The original program writes both columns through sngl().
    return Waveform(
        times=waveform.times[:output_count].astype(np.float32),
        amplitudes=output.astype(np.float32),
        dt=waveform.dt,
        format=waveform.format,
        path=waveform.path,
        sac_trace=waveform.sac_trace,
        sac_reference_time=waveform.sac_reference_time,
    )


def convolve_waveform(
    waveform: Waveform,
    stf: SourceTimeFunction,
    *,
    mode: str = "same",
    method: str = "auto",
) -> ConvolutionResult:
    """Convolve a uniformly sampled waveform with a waveform-grid STF."""
    if mode == "fortran":
        if stf.kind not in {"gaussian", "triangle"}:
            raise StfConvolutionError("Fortran mode supports builtin gaussian or triangle STF only")
        result = _fortran_convolution(waveform, stf)
        return ConvolutionResult(result, "fortran", "direct", stf, ())
    if mode not in {"same", "full"}:
        raise StfConvolutionError("mode must be same, full, or fortran")
    if len(waveform.amplitudes) < 1:
        raise StfConvolutionError("waveform cannot be empty")
    full, selected = _full_convolution(waveform.amplitudes, stf.amplitudes, waveform.dt, method)
    full_times = waveform.times[0] + stf.times[0] + np.arange(len(full), dtype=float) * waveform.dt
    if mode == "full":
        output_times, output = full_times, full
    else:
        j_min = int(round(stf.times[0] / waveform.dt))
        indices = np.arange(len(waveform.amplitudes)) - j_min
        output = np.zeros(len(indices), dtype=float)
        valid = (indices >= 0) & (indices < len(full))
        output[valid] = full[indices[valid]]
        output_times = waveform.times.copy()
    result = Waveform(
        output_times,
        output,
        waveform.dt,
        waveform.format,
        waveform.path,
        waveform.sac_trace,
        waveform.sac_reference_time,
    )
    return ConvolutionResult(result, mode, selected, stf, tuple(stf.metadata.get("warnings", [])))
