from __future__ import annotations

import hashlib
import csv
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np
from obspy import Trace, UTCDateTime, read
from obspy.taup import TauPyModel

from ulvz_phase_arrivals.cli import build_parser, write_sac_picks
from ulvz_phase_arrivals.core import (
    CSV_FIELDS, V1_CSV_FIELDS, V1_SCHEMA_VERSION, TraceAxis, annotate_run,
    derive_convolved_rows, detect_format, parse_cmtsolution, parse_stations,
)
from ulvz_phase_arrivals.storage import read_annotation, read_csv, read_sidecar, write_outputs


def make_run(root: Path, *, asdf: bool = True, sac: bool = False, cmt_shift: float = 2.0,
             asdf_start: UTCDateTime | None = None, sac_start: UTCDateTime | None = None) -> Path:
    run = root / "run"; data = run / "DATA"; output = run / "OUTPUT_FILES"
    data.mkdir(parents=True); output.mkdir()
    data.joinpath("CMTSOLUTION").write_text(
        "PDE 2022 9 20 18 23 42.90 0 0 12 0 6 TEST\n"
        f"time shift: {cmt_shift}\nhalf duration: 9.0\nlatitude: 0\nlongitude: 0\ndepth: 12\n",
        encoding="utf-8")
    data.joinpath("STATIONS").write_text("STA AX 0.0 90.0 0.0 0.0\n", encoding="utf-8")
    origin = UTCDateTime(2022, 9, 20, 18, 23, 42.90)
    asdf_start = asdf_start or origin - 0.75
    sac_start = sac_start or asdf_start
    if asdf:
        with h5py.File(output / "synthetic.h5", "w") as handle:
            group = handle.require_group("Waveforms").require_group("AX.STA")
            for component in "ENZ":
                dataset = group.create_dataset(f"AX.STA.S3.BX{component}__x", data=np.arange(32, dtype=np.float32))
                dataset.attrs["starttime"] = int(round(asdf_start.timestamp * 1.0e9))
                dataset.attrs["sampling_rate"] = 10.0
    if sac:
        for component in "ENZ":
            trace = Trace(np.arange(32, dtype=np.float32))
            trace.stats.network = "AX"; trace.stats.station = "STA"; trace.stats.channel = f"BX{component}"
            trace.stats.starttime = sac_start; trace.stats.sampling_rate = 10.0
            trace.write(str(output / f"AX.STA.BX{component}.sac"), format="SAC")
    return run


class PhaseArrivalTests(unittest.TestCase):
    def test_cmtsolution_origin_header_variants(self) -> None:
        cases = (
            ("PDE 2022 9 20 18 23 42.90 0 0 12 0 6 TEST", "2022-09-20T18:23:42.900000Z", 2.0, 1.0, 2.0, 3.0),
            ("PDEW2014 8 18 2 32 5.30 32.7000 47.6900 10.2 0.0 6.2 TEST", "2014-08-18T02:32:05.300000Z", 4.7, 32.59, 47.53, 12.0),
        )
        with tempfile.TemporaryDirectory() as raw:
            for index, (header, origin, shift, latitude, longitude, depth) in enumerate(cases):
                path = Path(raw) / f"CMTSOLUTION_{index}"
                path.write_text(header + "\n" +
                                f"time shift: {shift}\nhalf duration: 3.1\nlatitude: {latitude}\n"
                                f"longitude: {longitude}\ndepth: {depth}\n", encoding="utf-8")
                source = parse_cmtsolution(path)
                self.assertEqual(source.pde_origin_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), origin)
                self.assertAlmostEqual(source.time_shift_s, shift)
                self.assertAlmostEqual(source.latitude_deg, latitude)
                self.assertAlmostEqual(source.longitude_deg, longitude)
                self.assertAlmostEqual(source.depth_km, depth)
                self.assertAlmostEqual(source.centroid_source_time - source.pde_origin_time, shift)

    def test_cmt_stations_and_time_shift(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            run = make_run(Path(raw))
            source = parse_cmtsolution(run / "DATA/CMTSOLUTION")
            stations = parse_stations(run / "DATA/STATIONS")
            self.assertEqual(len(stations), 1)
            self.assertAlmostEqual(source.time_shift_s, 2.0)
            self.assertAlmostEqual(source.centroid_source_time - source.pde_origin_time, 2.0)
            _, rows, _ = annotate_run(run, input_format="asdf")
            p = next(row for row in rows if row["requested_phase"] == "P" and row["component"] == "BXE")
            self.assertEqual(p["status"], "ok")
            self.assertEqual(p["cmtsolution_half_duration_s"], "9.000000000")
            self.assertEqual(p["cmtsolution_time_shift_s"], "2.000000000")
            self.assertAlmostEqual(UTCDateTime(p["base_arrival_time_utc"]) - source.centroid_source_time,
                                   float(p["travel_time_s"]), places=5)

    def test_phase_availability_and_missing(self) -> None:
        model = TauPyModel(model="prem")
        near = {phase: model.get_travel_times(12, 90, phase_list=[phase]) for phase in ("P", "Pdiff", "S", "Sdiff", "PP", "SKS", "SS")}
        far = {phase: model.get_travel_times(12, 135, phase_list=[phase]) for phase in ("P", "Pdiff", "S", "Sdiff", "PP", "SKS", "SS")}
        self.assertTrue(near["P"] and not near["Pdiff"] and near["S"] and not near["Sdiff"])
        self.assertTrue(not far["P"] and far["Pdiff"] and not far["S"] and far["Sdiff"])
        self.assertTrue(all(near[phase] for phase in ("PP", "SKS", "SS")))

    def test_sidecar_payload_unchanged_and_readback(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); run = make_run(root); source_file = run / "OUTPUT_FILES/synthetic.h5"
            before = hashlib.sha256(source_file.read_bytes()).hexdigest()
            _, rows, _ = annotate_run(run, input_format="asdf")
            out = root / "annotation"; sidecar, csv_path = write_outputs(out, rows, {"test": True})
            self.assertEqual(rows, read_sidecar(sidecar))
            self.assertTrue(csv_path.is_file())
            self.assertEqual(before, hashlib.sha256(source_file.read_bytes()).hexdigest())
            with h5py.File(sidecar, "r") as handle:
                self.assertNotIn("Waveforms", handle)
                self.assertIn("AuxiliaryData/TheoreticalArrivals/AX_STA/data", handle)
            with self.assertRaises(FileExistsError):
                write_outputs(out, rows, {"test": True})
            write_outputs(out, rows, {"test": True}, overwrite=True)
            parsed = build_parser().parse_args([str(run), "--resume"])
            self.assertTrue(parsed.resume)

    def test_asdf_sac_consistency_and_recomputed_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            origin = UTCDateTime(2022, 9, 20, 18, 23, 42.90)
            run = make_run(Path(raw), asdf=True, sac=True, asdf_start=origin - 0.75, sac_start=origin + 1.25)
            _, asdf_rows, _ = annotate_run(run, input_format="asdf", stf_time_shift_s=3.0)
            _, sac_rows, _ = annotate_run(run, input_format="sac", stf_time_shift_s=3.0)
            a = next(row for row in asdf_rows if row["requested_phase"] == "P" and row["component"] == "BXE")
            s = next(row for row in sac_rows if row["requested_phase"] == "P" and row["component"] == "BXE")
            self.assertEqual(a["travel_time_s"], s["travel_time_s"])
            self.assertEqual(a["effective_arrival_time_utc"], s["effective_arrival_time_utc"])
            self.assertAlmostEqual(float(a["arrival_from_trace_start_s"]) - float(s["arrival_from_trace_start_s"]), 2.0, places=5)
            _, unshifted, _ = annotate_run(run, input_format="asdf", stf_time_shift_s=0.0)
            u = next(row for row in unshifted if row["requested_phase"] == "P" and row["component"] == "BXE")
            self.assertAlmostEqual(float(a["arrival_from_trace_start_s"]) - float(u["arrival_from_trace_start_s"]), 3.0, places=5)
            with self.assertRaises(ValueError):
                detect_format(run, "auto")

    def test_sac_pick_copies_leave_original_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); run = make_run(root, asdf=False, sac=True)
            original = next((run / "OUTPUT_FILES").glob("*.sac"))
            before = hashlib.sha256(original.read_bytes()).hexdigest()
            _, rows, traces = annotate_run(run, input_format="sac")
            target = write_sac_picks(root / "annotation", rows, traces)
            copied = target / original.name
            self.assertTrue(copied.is_file())
            self.assertEqual(before, hashlib.sha256(original.read_bytes()).hexdigest())
            self.assertNotEqual(read(str(copied))[0].stats.sac.t0, -12345.0)

    def test_v1_csv_normalizes_and_derived_rows_preserve_base_physics(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); run = make_run(root, cmt_shift=2.0)
            _, rows, traces = annotate_run(run, input_format="asdf")
            legacy = [{field: row[field] for field in V1_CSV_FIELDS} for row in rows]
            for row in legacy:
                row["schema_version"] = V1_SCHEMA_VERSION
            csv_path = root / "v1.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=V1_CSV_FIELDS); writer.writeheader(); writer.writerows(legacy)
            normalized = read_csv(csv_path)
            self.assertEqual(normalized[0]["input_schema_version"], V1_SCHEMA_VERSION)
            trace = traces[0]
            derived = derive_convolved_rows(
                normalized,
                [TraceAxis(trace.source_path, "/Waveforms/AX.STA/output", trace.starttime.timestamp + 3.0,
                           trace.sampling_rate_hz, trace.npts)],
                applied_stf_time_shift_s=3.0,
                stf_reference="explicit_overall_shift_relative_to_stf_coordinate_zero",
                stf_provenance={"test": True},
            )
            p = next(row for row in derived if row["requested_phase"] == "P" and row["component"] == "BXE")
            base = next(row for row in normalized if row["requested_phase"] == "P" and row["component"] == "BXE")
            self.assertEqual(p["travel_time_s"], base["travel_time_s"])
            self.assertEqual(p["taup_model"], base["taup_model"])
            self.assertEqual(p["trace_starttime_utc"], base["trace_starttime_utc"])
            self.assertEqual(p["total_stf_time_shift_s"], "3.000000000")
            self.assertAlmostEqual(float(p["effective_arrival_from_trace_start_s"]),
                                   float(base["arrival_from_trace_start_s"]), places=5)
            missing = next(row for row in derived if row["requested_phase"] == "Pdiff")
            self.assertEqual(missing["status"], "missing")
            self.assertEqual(missing["effective_arrival_time_utc"], "")
            self.assertEqual(tuple(p), CSV_FIELDS)

    def test_annotation_reader_allows_single_artifact_and_rejects_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); run = make_run(root)
            _, rows, _ = annotate_run(run, input_format="asdf")
            csv_only = root / "csv_only"; sidecar, _ = write_outputs(csv_only, rows, {"test": True})
            sidecar.unlink()
            self.assertEqual(read_annotation(csv_only), rows)
            h5_only = root / "h5_only"; _, csv_path = write_outputs(h5_only, rows, {"test": True})
            csv_path.unlink()
            self.assertEqual(read_annotation(h5_only), rows)
            mismatch = root / "mismatch"; _, csv_path = write_outputs(mismatch, rows, {"test": True})
            csv_path.write_text(csv_path.read_text(encoding="utf-8").replace("prem", "other", 1), encoding="utf-8")
            with self.assertRaises(ValueError, msg="CSV/HDF5 mismatch must be rejected"):
                read_annotation(mismatch)


if __name__ == "__main__":
    unittest.main()
