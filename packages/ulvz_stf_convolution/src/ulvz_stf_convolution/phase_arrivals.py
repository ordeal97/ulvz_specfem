"""Optional bridge to the public ``ulvz_phase_arrivals`` annotation API."""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys
from types import ModuleType
from typing import Iterable

from .errors import StfConvolutionError


_CANONICAL_NAMES = ("theoretical_arrivals.csv", "synthetic.theoretical_arrivals.h5")
_REQUIRED_API = (
    "API_VERSION", "SCHEMA_VERSION", "TraceAxis", "derive_convolved_rows", "read_annotation",
    "retime_sac_primary_picks", "write_outputs",
)


def _annotation_directories(input_path: Path, input_format: str) -> tuple[Path, ...]:
    directories = [output_annotation_dir(input_path), input_path.parent]
    if input_format == "sac" and input_path.parent.name == "sac_picks":
        directories.append(input_path.parent.parent)
    return tuple(dict.fromkeys(directory.resolve() for directory in directories))


def _has_annotation(directory: Path) -> bool:
    return any((directory / name).is_file() for name in _CANONICAL_NAMES)


def _load_package(source: str | None) -> ModuleType:
    if source:
        root = Path(source).resolve()
        if not (root / "ulvz_phase_arrivals").is_dir():
            raise StfConvolutionError("--phase-arrivals-src must contain the ulvz_phase_arrivals package directory")
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        module = import_module("ulvz_phase_arrivals")
    except ImportError as exc:
        raise StfConvolutionError(
            "formal theoretical-arrivals metadata was found, but ulvz_phase_arrivals is unavailable; "
            "install the compatible package or provide --phase-arrivals-src"
        ) from exc
    missing = [name for name in _REQUIRED_API if not hasattr(module, name)]
    if missing:
        raise StfConvolutionError(
            "formal theoretical-arrivals metadata requires ulvz_phase_arrivals schema/API v0.2+; "
            f"missing public API: {', '.join(missing)}"
        )
    try:
        version = tuple(int(part) for part in str(module.API_VERSION).split(".")[:2])
    except ValueError as exc:
        raise StfConvolutionError("ulvz_phase_arrivals exposes an invalid public API version") from exc
    if version < (0, 2):
        raise StfConvolutionError("formal theoretical-arrivals metadata requires ulvz_phase_arrivals API v0.2+")
    return module


def load_input_annotation(input_path: Path, input_format: str, source: str | None):
    """Return ``(package, rows)`` for a formal annotation, otherwise ``None``."""
    if input_format not in {"sac", "asdf"}:
        return None
    directories = _annotation_directories(input_path, input_format)
    candidates = [directory for directory in directories if _has_annotation(directory)]
    if not candidates:
        return None
    package = _load_package(source)
    for directory in candidates:
        try:
            rows = package.read_annotation(directory)
        except Exception as exc:
            raise StfConvolutionError(f"could not read formal theoretical-arrivals annotation in {directory}: {exc}") from exc
        if rows is not None:
            return package, rows
    return None


def output_annotation_dir(output_path: Path) -> Path:
    return Path(f"{output_path}.theoretical_arrivals")


def derive_annotation(
    package: ModuleType,
    rows: list[dict[str, str]],
    axes: Iterable[object],
    *,
    applied_stf_time_shift_s: float,
    stf_reference: str,
    stf_provenance: dict[str, object],
) -> list[dict[str, str]]:
    try:
        return package.derive_convolved_rows(
            rows,
            axes,
            applied_stf_time_shift_s=applied_stf_time_shift_s,
            stf_reference=stf_reference,
            stf_provenance=stf_provenance,
        )
    except Exception as exc:
        raise StfConvolutionError(f"could not derive theoretical-arrivals annotation: {exc}") from exc


def write_derived_annotation(
    package: ModuleType,
    rows: list[dict[str, str]],
    output_path: Path,
    *,
    applied_stf_time_shift_s: float,
    stf_reference: str,
    stf_provenance: dict[str, object],
    overwrite: bool,
) -> tuple[Path, Path]:
    try:
        destination = output_annotation_dir(output_path)
        return package.write_outputs(destination, rows, {
            "producer": "ulvz_stf_convolution",
            "derived_schema_version": package.SCHEMA_VERSION,
            "applied_stf_time_shift_s": applied_stf_time_shift_s,
            "stf_reference": stf_reference,
            "stf_provenance": stf_provenance,
        }, overwrite=overwrite)
    except Exception as exc:
        raise StfConvolutionError(f"could not write derived theoretical-arrivals annotation: {exc}") from exc


def stf_provenance(result, applied_stf_time_shift_s: float) -> tuple[str, dict[str, object]]:
    """Describe STF coordinates without treating duration or centroid as a shift."""
    return (
        "explicit_overall_shift_relative_to_stf_coordinate_zero",
        {
            "producer": "ulvz_stf_convolution",
            "stf_kind": result.stf.kind,
            "stf_time_axis_start_s": float(result.stf.times[0]),
            "stf_time_axis_end_s": float(result.stf.times[-1]),
            "half_duration_s": result.stf.metadata.get("half_duration"),
            "explicit_applied_stf_time_shift_s": float(applied_stf_time_shift_s),
            "time_shift_definition": "only explicit --stf-time-shift; duration, start, peak, and centroid are not inferred shifts",
            "convolution_mode": result.mode,
        },
    )
