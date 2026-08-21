"""Whole-file ASDF I/O for SPECFEM ``synthetic.h5`` seismograms."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
import shutil

import numpy as np

from .errors import StfConvolutionError
from .models import Waveform


def _h5py():
    try:
        import h5py
    except ImportError as exc:
        raise StfConvolutionError("ASDF support requires h5py; install ulvz-stf-convolution[asdf]") from exc
    return h5py


def _text(value: object) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _starttime_ns(value: object, dataset_path: str) -> int:
    if isinstance(value, np.ndarray) and value.shape == ():
        value = value.item()
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return int(value)
    raise StfConvolutionError(f"ASDF waveform {dataset_path} has an invalid starttime attribute")


def _waveform_from_dataset(dataset, source: Path) -> Waveform:
    dataset_path = dataset.name
    if dataset.ndim != 1 or not np.issubdtype(dataset.dtype, np.floating):
        raise StfConvolutionError(f"ASDF waveform {dataset_path} must be a one-dimensional floating-point dataset")
    if "sampling_rate" not in dataset.attrs or "starttime" not in dataset.attrs:
        raise StfConvolutionError(f"ASDF waveform {dataset_path} is missing sampling_rate or starttime")
    sampling_rate = float(dataset.attrs["sampling_rate"])
    if not np.isfinite(sampling_rate) or sampling_rate <= 0.0:
        raise StfConvolutionError(f"ASDF waveform {dataset_path} has an invalid sampling_rate attribute")
    amplitudes = np.asarray(dataset[...], dtype=float)
    if amplitudes.size < 2:
        raise StfConvolutionError(f"ASDF waveform {dataset_path} must contain at least two samples")
    if not np.isfinite(amplitudes).all():
        raise StfConvolutionError(f"ASDF waveform {dataset_path} amplitudes must be finite")
    dt = 1.0 / sampling_rate
    return Waveform(
        times=np.arange(amplitudes.size, dtype=float) * dt,
        amplitudes=amplitudes,
        dt=dt,
        format="asdf",
        path=source,
        asdf_dataset_path=dataset_path,
        asdf_starttime_ns=_starttime_ns(dataset.attrs["starttime"], dataset_path),
        asdf_dtype=dataset.dtype,
    )


def read_asdf_waveforms(path: str | Path) -> tuple[Waveform, ...]:
    """Read every SPECFEM waveform from an ASDF ``synthetic.h5`` file."""
    source = Path(path)
    h5py = _h5py()
    try:
        with h5py.File(source, "r") as handle:
            if _text(handle.attrs.get("file_format", "")) != "ASDF":
                raise StfConvolutionError(f"{source} is not an ASDF file (file_format != ASDF)")
            if "Waveforms" not in handle or not isinstance(handle["Waveforms"], h5py.Group):
                raise StfConvolutionError(f"{source} has no ASDF /Waveforms group")
            waveforms: list[Waveform] = []

            def visit(_name: str, item) -> None:
                if isinstance(item, h5py.Dataset) and item.name.rsplit("/", 1)[-1] != "StationXML":
                    waveforms.append(_waveform_from_dataset(item, source))

            handle["Waveforms"].visititems(visit)
    except OSError as exc:
        raise StfConvolutionError(f"could not read ASDF waveform file {source}: {exc}") from exc
    if not waveforms:
        raise StfConvolutionError(f"{source} contains no waveform datasets under /Waveforms")
    return tuple(waveforms)


def _time_string(epoch_ns: int) -> str:
    return datetime.fromtimestamp(epoch_ns / 1.0e9, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S")


def _renamed_dataset_path(waveform: Waveform, sampling_rate: float, input_npts: int) -> tuple[str, int]:
    if waveform.asdf_dataset_path is None or waveform.asdf_starttime_ns is None:
        raise StfConvolutionError("ASDF output requires waveform metadata read from an ASDF input")
    shift_ns = int(round(float(waveform.times[0]) * 1.0e9))
    start_ns = waveform.asdf_starttime_ns + shift_ns
    original = PurePosixPath(waveform.asdf_dataset_path)
    if shift_ns == 0 and len(waveform.amplitudes) == input_npts:
        return str(original), start_ns
    parts = original.name.split("__")
    if len(parts) < 4 or not parts[0] or not parts[3]:
        raise StfConvolutionError(
            f"ASDF waveform {waveform.asdf_dataset_path} has a non-SPECFEM name and cannot be retimed"
        )
    end_ns = start_ns + int(round((len(waveform.amplitudes) - 1) * 1.0e9 / sampling_rate))
    tag = "__".join(parts[3:])
    name = f"{parts[0]}__{_time_string(start_ns)}__{_time_string(end_ns)}__{tag}"
    return str(original.parent / name), start_ns


def _validate_asdf_output(source: Path, waveforms: tuple[Waveform, ...]) -> dict[str, Waveform]:
    originals = {waveform.asdf_dataset_path: waveform for waveform in read_asdf_waveforms(source)}
    supplied = {waveform.asdf_dataset_path: waveform for waveform in waveforms}
    if None in supplied or len(supplied) != len(waveforms) or set(supplied) != set(originals):
        raise StfConvolutionError("ASDF output must contain exactly the waveform datasets read from the input file")
    for dataset_path, waveform in supplied.items():
        assert dataset_path is not None
        original = originals[dataset_path]
        if waveform.format != "asdf" or waveform.asdf_starttime_ns != original.asdf_starttime_ns:
            raise StfConvolutionError(f"ASDF waveform metadata changed unexpectedly for {dataset_path}")
        if len(waveform.amplitudes) < 1 or not np.isfinite(waveform.amplitudes).all():
            raise StfConvolutionError(f"ASDF waveform {dataset_path} output amplitudes must be finite")
        if not np.isclose(waveform.dt, original.dt, rtol=0.0, atol=max(1.0e-12, original.dt * 1.0e-9)):
            raise StfConvolutionError(f"ASDF waveform {dataset_path} output dt does not match its input")
    return {path: waveform for path, waveform in supplied.items() if path is not None}


def write_asdf_waveforms(
    source_path: str | Path,
    destination_path: str | Path,
    waveforms: Iterable[Waveform],
    *,
    overwrite: bool = False,
) -> Path:
    """Write convolved traces to a new ASDF file while preserving all other content."""
    source = Path(source_path)
    destination = Path(destination_path)
    if source.resolve() == destination.resolve():
        raise StfConvolutionError("refusing to write ASDF output over the input waveform file")
    if destination.exists() and not overwrite:
        raise StfConvolutionError(f"refusing to overwrite existing output: {destination}")
    selected = _validate_asdf_output(source, tuple(waveforms))
    h5py = _h5py()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, destination)
        with h5py.File(destination, "r+") as handle:
            replacements: list[tuple[str, str, int, Waveform, dict[str, object], np.dtype]] = []
            for old_path, waveform in selected.items():
                dataset = handle[old_path]
                sampling_rate = float(dataset.attrs["sampling_rate"])
                new_path, start_ns = _renamed_dataset_path(waveform, sampling_rate, len(dataset))
                replacements.append((old_path, new_path, start_ns, waveform, dict(dataset.attrs.items()), dataset.dtype))
            old_paths = {item[0] for item in replacements}
            new_paths = [item[1] for item in replacements]
            if len(set(new_paths)) != len(new_paths) or any(path in handle and path not in old_paths for path in new_paths):
                raise StfConvolutionError("ASDF output waveform naming would overwrite an existing dataset")
            for old_path, _new_path, _start_ns, _waveform, _attributes, _dtype in replacements:
                del handle[old_path]
            for _old_path, new_path, start_ns, waveform, attributes, dtype in replacements:
                created = handle.create_dataset(new_path, data=np.asarray(waveform.amplitudes, dtype=dtype), dtype=dtype)
                for key, value in attributes.items():
                    created.attrs[key] = value
                created.attrs["starttime"] = np.int64(start_ns)
    except OSError as exc:
        raise StfConvolutionError(f"could not write ASDF waveform file {destination}: {exc}") from exc
    return destination
