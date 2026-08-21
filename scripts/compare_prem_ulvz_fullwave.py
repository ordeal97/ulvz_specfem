#!/usr/bin/env python3
"""Compare raw SPECFEM ASCII A/B synthetics for the PREM ULVZ validation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from obspy.taup import TauPyModel


def read_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] != 2 or not np.isfinite(data).all():
        raise ValueError(f"invalid non-finite/two-column ASCII trace: {path}")
    return data[:, 0], data[:, 1]


def metrics(reference: np.ndarray, trial: np.ndarray, dt: float) -> dict[str, float]:
    difference = trial - reference
    reference_energy, trial_energy = np.dot(reference, reference), np.dot(trial, trial)
    denom = np.sqrt(reference_energy * trial_energy)
    zero_cc = float(np.dot(reference, trial) / denom) if denom else float("nan")
    correlation = np.correlate(trial, reference, mode="full")
    lags = np.arange(-(len(reference) - 1), len(reference))
    index = int(np.argmax(np.abs(correlation)))
    lag = int(lags[index])
    if lag > 0:
        aligned_ref, aligned_trial = reference[:-lag], trial[lag:]
    elif lag < 0:
        aligned_ref, aligned_trial = reference[-lag:], trial[:lag]
    else:
        aligned_ref, aligned_trial = reference, trial
    aligned_denom = np.sqrt(np.dot(aligned_ref, aligned_ref) * np.dot(aligned_trial, aligned_trial))
    return {"zero_lag_cc": zero_cc, "optimal_cc": float(np.dot(aligned_ref, aligned_trial) / aligned_denom) if aligned_denom else float("nan"),
            "optimal_lag_s": lag * dt, "nrms": float(np.sqrt(np.mean(difference**2)) / np.sqrt(np.mean(reference**2))) if reference_energy else float("nan"),
            "peak_amplitude_ratio": float(np.max(np.abs(trial)) / np.max(np.abs(reference))) if np.max(np.abs(reference)) else float("nan"),
            "rms_ratio": float(np.sqrt(np.mean(trial**2)) / np.sqrt(np.mean(reference**2))) if reference_energy else float("nan"),
            "energy_ratio": float(trial_energy / reference_energy) if reference_energy else float("nan"),
            "normalized_difference_energy": float(np.dot(difference, difference) / reference_energy) if reference_energy else float("nan")}


def window_indices(time: np.ndarray, start: float, end: float) -> np.ndarray:
    indices = np.flatnonzero((time >= start) & (time <= end))
    if len(indices) < 3:
        raise ValueError(f"window {start:.2f}-{end:.2f}s has fewer than three samples")
    return indices


def save_plot(path: Path, time: np.ndarray, reference: np.ndarray, trial: np.ndarray, title: str, windows: dict[str, tuple[float, float]]) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(11, 5), sharex=True, constrained_layout=True)
    axes[0].plot(time, reference, label="A: ULVZ disabled", lw=0.8)
    axes[0].plot(time, trial, label="B: ULVZ enabled", lw=0.8, alpha=0.8)
    axes[1].plot(time, trial - reference, color="black", lw=0.7, label="B - A")
    for name, (start, end) in windows.items():
        for axis in axes:
            axis.axvspan(start, end, alpha=0.12, label=name if axis is axes[0] else None)
    axes[0].set_title(title); axes[0].set_ylabel("displacement")
    axes[1].set_ylabel("residual"); axes[1].set_xlabel("time (s)")
    axes[0].legend(ncol=4, fontsize=8); figure.savefig(path, dpi=150); plt.close(figure)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, help="new comparison subdirectory; defaults to comparison")
    args = parser.parse_args()
    root = args.result_root.resolve()
    output = (args.output_dir if args.output_dir else root / "comparison").resolve()
    output.mkdir(exist_ok=False); figures = output / "figures"; figures.mkdir()
    stations = list(csv.DictReader((root / "station_geometry.csv").open(encoding="utf-8")))
    disabled, enabled = root / "A_disabled/OUTPUT_FILES", root / "B_enabled/OUTPUT_FILES"
    a_files, b_files = {path.name: path for path in disabled.glob("*.sem.ascii")}, {path.name: path for path in enabled.glob("*.sem.ascii")}
    if set(a_files) != set(b_files) or not a_files:
        raise RuntimeError("A/B station/component files are missing or do not match")
    station_names = {row["name"] for row in stations}
    if {name.split(".")[1] for name in a_files} != station_names:
        raise RuntimeError("waveform station set does not match station_geometry.csv")
    model = TauPyModel("prem")
    rows: list[dict] = []; axis_audit: list[dict] = []; z_traces: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, dict]] = {}
    for filename in sorted(a_files):
        network, station, component, _, _ = filename.split(".")
        time_a, data_a = read_trace(a_files[filename]); time_b, data_b = read_trace(b_files[filename])
        if len(time_a) != len(time_b) or not np.array_equal(time_a, time_b):
            raise RuntimeError(f"non-identical A/B time axis: {filename}")
        dt = float(np.median(np.diff(time_a)))
        # SPECFEM ASCII time stamps are formatted at finite decimal precision;
        # accept only that printed-time quantization, while retaining exact A/B axes.
        if not np.allclose(np.diff(time_a), dt, rtol=0.0, atol=max(1e-4, abs(dt) * 1e-3)):
            raise RuntimeError(f"non-uniform sampling: {filename}")
        geometry = next(row for row in stations if row["name"] == station)
        distance, ptime, stime = float(geometry["source_distance_deg"]), float(geometry["p_diff_s"]), float(geometry["s_diff_s"])
        arrivals = {item.name: item.time for item in model.get_travel_times(208.6, distance, ["Pdiff", "Sdiff"])}
        if "Pdiff" not in arrivals or "Sdiff" not in arrivals or abs(arrivals["Pdiff"] - ptime) > 1e-4 or abs(arrivals["Sdiff"] - stime) > 1e-4:
            raise RuntimeError(f"TauP/PREM arrival audit failed: {station}")
        windows = {"full": (float(time_a[0]), float(time_a[-1])), "Pdiff": (ptime - 50.0, ptime + 50.0),
                   "Sdiff": (stime - 50.0, stime + 50.0), "Sdiff_postcursor_240s": (stime, stime + 240.0)}
        if windows["Sdiff_postcursor_240s"][1] > time_a[-1]:
            raise RuntimeError(f"record does not cover 240 s Sdiff postcursor: {filename}")
        for label, (start, end) in windows.items():
            idx = window_indices(time_a, start, end)
            row = {"filename": filename, "network": network, "station": station, "component": component,
                   "path_class": geometry["path_class"], "window": label, "window_start_s": start, "window_end_s": end,
                   "samples": len(idx), **metrics(data_a[idx], data_b[idx], dt)}
            rows.append(row)
        axis_audit.append({"filename": filename, "samples": len(time_a), "dt_s": dt, "time_start_s": time_a[0], "time_end_s": time_a[-1], "format": "two-column SPECFEM ASCII", "units": "displacement"})
        save_plot(figures / f"{filename}.png", time_a, data_a, data_b, filename, {key: value for key, value in windows.items() if key != "full"})
        if component == "MXZ":
            z_traces[station] = (time_a, data_a, data_b, geometry)
    write_csv(output / "station_level_metrics.csv", rows)
    write_csv(output / "waveform_axis_audit.csv", axis_audit)
    summaries: list[dict] = []
    for path_class in sorted({row["path_class"] for row in rows}):
        for window in sorted({row["window"] for row in rows}):
            selection = [row for row in rows if row["path_class"] == path_class and row["window"] == window]
            summaries.append({"path_class": path_class, "window": window, "traces": len(selection),
                              "mean_normalized_difference_energy": float(np.mean([float(row["normalized_difference_energy"]) for row in selection])),
                              "median_optimal_cc": float(np.median([float(row["optimal_cc"]) for row in selection]))})
    write_csv(output / "path_class_summary.csv", summaries)
    full = [row for row in rows if row["window"] == "full"]
    anomalies: list[dict] = []
    if full and max(float(row["normalized_difference_energy"]) for row in full) < 1e-12:
        anomalies.append({"flag": "nearly_zero_difference_all_stations", "detail": "all full-record normalized difference energies are <1e-12"})
    means = {item["path_class"]: item["mean_normalized_difference_energy"] for item in summaries if item["window"] == "full"}
    if "far" in means and "near_through" in means and means["far"] > means["near_through"]:
        anomalies.append({"flag": "far_exceeds_near", "detail": "far full-record mean difference energy exceeds near/through"})
    if full and np.ptp([float(row["optimal_lag_s"]) for row in full]) <= max(float(axis_audit[0]["dt_s"]), 1e-8) and np.ptp([float(row["peak_amplitude_ratio"]) for row in full]) < 1e-5:
        anomalies.append({"flag": "common_lag_and_amplitude_ratio", "detail": "all full traces have effectively identical lag and peak ratio"})
    for station in stations:
        if float(station["boundary_margin_deg"]) < 25.0:
            anomalies.append({"flag": "boundary_proximate_station", "detail": f"{station['name']} margin={station['boundary_margin_deg']} deg"})
    write_csv(output / "anomalous_stations.csv", anomalies or [{"flag": "none", "detail": "no predefined anomaly triggered"}])
    ordered = sorted(z_traces, key=lambda station: z_traces[station][3]["path_class"])
    overview, axes = plt.subplots(len(ordered), 2, figsize=(12, 2.8 * len(ordered)), sharex="col", constrained_layout=True)
    for index, station in enumerate(ordered):
        time, reference, trial, geometry = z_traces[station]
        axes[index, 0].plot(time, reference, lw=0.7, label="A disabled")
        axes[index, 0].plot(time, trial, lw=0.7, label="B enabled")
        axes[index, 0].set_ylabel(f"{geometry['path_class']}\\n{station}")
        axes[index, 1].plot(time, trial - reference, lw=0.7, color="black")
        axes[index, 1].set_ylabel("B - A")
    axes[0, 0].legend(fontsize=8); axes[0, 0].set_title("raw MXZ overlay by path class"); axes[0, 1].set_title("raw MXZ residual by path class")
    axes[-1, 0].set_xlabel("time (s)"); axes[-1, 1].set_xlabel("time (s)")
    overview.savefig(figures / "path_class_mxz_overview.png", dpi=150); plt.close(overview)
    phase, axes = plt.subplots(len(ordered), 2, figsize=(12, 2.8 * len(ordered)), sharex=False, constrained_layout=True)
    for index, station in enumerate(ordered):
        time, reference, trial, geometry = z_traces[station]
        for column, (label, arrival_key) in enumerate((("Pdiff", "p_diff_s"), ("Sdiff", "s_diff_s"))):
            center = float(geometry[arrival_key]); mask = (time >= center - 50.0) & (time <= center + 50.0)
            axes[index, column].plot(time[mask], reference[mask], lw=0.8, label="A disabled")
            axes[index, column].plot(time[mask], trial[mask], lw=0.8, label="B enabled")
            axes[index, column].set_ylabel(f"{geometry['path_class']}\\n{station}")
            axes[index, column].set_title(label if index == 0 else "")
    axes[0, 0].legend(fontsize=8); axes[-1, 0].set_xlabel("time (s)"); axes[-1, 1].set_xlabel("time (s)")
    phase.savefig(figures / "pdiff_sdiff_mxz_windows.png", dpi=150); plt.close(phase)
    (output / "comparison_metadata.json").write_text(json.dumps({"processing": "raw ASCII only; no filtering or observational fitting", "taup_model": "prem", "time_axes_identical": True, "station_count": len(stations), "trace_count": len(a_files)}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
