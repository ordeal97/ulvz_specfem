"""Formal SAC primary-pick recognition and retiming for derived waveforms."""
from __future__ import annotations

from pathlib import Path

from obspy import UTCDateTime, read


SAC_PRIMARY_PICK_SLOTS = {"P": 0, "Pdiff": 1, "S": 2, "Sdiff": 3, "PP": 4, "SKS": 5, "SS": 6}


def _header_value(sac, key: str):
    value = sac.get(key) if hasattr(sac, "get") else getattr(sac, key, None)
    if value is None or float(value) == -12345.0:
        return None
    return value


def _reference_time(trace) -> UTCDateTime:
    sac = getattr(trace.stats, "sac", {})
    return trace.stats.starttime - float(_header_value(sac, "b") or 0.0)


def _trace_path_matches(row: dict[str, str], source: Path) -> bool:
    try:
        path = row.get("input_waveform_trace_path") or row["trace_path"]
        return Path(path).resolve() == source.resolve()
    except OSError:
        return (row.get("input_waveform_trace_path") or row["trace_path"]) == str(source)


def retime_sac_primary_picks(input_path: Path, output_path: Path, rows: list[dict[str, str]]) -> tuple[str, ...]:
    """Retiming only package-defined and formally verified SAC primary picks.

    The result is written to ``output_path`` only.  Pick values are relative to
    the output SAC reference time, never to the waveform starttime.
    """
    source = Path(input_path)
    destination = Path(output_path)
    if source.resolve() == destination.resolve():
        raise ValueError("refusing to retime SAC picks in the input waveform")
    input_stream = read(str(source), format="SAC")
    output_stream = read(str(destination), format="SAC")
    if len(input_stream) != 1 or len(output_stream) != 1:
        raise ValueError("SAC primary-pick retiming requires one trace per file")
    input_trace, output_trace = input_stream[0], output_stream[0]
    input_sac = getattr(input_trace.stats, "sac", {})
    output_sac = dict(getattr(output_trace.stats, "sac", {}))
    input_reference = _reference_time(input_trace)
    output_reference = _reference_time(output_trace)
    tolerance = max(1.0e-3, 0.5 * float(input_trace.stats.delta))
    updated: list[str] = []
    for phase, slot in SAC_PRIMARY_PICK_SLOTS.items():
        label_key, time_key = f"kt{slot}", f"t{slot}"
        label = str(input_sac.get(label_key, "")).strip()
        pick = _header_value(input_sac, time_key)
        candidates = [
            row for row in rows
            if row.get("input_format") == "sac" and _trace_path_matches(row, source)
            and row.get("requested_phase") == phase and row.get("status") == "ok"
            and row.get("is_primary") == "true"
        ]
        if label != phase or pick is None or len(candidates) != 1:
            continue
        row = candidates[0]
        travel = row.get("travel_time_s", "")
        if not travel:
            continue
        prior_total = float(row["total_stf_time_shift_s"]) - float(row["applied_stf_time_shift_s"])
        expected_input = UTCDateTime(row["centroid_source_time_utc"]) + prior_total + float(travel)
        if abs((input_reference + float(pick)) - expected_input) > tolerance:
            continue
        effective = row.get("effective_arrival_time_utc", "")
        if not effective:
            continue
        output_sac[time_key] = float(UTCDateTime(effective) - output_reference)
        output_sac[label_key] = phase
        updated.append(phase)
    if updated:
        output_trace.stats.sac = output_sac
        output_trace.write(str(destination), format="SAC")
    return tuple(updated)
