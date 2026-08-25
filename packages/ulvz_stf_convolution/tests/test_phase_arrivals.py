from __future__ import annotations

import hashlib
from pathlib import Path

import h5py
import numpy as np
import pytest
from obspy import UTCDateTime
from obspy import Trace, read

from ulvz_stf_convolution.asdf import read_asdf_waveforms
from ulvz_stf_convolution.cli import main


phase = pytest.importorskip("ulvz_phase_arrivals")


def _annotated_run(tmp_path: Path, *, initial_stf_shift: float = 0.0) -> tuple[Path, list[dict[str, str]]]:
    run = tmp_path / "run"; data = run / "DATA"; output = run / "OUTPUT_FILES"
    data.mkdir(parents=True); output.mkdir()
    data.joinpath("CMTSOLUTION").write_text(
        "PDE 2022 9 20 18 23 42.90 0 0 12 0 6 TEST\n"
        "time shift: 2\nhalf duration: 9\nlatitude: 0\nlongitude: 0\ndepth: 12\n", encoding="utf-8",
    )
    data.joinpath("STATIONS").write_text("STA AX 0.0 90.0 0.0 0.0\n", encoding="utf-8")
    source = output / "synthetic.h5"
    with h5py.File(source, "w") as handle:
        handle.attrs["file_format"] = "ASDF"; handle.attrs["file_format_version"] = "1.0.0"
        station = handle.require_group("Waveforms").require_group("AX.STA")
        dataset = station.create_dataset(
            "AX.STA.S3.BXZ__2022-09-20T18:23:42__2022-09-20T18:23:46__synthetic",
            data=np.arange(40, dtype=np.float32),
        )
        dataset.attrs["sampling_rate"] = 10.0
        dataset.attrs["starttime"] = np.int64(1_663_698_222_150_000_000)
    _, rows, _ = phase.annotate_run(run, input_format="asdf", phases=("P", "Pdiff", "S", "Sdiff"),
                                    stf_time_shift_s=initial_stf_shift)
    phase.write_outputs(output, rows, {"test": True})
    return source, rows


def _phase_src() -> str:
    return str(Path(phase.__file__).resolve().parent.parent)


def _row(rows, requested: str) -> dict[str, str]:
    return next(row for row in rows if row["requested_phase"] == requested and row["component"] == "BXZ")


def test_asdf_annotation_shift_uses_actual_output_axis_and_preserves_input(tmp_path) -> None:
    source, input_rows = _annotated_run(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    input_sidecar = source.parent / "synthetic.theoretical_arrivals.h5"
    input_csv = source.parent / "theoretical_arrivals.csv"
    annotation_before = (hashlib.sha256(input_sidecar.read_bytes()).hexdigest(), hashlib.sha256(input_csv.read_bytes()).hexdigest())
    stf = tmp_path / "stf.txt"; stf.write_text("0 1\n0.1 1\n", encoding="utf-8")
    destination = tmp_path / "shifted.h5"
    assert main([
        "--input", str(source), "--output", str(destination), "--input-format", "asdf",
        "--stf-kind", "numeric", "--stf-file", str(stf), "--stf-time-shift", "3", "--mode", "full",
        "--phase-arrivals-src", _phase_src(),
    ]) == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    assert annotation_before == (hashlib.sha256(input_sidecar.read_bytes()).hexdigest(), hashlib.sha256(input_csv.read_bytes()).hexdigest())
    derived = phase.read_annotation(Path(f"{destination}.theoretical_arrivals"))
    assert derived is not None
    original, updated = _row(input_rows, "P"), _row(derived, "P")
    assert updated["travel_time_s"] == original["travel_time_s"]
    assert updated["taup_model"] == original["taup_model"]
    assert updated["total_stf_time_shift_s"] == "3.000000000"
    assert UTCDateTime(updated["effective_arrival_time_utc"]) - UTCDateTime(original["effective_arrival_time_utc"]) == pytest.approx(3.0)
    assert float(updated["effective_arrival_from_trace_start_s"]) == pytest.approx(
        float(original["arrival_from_trace_start_s"]), abs=1.0e-5
    )
    trace = read_asdf_waveforms(destination)[0]
    assert float(updated["output_trace_starttime_epoch_s"]) == pytest.approx(trace.asdf_starttime_ns / 1e9)
    assert _row(derived, "Pdiff")["status"] == "missing"


def test_zero_shift_duration_change_does_not_move_absolute_arrival(tmp_path) -> None:
    source, input_rows = _annotated_run(tmp_path)
    destination = tmp_path / "duration.h5"
    assert main([
        "--input", str(source), "--output", str(destination), "--input-format", "asdf",
        "--stf-kind", "gaussian", "--half-duration", "0.1", "--mode", "full",
        "--phase-arrivals-src", _phase_src(),
    ]) == 0
    derived = phase.read_annotation(Path(f"{destination}.theoretical_arrivals"))
    original, updated = _row(input_rows, "P"), _row(derived, "P")
    assert updated["total_stf_time_shift_s"] == "0.000000000"
    assert updated["effective_arrival_time_utc"] == original["effective_arrival_time_utc"]
    assert float(updated["effective_arrival_from_trace_start_s"]) != pytest.approx(float(original["arrival_from_trace_start_s"]))


def test_cumulative_stf_shift_keeps_cmtsolution_shift_separate(tmp_path) -> None:
    source, _ = _annotated_run(tmp_path, initial_stf_shift=2.0)
    stf = tmp_path / "stf.txt"; stf.write_text("0 1\n0.1 1\n", encoding="utf-8")
    destination = tmp_path / "cumulative.h5"
    assert main([
        "--input", str(source), "--output", str(destination), "--input-format", "asdf",
        "--stf-kind", "numeric", "--stf-file", str(stf), "--stf-time-shift", "3", "--mode", "full",
        "--phase-arrivals-src", _phase_src(),
    ]) == 0
    derived = phase.read_annotation(Path(f"{destination}.theoretical_arrivals"))
    updated = _row(derived, "P")
    assert updated["cmtsolution_time_shift_s"] == "2.000000000"
    assert updated["applied_stf_time_shift_s"] == "3.000000000"
    assert updated["total_stf_time_shift_s"] == "5.000000000"
    second = tmp_path / "cumulative_second.h5"
    assert main([
        "--input", str(destination), "--output", str(second), "--input-format", "asdf",
        "--stf-kind", "numeric", "--stf-file", str(stf), "--stf-time-shift", "1", "--mode", "full",
        "--phase-arrivals-src", _phase_src(),
    ]) == 0
    twice = phase.read_annotation(Path(f"{second}.theoretical_arrivals"))
    final = _row(twice, "P")
    assert final["applied_stf_time_shift_s"] == "1.000000000"
    assert final["total_stf_time_shift_s"] == "6.000000000"


def test_sac_primary_pick_is_retimed_against_output_reference_time(tmp_path) -> None:
    run = tmp_path / "sac_run"; data = run / "DATA"; output = run / "OUTPUT_FILES"
    data.mkdir(parents=True); output.mkdir()
    data.joinpath("CMTSOLUTION").write_text(
        "PDE 2022 9 20 18 23 42.90 0 0 12 0 6 TEST\n"
        "time shift: 2\nhalf duration: 9\nlatitude: 0\nlongitude: 0\ndepth: 12\n", encoding="utf-8",
    )
    data.joinpath("STATIONS").write_text("STA AX 0.0 90.0 0.0 0.0\n", encoding="utf-8")
    source = output / "AX.STA.BXZ.sac"
    trace = Trace(np.arange(40, dtype=np.float32))
    trace.stats.network = "AX"; trace.stats.station = "STA"; trace.stats.channel = "BXZ"
    trace.stats.starttime = UTCDateTime(2022, 9, 20, 18, 23, 42.15); trace.stats.sampling_rate = 10.0
    trace.write(str(source), format="SAC")
    _, rows, _ = phase.annotate_run(run, input_format="sac", phases=("P",))
    phase.write_outputs(output, rows, {"test": True})
    primary = _row(rows, "P")
    stream = read(str(source), format="SAC"); input_trace = stream[0]
    reference = input_trace.stats.starttime - float(input_trace.stats.sac.b)
    input_trace.stats.sac.t0 = float(UTCDateTime(primary["effective_arrival_time_utc"]) - reference)
    input_trace.stats.sac.kt0 = "P"; input_trace.write(str(source), format="SAC")
    stf = tmp_path / "sac_stf.txt"; stf.write_text("0 1\n0.1 1\n", encoding="utf-8")
    destination = tmp_path / "retimed.sac"
    assert main([
        "--input", str(source), "--output", str(destination), "--input-format", "sac",
        "--stf-kind", "numeric", "--stf-file", str(stf), "--stf-time-shift", "3", "--mode", "full",
        "--phase-arrivals-src", _phase_src(),
    ]) == 0
    derived = phase.read_annotation(Path(f"{destination}.theoretical_arrivals"))
    updated = _row(derived, "P")
    output_trace = read(str(destination), format="SAC")[0]
    output_reference = output_trace.stats.starttime - float(output_trace.stats.sac.b)
    assert output_trace.stats.sac.kt0 == "P"
    assert output_trace.stats.sac.t0 == pytest.approx(
        UTCDateTime(updated["effective_arrival_time_utc"]) - output_reference, abs=1.0e-4
    )
