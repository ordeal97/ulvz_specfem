"""ASCII and ObsPy SAC waveform I/O."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .errors import StfConvolutionError
from .models import Waveform


def infer_dt(times: np.ndarray) -> float:
    if len(times) < 2:
        raise StfConvolutionError("waveform must contain at least two samples")
    if not np.isfinite(times).all() or not np.all(np.diff(times) > 0.0):
        raise StfConvolutionError("waveform times must be finite and strictly increasing")
    steps = np.diff(times)
    dt = float(np.median(steps))
    tolerance = max(1.0e-10, abs(dt) * 1.0e-6)
    if not np.all(np.abs(steps - dt) <= tolerance):
        raise StfConvolutionError("waveform time sampling is not sufficiently uniform for discrete convolution")
    return dt


def _resolve_format(path: Path, requested: str) -> str:
    if requested not in {"auto", "ascii", "sac"}:
        raise StfConvolutionError("format must be auto, ascii, or sac")
    if requested != "auto":
        return requested
    return "sac" if path.suffix.lower() == ".sac" else "ascii"


def _obspy():
    try:
        import obspy
    except ImportError as exc:
        raise StfConvolutionError("SAC support requires ObsPy; install ulvz-stf-convolution[sac]") from exc
    return obspy


def read_waveform(path: str | Path, *, format: str = "auto") -> Waveform:
    source = Path(path)
    selected = _resolve_format(source, format)
    if selected == "ascii":
        try:
            table = np.loadtxt(source, dtype=float, ndmin=2)
        except (OSError, ValueError) as exc:
            raise StfConvolutionError(f"could not read ASCII waveform {source}: {exc}") from exc
        if table.ndim != 2 or table.shape[1] != 2:
            raise StfConvolutionError("ASCII waveform must contain exactly two columns: time amplitude")
        times, amplitudes = table[:, 0], table[:, 1]
        if not np.isfinite(amplitudes).all():
            raise StfConvolutionError("waveform amplitudes must be finite")
        return Waveform(times, amplitudes, infer_dt(times), "ascii", source)

    obspy = _obspy()
    try:
        stream = obspy.read(str(source), format="SAC")
    except Exception as exc:  # ObsPy has several reader-specific exception types.
        raise StfConvolutionError(f"could not read SAC waveform {source}: {exc}") from exc
    if len(stream) != 1:
        raise StfConvolutionError("SAC input must contain exactly one trace")
    trace = stream[0]
    if not np.isfinite(trace.data).all():
        raise StfConvolutionError("SAC waveform amplitudes must be finite")
    sac = getattr(trace.stats, "sac", {})
    # ObsPy exposes SAC's header reference time through starttime + b rather
    # than a stable ``stats.sac.reftime`` attribute on every supported release.
    b = float(getattr(sac, "b", 0.0))
    reference = trace.stats.starttime - b
    times = b + np.arange(trace.stats.npts, dtype=float) * float(trace.stats.delta)
    return Waveform(times, np.asarray(trace.data, dtype=float), infer_dt(times), "sac", source, trace.copy(), reference)


def _write_sac(waveform: Waveform, destination: Path) -> None:
    if waveform.sac_trace is None or waveform.sac_reference_time is None:
        raise StfConvolutionError("SAC output requires a waveform read from SAC input")
    trace = waveform.sac_trace.copy()
    b = float(waveform.times[0])
    trace.data = np.asarray(waveform.amplitudes, dtype=np.float32)
    trace.stats.delta = waveform.dt
    trace.stats.npts = len(trace.data)
    trace.stats.starttime = waveform.sac_reference_time + b
    if not hasattr(trace.stats, "sac"):
        trace.stats.sac = {}
    trace.stats.sac.b = b
    trace.stats.sac.e = b + (len(trace.data) - 1) * waveform.dt
    trace.write(str(destination), format="SAC")

    verified = read_waveform(destination, format="sac")
    expected_e = b + (len(waveform.amplitudes) - 1) * waveform.dt
    if len(verified.amplitudes) != len(waveform.amplitudes) or not np.allclose(verified.amplitudes, waveform.amplitudes, rtol=2e-6, atol=2e-6):
        raise StfConvolutionError("SAC round-trip data verification failed")
    if not np.isclose(verified.dt, waveform.dt, rtol=0.0, atol=1e-7):
        raise StfConvolutionError("SAC round-trip delta verification failed")
    if not np.isclose(verified.times[0], b, rtol=0.0, atol=1e-6) or not np.isclose(verified.times[-1], expected_e, rtol=0.0, atol=1e-5):
        raise StfConvolutionError("SAC round-trip b/e verification failed")
    if abs(float(verified.sac_trace.stats.starttime - (waveform.sac_reference_time + b))) > 1.0e-6:
        raise StfConvolutionError("SAC round-trip absolute start time verification failed")


def write_waveform(waveform: Waveform, path: str | Path, *, format: str = "auto", overwrite: bool = False) -> Path:
    destination = Path(path)
    selected = _resolve_format(destination, format if format != "auto" else waveform.format)
    if waveform.path is not None and destination.resolve() == waveform.path.resolve():
        raise StfConvolutionError("refusing to write output over the input waveform")
    if destination.exists() and not overwrite:
        raise StfConvolutionError(f"refusing to overwrite existing output: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if selected == "ascii":
        np.savetxt(destination, np.column_stack((waveform.times, waveform.amplitudes)), fmt="%.10e")
    else:
        _write_sac(waveform, destination)
    return destination
