"""Source-time-function construction, validation, normalization, and resampling."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy import interpolate, signal

from .errors import StfConvolutionError
from .models import SourceTimeFunction

SOURCE_DECAY_MIMIC_TRIANGLE = 1.628
_ZERO_INTEGRAL_TOL = 1.0e-12


def _integral(times: np.ndarray, amplitudes: np.ndarray) -> float:
    return float(np.trapezoid(amplitudes, x=times))


def _require_finite_pair(times: np.ndarray, amplitudes: np.ndarray, label: str) -> None:
    if times.ndim != 1 or amplitudes.ndim != 1 or len(times) != len(amplitudes):
        raise StfConvolutionError(f"{label} must contain matching one-dimensional time and amplitude arrays")
    if len(times) < 2:
        raise StfConvolutionError(f"{label} must contain at least two samples")
    if not np.isfinite(times).all() or not np.isfinite(amplitudes).all():
        raise StfConvolutionError(f"{label} time and amplitude values must be finite")
    if not np.all(np.diff(times) > 0.0):
        raise StfConvolutionError(f"{label} time values must be strictly increasing")


def _normalize(times: np.ndarray, amplitudes: np.ndarray, *, required: bool) -> tuple[np.ndarray, float, float]:
    before = _integral(times, amplitudes)
    scale = max(1.0, float(np.max(np.abs(amplitudes))), float(times[-1] - times[0]))
    if not np.isfinite(before) or abs(before) <= _ZERO_INTEGRAL_TOL * scale:
        raise StfConvolutionError("STF integral is zero or too small for stable normalization")
    if not required:
        return amplitudes.copy(), before, before
    normalized = amplitudes / before
    return normalized, before, _integral(times, normalized)


def read_numeric_stf(path: str | Path, *, normalize: bool = True) -> SourceTimeFunction:
    """Read a two-column numeric moment-rate function using its actual time coordinates."""
    source = Path(path)
    try:
        table = np.loadtxt(source, dtype=float, ndmin=2)
    except (OSError, ValueError) as exc:
        raise StfConvolutionError(f"could not read numeric STF {source}: {exc}") from exc
    if table.ndim != 2 or table.shape[1] != 2:
        raise StfConvolutionError("numeric STF must contain exactly two columns: time_seconds amplitude")
    times, amplitudes = table[:, 0], table[:, 1]
    _require_finite_pair(times, amplitudes, "numeric STF")
    values, before, after = _normalize(times, amplitudes, required=normalize)
    gaps = np.diff(times)
    return SourceTimeFunction(
        times=times,
        amplitudes=values,
        kind="numeric",
        original_integral=before,
        normalized_integral=after,
        metadata={
            "path": str(source),
            "normalize_requested": normalize,
            "original_dt_min": float(np.min(gaps)),
            "original_dt_median": float(np.median(gaps)),
            "original_dt_max": float(np.max(gaps)),
        },
    )


def builtin_stf(kind: str, half_duration: float, dt: float, *, modern: bool = True) -> SourceTimeFunction:
    """Construct either builtin STF exactly on the waveform's time-grid basis."""
    if not np.isfinite(half_duration) or half_duration <= 0.0:
        raise StfConvolutionError("half duration must be finite and positive")
    if not np.isfinite(dt) or dt <= 0.0:
        raise StfConvolutionError("waveform dt must be finite and positive")
    normalized_kind = kind.lower()
    if normalized_kind == "gaussian":
        count = int(np.ceil(1.5 * half_duration / dt))
        times = np.arange(-count, count + 1, dtype=float) * dt
        alpha = SOURCE_DECAY_MIMIC_TRIANGLE / half_duration
        amplitudes = alpha * np.exp(-(alpha * times) ** 2) / np.sqrt(np.pi)
        if modern:
            values, before, after = _normalize(times, amplitudes, required=True)
        else:
            values, before, after = _normalize(times, amplitudes, required=False)
        metadata = {"half_duration": half_duration, "fortran_sample_count": count, "truncation": "plus_minus_1.5H"}
    elif normalized_kind == "triangle":
        count = int(np.ceil(half_duration / dt))
        times = np.arange(-count, count + 1, dtype=float) * dt
        height = 1.0 / half_duration
        extent = count * dt
        amplitudes = np.zeros_like(times)
        mask = np.abs(times) <= half_duration
        negative = mask & (times < 0.0)
        positive = mask & ~negative
        amplitudes[negative] = (times[negative] + extent) / extent * height
        amplitudes[positive] = (extent - times[positive]) / extent * height
        values, before, after = _normalize(times, amplitudes, required=False)
        metadata = {"half_duration": half_duration, "fortran_sample_count": count, "truncation": "Fortran_abs_time_le_H"}
    else:
        raise StfConvolutionError("builtin STF kind must be gaussian or triangle")
    return SourceTimeFunction(times, values, normalized_kind, before, after, metadata)


def _sample_to_grid(stf: SourceTimeFunction, dt: float, shift: float) -> tuple[np.ndarray, np.ndarray, dict[str, float], list[str]]:
    gaps = np.diff(stf.times)
    max_gap = float(np.max(gaps))
    if max_gap > 4.0 * dt:
        raise StfConvolutionError(f"numeric STF has an unacceptable gap ({max_gap:g} s > 4 * waveform dt)")
    start = float(stf.times[0] + shift)
    end = float(stf.times[-1] + shift)
    j_min, j_max = int(np.floor(start / dt)), int(np.ceil(end / dt))
    target_times = np.arange(j_min, j_max + 1, dtype=float) * dt
    interpolator = interpolate.PchipInterpolator(stf.times, stf.amplitudes, extrapolate=False)
    values = np.nan_to_num(interpolator(target_times - shift), nan=0.0)
    metadata = {
        "original_dt_min": float(np.min(gaps)),
        "original_dt_median": float(np.median(gaps)),
        "original_dt_max": max_gap,
        "target_dt": dt,
        "target_nyquist_hz": 0.5 / dt,
        "time_shift_seconds": shift,
    }
    return target_times, values, metadata, []


def resample_stf(
    stf: SourceTimeFunction,
    waveform_dt: float,
    *,
    time_shift: float = 0.0,
    allow_coarse_stf: bool = False,
    normalize: bool | None = None,
) -> SourceTimeFunction:
    """Resample an STF on the coordinate-aware waveform grid, preserving time zero."""
    if not np.isfinite(waveform_dt) or waveform_dt <= 0.0:
        raise StfConvolutionError("waveform dt must be finite and positive")
    if not np.isfinite(time_shift):
        raise StfConvolutionError("STF time shift must be finite")
    if stf.kind != "numeric":
        # Builtins are already on the waveform grid.  A non-integer shift is still interpolated.
        if abs(time_shift) < 1.0e-15:
            return stf
    gaps = np.diff(stf.times)
    max_gap = float(np.max(gaps))
    warnings: list[str] = []
    if max_gap > 4.0 * waveform_dt:
        raise StfConvolutionError(f"STF has an unacceptable gap ({max_gap:g} s > 4 * waveform dt)")
    if max_gap > waveform_dt:
        if not allow_coarse_stf:
            raise StfConvolutionError(
                "STF is coarser than waveform dt; use --allow-coarse-stf only after accepting lost source bandwidth"
            )
        warnings.append("coarse_STF_upsampling_allowed: interpolation cannot recover unsampled high-frequency content")

    target_times, target_values, metadata, _ = _sample_to_grid(stf, waveform_dt, time_shift)
    # A finer source is reconstructed on a t=0-aligned intermediate grid and FIR low-pass filtered before decimation.
    min_gap = float(np.min(gaps))
    decimation = max(1, int(np.ceil(waveform_dt / min_gap)))
    if max_gap <= waveform_dt and decimation > 1:
        fine_dt = waveform_dt / decimation
        j_min = int(round(target_times[0] / waveform_dt))
        j_max = int(round(target_times[-1] / waveform_dt))
        fine_times = np.arange(j_min * decimation, j_max * decimation + 1, dtype=float) * fine_dt
        interpolator = interpolate.PchipInterpolator(stf.times, stf.amplitudes, extrapolate=False)
        fine_values = np.nan_to_num(interpolator(fine_times - time_shift), nan=0.0)
        filtered = signal.resample_poly(fine_values, up=1, down=decimation, padtype="constant")
        target_values = filtered[: len(target_times)]
        metadata["resampling_method"] = "PCHIP_then_resample_poly_FIR"
        metadata["anti_alias_decimation"] = decimation
    else:
        metadata["resampling_method"] = "PCHIP_interpolation"
        metadata["anti_alias_decimation"] = 1

    should_normalize = stf.kind == "numeric" if normalize is None else normalize
    values, before, after = _normalize(target_times, target_values, required=should_normalize)
    metadata["resampled_integral_before"] = before
    metadata["resampled_integral_after"] = after
    metadata["warnings"] = warnings
    return SourceTimeFunction(target_times, values, stf.kind, stf.original_integral, after, {**stf.metadata, **metadata})


def fortran_compatible_stf(kind: str, half_duration: float, dt: float) -> SourceTimeFunction:
    """Return the unnormalized finite kernel used by the current Fortran utility."""
    return builtin_stf(kind, half_duration, dt, modern=False)
