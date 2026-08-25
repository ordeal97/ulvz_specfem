"""Shared input readers and TauP arrival calculation; no output mutation here."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

import h5py
import numpy as np
from obspy import UTCDateTime, read
from obspy.geodetics.base import locations2degrees
from obspy.taup import TauPyModel

DEFAULT_PHASES = ("P", "Pdiff", "S", "Sdiff", "PP", "SKS", "SS")
SCHEMA_VERSION = "1.1.0"
V1_SCHEMA_VERSION = "1.0.0"
CMTSOLUTION_ORIGIN_RE = re.compile(
    r"^\s*(?:PDE[A-Za-z]*)?\s*"
    r"(?P<year>\d{4})\s+(?P<month>\d{1,2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<hour>\d{1,2})\s+(?P<minute>\d{1,2})\s+(?P<second>[+-]?\d+(?:\.\d*)?)\b"
)

V1_CSV_FIELDS = (
    "schema_version", "input_format", "network", "station", "component", "trace_path",
    "trace_starttime_utc", "trace_starttime_epoch_s", "sampling_rate_hz", "npts",
    "sac_reference_time_utc", "sac_reference_time_epoch_s", "station_latitude_deg", "station_longitude_deg",
    "source_latitude_deg", "source_longitude_deg", "source_depth_km", "pde_origin_time_utc",
    "cmtsolution_time_shift_s", "centroid_source_time_utc", "cmtsolution_half_duration_s", "stf_time_shift_s",
    "taup_model", "requested_phase", "returned_phase", "status", "arrival_rank", "is_primary",
    "distance_deg", "travel_time_s", "base_arrival_time_utc", "effective_arrival_time_utc",
    "arrival_from_trace_start_s", "arrival_sample_index_float", "arrival_sample_index_nearest",
    "ray_param_sec_degree", "takeoff_angle_deg", "incident_angle_deg",
)

# v1.1 keeps every v1.0 field with its original meaning.  The fields below
# describe a derived waveform and deliberately do not repurpose its base axis.
DERIVED_CSV_FIELDS = (
    "input_schema_version", "input_waveform_trace_path", "applied_stf_time_shift_s", "total_stf_time_shift_s",
    "effective_source_time_utc", "stf_reference", "stf_provenance_json",
    "output_trace_path", "output_trace_starttime_utc", "output_trace_starttime_epoch_s",
    "output_sampling_rate_hz", "output_npts", "output_sac_reference_time_utc",
    "effective_arrival_from_trace_start_s", "effective_arrival_sample_index_float",
    "effective_arrival_sample_index_nearest", "derivation_status",
)
CSV_FIELDS = V1_CSV_FIELDS + DERIVED_CSV_FIELDS


@dataclass(frozen=True)
class TraceAxis:
    """Actual output waveform axis used when deriving arrival coordinates."""

    input_trace_path: str
    output_trace_path: str
    output_starttime_epoch_s: float
    output_sampling_rate_hz: float
    output_npts: int
    output_sac_reference_epoch_s: float | None = None

    @property
    def output_starttime(self) -> UTCDateTime:
        return UTCDateTime(self.output_starttime_epoch_s)

    @property
    def output_sac_reference_time(self) -> UTCDateTime | None:
        return UTCDateTime(self.output_sac_reference_epoch_s) if self.output_sac_reference_epoch_s is not None else None


def _iso(value: UTCDateTime | None) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if value is not None else ""


def _number(value: Any) -> str:
    return "" if value is None else f"{float(value):.9f}"


@dataclass(frozen=True)
class Source:
    pde_origin_time: UTCDateTime
    time_shift_s: float
    latitude_deg: float
    longitude_deg: float
    depth_km: float
    half_duration_s: float | None

    @property
    def centroid_source_time(self) -> UTCDateTime:
        return self.pde_origin_time + self.time_shift_s


@dataclass(frozen=True)
class Station:
    network: str
    station: str
    latitude_deg: float
    longitude_deg: float


@dataclass(frozen=True)
class TraceMetadata:
    input_format: str
    network: str
    station: str
    component: str
    starttime: UTCDateTime
    sampling_rate_hz: float
    npts: int
    path: Path
    source_path: str
    sac_reference_time: UTCDateTime | None = None


def parse_cmtsolution(path: Path) -> Source:
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"empty CMTSOLUTION: {path}")
    match = CMTSOLUTION_ORIGIN_RE.match(lines[0])
    if match is None:
        raise ValueError(f"invalid CMTSOLUTION first line: {lines[0]}")
    origin = UTCDateTime(int(match["year"]), int(match["month"]), int(match["day"]),
                         int(match["hour"]), int(match["minute"]), float(match["second"]))
    values: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().lower()] = value.strip()
    required = ("time shift", "latitude", "longitude", "depth")
    missing = [key for key in required if key not in values]
    if missing:
        raise ValueError(f"{path}: missing CMTSOLUTION fields: {', '.join(missing)}")
    half = values.get("half duration")
    return Source(origin, float(values["time shift"]), float(values["latitude"]),
                  float(values["longitude"]), float(values["depth"]), float(half) if half is not None else None)


def parse_stations(path: Path) -> dict[tuple[str, str], Station]:
    result: dict[tuple[str, str], Station] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        values = line.split()
        if len(values) != 6:
            raise ValueError(f"{path}:{line_number}: expected six STATIONS columns")
        station, network = values[:2]
        key = (network, station)
        if key in result:
            raise ValueError(f"{path}:{line_number}: duplicate station {network}.{station}")
        result[key] = Station(network, station, float(values[2]), float(values[3]))
    if not result:
        raise ValueError(f"no stations in {path}")
    return result


def _decode(value: Any) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def read_asdf_traces(path: Path) -> list[TraceMetadata]:
    result: list[TraceMetadata] = []
    component_pattern = re.compile(r"\.BX([ENZ])(?:__|\.|$)")
    with h5py.File(path, "r") as handle:
        if "Waveforms" not in handle:
            raise ValueError(f"{path}: ASDF Waveforms group missing")
        for station_id, group in handle["Waveforms"].items():
            if not isinstance(group, h5py.Group) or "." not in station_id:
                continue
            network, station = station_id.split(".", 1)
            for name, dataset in group.items():
                match = component_pattern.search(name)
                if not isinstance(dataset, h5py.Dataset) or match is None or dataset.ndim != 1:
                    continue
                if "starttime" not in dataset.attrs or "sampling_rate" not in dataset.attrs:
                    raise ValueError(f"{dataset.name}: starttime/sampling_rate attribute missing")
                start_ns = int(dataset.attrs["starttime"])
                result.append(TraceMetadata("asdf", network, station, "BX" + match.group(1),
                                            UTCDateTime(start_ns / 1.0e9), float(dataset.attrs["sampling_rate"]),
                                            int(dataset.shape[0]), path, dataset.name))
    if not result:
        raise ValueError(f"{path}: no BXE/BXN/BXZ traces")
    return sorted(result, key=lambda item: (item.network, item.station, item.component, item.source_path))


def sac_files(output_dir: Path) -> list[Path]:
    return sorted({*output_dir.glob("*.sac"), *output_dir.glob("*.SAC")})


def read_sac_traces(output_dir: Path) -> list[TraceMetadata]:
    files = sac_files(output_dir)
    result: list[TraceMetadata] = []
    for path in files:
        stream = read(str(path), headonly=True)
        if len(stream) != 1:
            raise ValueError(f"{path}: expected one SAC trace")
        trace = stream[0]
        sac = getattr(trace.stats, "sac", {})
        network = (trace.stats.network or sac.get("knetwk", "")).strip()
        station = (trace.stats.station or sac.get("kstnm", "")).strip()
        component = str(trace.stats.channel or sac.get("kcmpnm", "")).strip().upper()
        if not network or not station or component not in {"BXE", "BXN", "BXZ"}:
            raise ValueError(f"{path}: requires network, station, and BXE/BXN/BXZ channel")
        b = float(sac.get("b", 0.0))
        reference = trace.stats.starttime - b
        result.append(TraceMetadata("sac", network, station, component, trace.stats.starttime,
                                    float(trace.stats.sampling_rate), int(trace.stats.npts), path, str(path), reference))
    if not result:
        raise ValueError(f"{output_dir}: no SAC files matching *.sac or *.SAC")
    return sorted(result, key=lambda item: (item.network, item.station, item.component, str(item.path)))


def detect_format(run_dir: Path, requested: str) -> str:
    output = run_dir / "OUTPUT_FILES"
    has_asdf = (output / "synthetic.h5").is_file()
    has_sac = bool(sac_files(output))
    if requested != "auto":
        if requested == "asdf" and not has_asdf:
            raise ValueError(f"{output}/synthetic.h5 not found")
        if requested == "sac" and not has_sac:
            raise ValueError(f"{output}: no SAC input found")
        return requested
    if has_asdf == has_sac:
        found = "both ASDF and SAC" if has_asdf else "neither ASDF nor SAC"
        raise ValueError(f"{run_dir}: auto format is ambiguous ({found}); use --format explicitly")
    return "asdf" if has_asdf else "sac"


def load_traces(run_dir: Path, input_format: str) -> list[TraceMetadata]:
    output = run_dir / "OUTPUT_FILES"
    return read_asdf_traces(output / "synthetic.h5") if input_format == "asdf" else read_sac_traces(output)


def _arrival_rows(source: Source, station: Station, traces: Iterable[TraceMetadata], model: TauPyModel,
                  model_name: str, phases: tuple[str, ...], stf_time_shift_s: float) -> list[dict[str, str]]:
    distance = locations2degrees(source.latitude_deg, source.longitude_deg, station.latitude_deg, station.longitude_deg)
    rows: list[dict[str, str]] = []
    for requested_phase in phases:
        arrivals = sorted(model.get_travel_times(source.depth_km, distance, phase_list=[requested_phase]), key=lambda value: value.time)
        payload: list[tuple[int | None, bool, Any | None]] = ([(None, False, None)] if not arrivals else
                                                               [(index, index == 0, arrival) for index, arrival in enumerate(arrivals)])
        for trace in traces:
            for rank, primary, arrival in payload:
                base = source.centroid_source_time + arrival.time if arrival is not None else None
                effective = base + stf_time_shift_s if base is not None else None
                relative = effective - trace.starttime if effective is not None else None
                record = {field: "" for field in CSV_FIELDS}
                record.update({
                    "schema_version": SCHEMA_VERSION, "input_format": trace.input_format,
                    "network": station.network, "station": station.station, "component": trace.component,
                    "trace_path": trace.source_path, "trace_starttime_utc": _iso(trace.starttime),
                    "trace_starttime_epoch_s": _number(trace.starttime.timestamp), "sampling_rate_hz": _number(trace.sampling_rate_hz),
                    "npts": str(trace.npts), "sac_reference_time_utc": _iso(trace.sac_reference_time),
                    "sac_reference_time_epoch_s": _number(trace.sac_reference_time.timestamp if trace.sac_reference_time else None),
                    "station_latitude_deg": _number(station.latitude_deg), "station_longitude_deg": _number(station.longitude_deg),
                    "source_latitude_deg": _number(source.latitude_deg), "source_longitude_deg": _number(source.longitude_deg),
                    "source_depth_km": _number(source.depth_km), "pde_origin_time_utc": _iso(source.pde_origin_time),
                    "cmtsolution_time_shift_s": _number(source.time_shift_s), "centroid_source_time_utc": _iso(source.centroid_source_time),
                    "cmtsolution_half_duration_s": _number(source.half_duration_s), "stf_time_shift_s": _number(stf_time_shift_s),
                    "taup_model": model_name, "requested_phase": requested_phase,
                    "returned_phase": arrival.name if arrival is not None else "", "status": "ok" if arrival is not None else "missing",
                    "arrival_rank": "" if rank is None else str(rank), "is_primary": "true" if primary else "false",
                    "distance_deg": _number(distance), "travel_time_s": _number(arrival.time if arrival is not None else None),
                    "base_arrival_time_utc": _iso(base), "effective_arrival_time_utc": _iso(effective),
                    "arrival_from_trace_start_s": _number(relative),
                    "arrival_sample_index_float": _number(relative * trace.sampling_rate_hz if relative is not None else None),
                    "arrival_sample_index_nearest": str(int(round(relative * trace.sampling_rate_hz))) if relative is not None else "",
                    "ray_param_sec_degree": _number(getattr(arrival, "ray_param_sec_degree", None) if arrival is not None else None),
                    "takeoff_angle_deg": _number(getattr(arrival, "takeoff_angle", None) if arrival is not None else None),
                    "incident_angle_deg": _number(getattr(arrival, "incident_angle", None) if arrival is not None else None),
                    "input_schema_version": SCHEMA_VERSION,
                    "input_waveform_trace_path": trace.source_path,
                    "applied_stf_time_shift_s": _number(stf_time_shift_s),
                    "total_stf_time_shift_s": _number(stf_time_shift_s),
                    "effective_source_time_utc": _iso(source.centroid_source_time + stf_time_shift_s),
                    "stf_reference": "explicit_overall_shift_relative_to_stf_coordinate_zero",
                    "stf_provenance_json": json.dumps({"producer": "ulvz_phase_arrivals", "time_shift_source": "explicit_stf_time_shift_s"}, sort_keys=True),
                    "output_trace_path": trace.source_path,
                    "output_trace_starttime_utc": _iso(trace.starttime),
                    "output_trace_starttime_epoch_s": _number(trace.starttime.timestamp),
                    "output_sampling_rate_hz": _number(trace.sampling_rate_hz),
                    "output_npts": str(trace.npts),
                    "output_sac_reference_time_utc": _iso(trace.sac_reference_time),
                    "effective_arrival_from_trace_start_s": _number(relative),
                    "effective_arrival_sample_index_float": _number(relative * trace.sampling_rate_hz if relative is not None else None),
                    "effective_arrival_sample_index_nearest": str(int(round(relative * trace.sampling_rate_hz))) if relative is not None else "",
                    "derivation_status": "initial_annotation",
                })
                rows.append(record)
    return rows


def annotate_run(run_dir: Path, *, input_format: str = "auto", model_name: str = "prem",
                 phases: Iterable[str] = DEFAULT_PHASES, stf_time_shift_s: float = 0.0) -> tuple[str, list[dict[str, str]], list[TraceMetadata]]:
    if model_name.lower() != "prem":
        raise ValueError("only --model prem is currently supported")
    phase_tuple = tuple(item.strip() for item in phases if item.strip())
    if not phase_tuple:
        raise ValueError("at least one phase is required")
    run_dir = run_dir.resolve()
    selected = detect_format(run_dir, input_format)
    source = parse_cmtsolution(run_dir / "DATA/CMTSOLUTION")
    stations = parse_stations(run_dir / "DATA/STATIONS")
    traces = load_traces(run_dir, selected)
    grouped: dict[tuple[str, str], list[TraceMetadata]] = {}
    for trace in traces:
        grouped.setdefault((trace.network, trace.station), []).append(trace)
    unknown = sorted(key for key in grouped if key not in stations)
    if unknown:
        raise ValueError("trace station(s) missing from STATIONS: " + ", ".join(f"{n}.{s}" for n, s in unknown))
    model = TauPyModel(model="prem")
    rows: list[dict[str, str]] = []
    for key, station_traces in grouped.items():
        rows.extend(_arrival_rows(source, stations[key], station_traces, model, "prem", phase_tuple, float(stf_time_shift_s)))
    return selected, rows, traces


def arrival_identity(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    """Stable identity for an arrival row without recomputing TauP."""
    return tuple(row.get(field, "") for field in (
        "trace_path", "requested_phase", "returned_phase", "status", "arrival_rank", "component",
    ))


def _normalized_number(value: str | None) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def normalize_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Normalize readable v1.0/v1.1 rows to the current in-memory field set."""
    normalized: list[dict[str, str]] = []
    for incoming in rows:
        version = incoming.get("schema_version", "")
        if version not in {V1_SCHEMA_VERSION, SCHEMA_VERSION}:
            raise ValueError(f"unsupported theoretical-arrivals schema version: {version or '<missing>'}")
        expected = V1_CSV_FIELDS if version == V1_SCHEMA_VERSION else CSV_FIELDS
        missing = [field for field in expected if field not in incoming]
        allowed = CSV_FIELDS if version == V1_SCHEMA_VERSION else expected
        extra = [field for field in incoming if field not in allowed]
        if missing or extra:
            raise ValueError("incompatible theoretical-arrivals row fields: "
                             f"missing={','.join(missing) or '-'} extra={','.join(extra) or '-'}")
        row = {field: incoming.get(field, "") for field in CSV_FIELDS}
        if version == V1_SCHEMA_VERSION:
            row["input_schema_version"] = V1_SCHEMA_VERSION
            row["input_waveform_trace_path"] = incoming["trace_path"]
            row["total_stf_time_shift_s"] = incoming["stf_time_shift_s"]
            row["effective_source_time_utc"] = _iso(
                UTCDateTime(incoming["centroid_source_time_utc"]) + float(incoming["stf_time_shift_s"])
            )
            row["stf_reference"] = "legacy_explicit_stf_time_shift_s"
            row["stf_provenance_json"] = json.dumps({"normalized_from_schema": V1_SCHEMA_VERSION}, sort_keys=True)
            row["derivation_status"] = "normalized_v1_0"
        normalized.append(row)
    return normalized


def _axis_key(input_format: str, path: str) -> str:
    if input_format == "sac":
        try:
            return str(Path(path).resolve())
        except OSError:
            return path
    return path


def derive_convolved_rows(
    rows: Iterable[dict[str, str]],
    axes: Iterable[TraceAxis],
    *,
    applied_stf_time_shift_s: float,
    stf_reference: str,
    stf_provenance: dict[str, object],
) -> list[dict[str, str]]:
    """Transform existing annotation rows onto actual convolved waveform axes.

    This function intentionally does not import or invoke TauP.  It preserves
    v1 base fields and derives only the new effective-coordinate fields.
    """
    if not np.isfinite(applied_stf_time_shift_s):
        raise ValueError("applied STF time shift must be finite")
    original_rows = list(rows)
    normalized = normalize_rows(original_rows)
    axis_by_input: dict[str, TraceAxis] = {}
    for axis in axes:
        if not np.isfinite(axis.output_starttime_epoch_s) or not np.isfinite(axis.output_sampling_rate_hz):
            raise ValueError("output trace axis must be finite")
        if axis.output_sampling_rate_hz <= 0.0 or axis.output_npts < 1:
            raise ValueError("output trace axis has invalid sampling rate or npts")
        key = _axis_key("sac" if str(axis.input_trace_path).lower().endswith(".sac") else "asdf", axis.input_trace_path)
        if key in axis_by_input:
            raise ValueError(f"duplicate output trace axis for {axis.input_trace_path}")
        axis_by_input[key] = axis
    provenance_json = json.dumps(stf_provenance, sort_keys=True, separators=(",", ":"))
    result: list[dict[str, str]] = []
    for input_row, row in zip(original_rows, normalized, strict=True):
        output = dict(row)
        input_version = input_row["schema_version"]
        previous_total = _normalized_number(row["total_stf_time_shift_s"])
        if previous_total is None:
            previous_total = _normalized_number(row["stf_time_shift_s"]) or 0.0
        total = previous_total + applied_stf_time_shift_s
        output["schema_version"] = SCHEMA_VERSION
        output["input_schema_version"] = input_version
        output["input_waveform_trace_path"] = row["output_trace_path"] or row["trace_path"]
        output["applied_stf_time_shift_s"] = _number(applied_stf_time_shift_s)
        output["total_stf_time_shift_s"] = _number(total)
        output["stf_reference"] = stf_reference
        output["stf_provenance_json"] = provenance_json
        centroid = UTCDateTime(row["centroid_source_time_utc"])
        effective_source = centroid + total
        output["effective_source_time_utc"] = _iso(effective_source)
        current_trace_path = row["output_trace_path"] or row["trace_path"]
        axis = axis_by_input.get(_axis_key(row["input_format"], current_trace_path))
        if axis is None:
            output["derivation_status"] = "unmatched_output_trace"
            for field in (
                "output_trace_path", "output_trace_starttime_utc", "output_trace_starttime_epoch_s",
                "output_sampling_rate_hz", "output_npts", "output_sac_reference_time_utc",
                "effective_arrival_from_trace_start_s", "effective_arrival_sample_index_float",
                "effective_arrival_sample_index_nearest",
            ):
                output[field] = ""
            result.append(output)
            continue
        output.update({
            "output_trace_path": axis.output_trace_path,
            "output_trace_starttime_utc": _iso(axis.output_starttime),
            "output_trace_starttime_epoch_s": _number(axis.output_starttime_epoch_s),
            "output_sampling_rate_hz": _number(axis.output_sampling_rate_hz),
            "output_npts": str(axis.output_npts),
            "output_sac_reference_time_utc": _iso(axis.output_sac_reference_time),
            "derivation_status": "updated",
        })
        travel = _normalized_number(row["travel_time_s"])
        if row["status"] != "ok" or travel is None:
            output["effective_arrival_time_utc"] = ""
            output["effective_arrival_from_trace_start_s"] = ""
            output["effective_arrival_sample_index_float"] = ""
            output["effective_arrival_sample_index_nearest"] = ""
            result.append(output)
            continue
        effective_arrival = effective_source + travel
        relative = effective_arrival - axis.output_starttime
        sample_float = relative * axis.output_sampling_rate_hz
        output["effective_arrival_time_utc"] = _iso(effective_arrival)
        output["effective_arrival_from_trace_start_s"] = _number(relative)
        output["effective_arrival_sample_index_float"] = _number(sample_float)
        output["effective_arrival_sample_index_nearest"] = str(int(round(sample_float)))
        result.append(output)
    return result
