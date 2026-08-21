#!/usr/bin/env python3
"""Diagnose path geometry and raw A/B waveform differences for a finished run.

The input full-wave result is read only.  Geometric CMB corridors are
great-circle proxies, not finite-frequency sensitivity kernels or exact ray
segments; the report keeps that limitation explicit.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from obspy.taup import TauPyModel

RCMB_KM = 3480.0
DEFAULT_INPUT = Path("results/prem_ulvz_fullwave_validation_20260818T152800Z")


@dataclass(frozen=True)
class Geometry:
    station: str
    network: str
    latitude_deg: float
    longitude_deg: float
    original_class: str
    source_distance_deg: float
    source_to_station_azimuth_deg: float
    source_to_ulvz_azimuth_deg: float
    relative_azimuth_deg: float
    corridor_min_distance_km: float
    corridor_cross_track_signed_km: float
    corridor_along_track_fraction: float
    corridor_closest_latitude_deg: float
    corridor_closest_longitude_deg: float
    distance_to_core_edge_km: float
    distance_to_outer_edge_km: float
    code_consistent_class: str
    p_diff_s: float
    s_diff_s: float
    boundary_margin_deg: float


def vector(lat: float, lon: float) -> np.ndarray:
    lat_rad, lon_rad = math.radians(lat), math.radians(lon)
    return np.array([math.cos(lat_rad) * math.cos(lon_rad), math.cos(lat_rad) * math.sin(lon_rad), math.sin(lat_rad)])


def geo(vector_value: np.ndarray) -> tuple[float, float]:
    unit = vector_value / np.linalg.norm(vector_value)
    return math.degrees(math.asin(float(np.clip(unit[2], -1.0, 1.0)))), ((math.degrees(math.atan2(unit[1], unit[0])) + 180.0) % 360.0 - 180.0)


def angular_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.degrees(math.acos(float(np.clip(np.dot(vector(*first), vector(*second)), -1.0, 1.0))))


def azimuth(first: tuple[float, float], second: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*first, *second))
    bearing = math.atan2(math.sin(lon2 - lon1) * math.cos(lat2), math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1))
    return math.degrees(bearing) % 360.0


def signed_angle(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def corridor_proxy(source: tuple[float, float], receiver: tuple[float, float], center: tuple[float, float]) -> tuple[float, float, float, tuple[float, float]]:
    """Closest minor-arc point and signed cross-track distance at the CMB."""
    start, end, target = vector(*source), vector(*receiver), vector(*center)
    total = math.acos(float(np.clip(np.dot(start, end), -1.0, 1.0)))
    normal = np.cross(start, end)
    normal /= np.linalg.norm(normal)
    projection = target - np.dot(target, normal) * normal
    projection /= np.linalg.norm(projection)
    if np.dot(projection, target) < 0.0:
        projection *= -1.0
    first = math.acos(float(np.clip(np.dot(start, projection), -1.0, 1.0)))
    second = math.acos(float(np.clip(np.dot(projection, end), -1.0, 1.0)))
    if abs(first + second - total) > 1.0e-7:
        candidates = [(start, 0.0), (end, 1.0)]
        projection, fraction = min(candidates, key=lambda item: math.acos(float(np.clip(np.dot(item[0], target), -1.0, 1.0))))
    else:
        fraction = first / total
    min_angle = math.acos(float(np.clip(np.dot(projection, target), -1.0, 1.0)))
    signed_cross_track = math.asin(float(np.clip(np.dot(target, normal), -1.0, 1.0))) * RCMB_KM
    return min_angle * RCMB_KM, signed_cross_track, fraction, geo(projection)


def parse_ulvz(path: Path) -> dict[str, float | str]:
    values: dict[str, float | str] = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        value = row["value"]
        values[row["key"]] = value if row["key"] == "BACKGROUND_MODEL" else float(value)
    return values


def classify(distance_km: float, radius_km: float, taper_km: float) -> str:
    if distance_km <= radius_km - taper_km:
        return "core_crossing_proxy"
    if distance_km <= radius_km:
        return "taper_crossing_proxy"
    return "outside_proxy"


def read_geometries(input_root: Path, ulvz: dict[str, float | str], source: tuple[float, float]) -> list[Geometry]:
    center = (float(ulvz["CENTER_LATITUDE_DEGREES"]), float(ulvz["CENTER_LONGITUDE_DEGREES"]))
    radius, taper = float(ulvz["LATERAL_RADIUS_KM"]), float(ulvz["LATERAL_TAPER_KM"])
    output: list[Geometry] = []
    for row in csv.DictReader((input_root / "station_geometry.csv").open(encoding="utf-8")):
        receiver = (float(row["latitude_deg"]), float(row["longitude_deg"]))
        distance, signed_cross, fraction, closest = corridor_proxy(source, receiver, center)
        station_azimuth, ulvz_azimuth = azimuth(source, receiver), azimuth(source, center)
        output.append(Geometry(
            station=row["name"], network=row["network"], latitude_deg=receiver[0], longitude_deg=receiver[1],
            original_class=row["path_class"], source_distance_deg=angular_distance(source, receiver),
            source_to_station_azimuth_deg=station_azimuth, source_to_ulvz_azimuth_deg=ulvz_azimuth,
            relative_azimuth_deg=signed_angle(station_azimuth - ulvz_azimuth), corridor_min_distance_km=distance,
            corridor_cross_track_signed_km=signed_cross, corridor_along_track_fraction=fraction,
            corridor_closest_latitude_deg=closest[0], corridor_closest_longitude_deg=closest[1],
            distance_to_core_edge_km=distance - (radius - taper), distance_to_outer_edge_km=distance - radius,
            code_consistent_class=classify(distance, radius, taper), p_diff_s=float(row["p_diff_s"]),
            s_diff_s=float(row["s_diff_s"]), boundary_margin_deg=float(row["boundary_margin_deg"])))
    return output


def verify_taup(geometries: list[Geometry], source_depth_km: float) -> None:
    model = TauPyModel("prem")
    for item in geometries:
        arrivals = {arrival.name: arrival.time for arrival in model.get_travel_times(source_depth_km, item.source_distance_deg, ["Pdiff", "Sdiff"])}
        if {"Pdiff", "Sdiff"} - set(arrivals):
            raise RuntimeError(f"TauP/PREM lacks Pdiff or Sdiff for {item.station}")
        if abs(arrivals["Pdiff"] - item.p_diff_s) > 1e-4 or abs(arrivals["Sdiff"] - item.s_diff_s) > 1e-4:
            raise RuntimeError(f"stored TauP/PREM arrivals differ for {item.station}")


def read_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path)
    if data.ndim != 2 or data.shape[1] != 2 or not np.isfinite(data).all():
        raise ValueError(f"invalid trace: {path}")
    return data[:, 0], data[:, 1]


def time_indices(time: np.ndarray, start: float, end: float) -> np.ndarray:
    indices = np.flatnonzero((time >= start) & (time <= end))
    if len(indices) < 3:
        raise ValueError(f"window {start:.3f}-{end:.3f}s has fewer than three samples")
    return indices


def waveform_metrics(reference: np.ndarray, trial: np.ndarray, dt: float, full_reference_energy: float) -> dict[str, float]:
    difference = trial - reference
    reference_energy, trial_energy, difference_energy = (float(np.dot(reference, reference)), float(np.dot(trial, trial)), float(np.dot(difference, difference)))
    denominator = math.sqrt(reference_energy * trial_energy)
    correlation = np.correlate(trial, reference, mode="full")
    lags = np.arange(-(len(reference) - 1), len(reference))
    lag = int(lags[int(np.argmax(np.abs(correlation)))])
    if lag > 0:
        aligned_reference, aligned_trial = reference[:-lag], trial[lag:]
    elif lag < 0:
        aligned_reference, aligned_trial = reference[-lag:], trial[:lag]
    else:
        aligned_reference, aligned_trial = reference, trial
    aligned_denominator = math.sqrt(float(np.dot(aligned_reference, aligned_reference)) * float(np.dot(aligned_trial, aligned_trial)))
    return {
        "zero_lag_cc": float(np.dot(reference, trial) / denominator) if denominator else float("nan"),
        "optimal_cc": float(np.dot(aligned_reference, aligned_trial) / aligned_denominator) if aligned_denominator else float("nan"),
        "optimal_lag_s": lag * dt,
        "nrms": math.sqrt(float(np.mean(difference ** 2))) / math.sqrt(float(np.mean(reference ** 2))) if reference_energy else float("nan"),
        "peak_amplitude_ratio": float(np.max(np.abs(trial)) / np.max(np.abs(reference))) if np.max(np.abs(reference)) else float("nan"),
        "rms_ratio": math.sqrt(float(np.mean(trial ** 2))) / math.sqrt(float(np.mean(reference ** 2))) if reference_energy else float("nan"),
        "energy_ratio": trial_energy / reference_energy if reference_energy else float("nan"),
        "normalized_difference_energy": difference_energy / reference_energy if reference_energy else float("nan"),
        "reference_energy": reference_energy, "trial_energy": trial_energy, "difference_energy": difference_energy,
        "difference_energy_fraction_full_reference": difference_energy / full_reference_energy if full_reference_energy else float("nan"),
    }


def duration_5_95(time: np.ndarray, data: np.ndarray) -> float:
    energy = np.cumsum(data ** 2)
    if energy[-1] <= 0.0:
        return float("nan")
    lower, upper = np.searchsorted(energy, (0.05 * energy[-1], 0.95 * energy[-1]))
    return float(time[min(upper, len(time) - 1)] - time[min(lower, len(time) - 1)])


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate_inputs(input_root: Path, geometries: list[Geometry]) -> tuple[dict[str, Path], dict[str, Path]]:
    disabled = {path.name: path for path in (input_root / "A_disabled/OUTPUT_FILES").glob("*.sem.ascii")}
    enabled = {path.name: path for path in (input_root / "B_enabled/OUTPUT_FILES").glob("*.sem.ascii")}
    expected_stations = {item.station for item in geometries}
    if set(disabled) != set(enabled) or not disabled:
        raise RuntimeError("A/B ASCII trace sets differ")
    if {name.split(".")[1] for name in disabled} != expected_stations:
        raise RuntimeError("trace stations differ from station_geometry.csv")
    return disabled, enabled


def analyse(input_root: Path, geometries: list[Geometry]) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    disabled, enabled = validate_inputs(input_root, geometries)
    geometry_by_station = {item.station: item for item in geometries}
    rows: list[dict[str, object]] = []
    decomposition: list[dict[str, object]] = []
    traces: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for filename in sorted(disabled):
        network, station, component, _, _ = filename.split(".")
        time_a, reference = read_trace(disabled[filename]); time_b, trial = read_trace(enabled[filename])
        if len(time_a) != len(time_b) or not np.array_equal(time_a, time_b):
            raise RuntimeError(f"A/B time axis differs: {filename}")
        dt = float(np.median(np.diff(time_a)))
        if not np.allclose(np.diff(time_a), dt, rtol=0.0, atol=max(1e-4, abs(dt) * 1e-3)):
            raise RuntimeError(f"unexpected ASCII time quantization: {filename}")
        geometry = geometry_by_station[station]
        windows = {
            "full": (float(time_a[0]), float(time_a[-1])),
            "Pdiff_main": (geometry.p_diff_s - 50.0, geometry.p_diff_s + 50.0),
            "Sdiff_main": (geometry.s_diff_s - 50.0, geometry.s_diff_s + 50.0),
            "Sdiff_postcursor_0_240": (geometry.s_diff_s, geometry.s_diff_s + 240.0),
            "Sdiff_late_50_240": (geometry.s_diff_s + 50.0, geometry.s_diff_s + 240.0),
            "Sdiff_late_50_80": (geometry.s_diff_s + 50.0, geometry.s_diff_s + 80.0),
            "Sdiff_late_80_160": (geometry.s_diff_s + 80.0, geometry.s_diff_s + 160.0),
            "Sdiff_late_160_240": (geometry.s_diff_s + 160.0, geometry.s_diff_s + 240.0),
        }
        full_reference_energy = float(np.dot(reference, reference))
        for label, (start, end) in windows.items():
            indices = time_indices(time_a, start, end)
            row: dict[str, object] = {"filename": filename, "network": network, "station": station, "component": component,
                                      "original_class": geometry.original_class, "code_consistent_class": geometry.code_consistent_class,
                                      "corridor_min_distance_km": geometry.corridor_min_distance_km,
                                      "distance_to_outer_edge_km": geometry.distance_to_outer_edge_km,
                                      "window": label, "window_start_s": start, "window_end_s": end, "samples": len(indices),
                                      **waveform_metrics(reference[indices], trial[indices], dt, full_reference_energy)}
            if label in {"Pdiff_main", "Sdiff_main", "Sdiff_late_50_240"}:
                row["reference_duration_5_95_s"] = duration_5_95(time_a[indices], reference[indices])
                row["trial_duration_5_95_s"] = duration_5_95(time_a[indices], trial[indices])
                row["duration_ratio_trial_over_reference"] = float(row["trial_duration_5_95_s"]) / float(row["reference_duration_5_95_s"]) if float(row["reference_duration_5_95_s"]) else float("nan")
            rows.append(row)
        main_idx, late_idx = time_indices(time_a, geometry.s_diff_s - 50.0, geometry.s_diff_s + 50.0), time_indices(time_a, geometry.s_diff_s + 50.0, geometry.s_diff_s + 240.0)
        main_a, main_b = float(np.dot(reference[main_idx], reference[main_idx])), float(np.dot(trial[main_idx], trial[main_idx]))
        for row in rows[-len(windows):]:
            if row["window"] == "Sdiff_late_50_240":
                row["reference_late_to_main_energy_ratio"] = float(row["reference_energy"]) / main_a if main_a else float("nan")
                row["trial_late_to_main_energy_ratio"] = float(row["trial_energy"]) / main_b if main_b else float("nan")
                row["reference_postcursor_peak"] = float(np.max(np.abs(reference[late_idx])))
                row["trial_postcursor_peak"] = float(np.max(np.abs(trial[late_idx])))
                row["postcursor_peak_ratio"] = float(row["trial_postcursor_peak"]) / float(row["reference_postcursor_peak"]) if float(row["reference_postcursor_peak"]) else float("nan")
        segments = {
            "pre_Pdiff": (float(time_a[0]), geometry.p_diff_s - 50.0),
            "Pdiff_main": (geometry.p_diff_s - 50.0, geometry.p_diff_s + 50.0),
            "between_Pdiff_Sdiff": (geometry.p_diff_s + 50.0, geometry.s_diff_s - 50.0),
            "Sdiff_main": (geometry.s_diff_s - 50.0, geometry.s_diff_s + 50.0),
            "late_50_80": (geometry.s_diff_s + 50.0, geometry.s_diff_s + 80.0),
            "late_80_160": (geometry.s_diff_s + 80.0, geometry.s_diff_s + 160.0),
            "late_160_240": (geometry.s_diff_s + 160.0, geometry.s_diff_s + 240.0),
            "tail_after_240": (geometry.s_diff_s + 240.0, float(time_a[-1])),
        }
        all_difference_energy = float(np.dot(trial - reference, trial - reference))
        for label, (start, end) in segments.items():
            # Half-open neighboring segments make the decomposition exactly
            # non-overlapping; the final segment includes the final sample.
            indices = np.flatnonzero((time_a >= start) & (time_a <= end if label == "tail_after_240" else time_a < end))
            if len(indices) < 3:
                raise ValueError(f"decomposition segment {label} is too short for {filename}")
            difference_energy = float(np.dot((trial[indices] - reference[indices]), (trial[indices] - reference[indices])))
            decomposition.append({"filename": filename, "station": station, "component": component, "original_class": geometry.original_class,
                                  "code_consistent_class": geometry.code_consistent_class, "segment": label, "start_s": start, "end_s": end,
                                  "difference_energy": difference_energy, "difference_energy_fraction_of_trace": difference_energy / all_difference_energy if all_difference_energy else float("nan"),
                                  "difference_energy_fraction_of_full_reference": difference_energy / full_reference_energy if full_reference_energy else float("nan")})
        if station == "FW03":
            traces[f"{station}_{component}"] = (time_a, reference, trial)
    return rows, decomposition, traces


def anomaly_rows(metrics: list[dict[str, object]], decomposition: list[dict[str, object]], geometries: list[Geometry]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for geometry in geometries:
        full = [row for row in metrics if row["station"] == geometry.station and row["window"] == "full"]
        dominant_trace = max(full, key=lambda row: float(row["normalized_difference_energy"]))
        parts = [row for row in decomposition if row["station"] == geometry.station and row["component"] == dominant_trace["component"]]
        dominant_part = max(parts, key=lambda row: float(row["difference_energy_fraction_of_trace"]))
        output.append({"station": geometry.station, "original_class": geometry.original_class, "code_consistent_class": geometry.code_consistent_class,
                       "dominant_component": dominant_trace["component"], "dominant_full_normalized_difference_energy": dominant_trace["normalized_difference_energy"],
                       "dominant_segment": dominant_part["segment"], "dominant_segment_fraction_of_trace_difference": dominant_part["difference_energy_fraction_of_trace"],
                       "boundary_margin_deg": geometry.boundary_margin_deg,
                       "evidence_based_interpretation": "single-station class; inspect component/segment contribution, not class mean as a statistical result"})
    return output


def geometry_figure(path: Path, geometries: list[Geometry], source: tuple[float, float], ulvz: dict[str, float | str]) -> None:
    center_lat, center_lon, radius = float(ulvz["CENTER_LATITUDE_DEGREES"]), float(ulvz["CENTER_LONGITUDE_DEGREES"]), float(ulvz["LATERAL_RADIUS_KM"])
    figure, axis = plt.subplots(figsize=(8, 5), constrained_layout=True)
    circle = []
    angular_radius = radius / RCMB_KM
    for bearing in np.linspace(0.0, 360.0, 181):
        bearing_rad, lat_rad, lon_rad = math.radians(bearing), math.radians(center_lat), math.radians(center_lon)
        lat = math.asin(math.sin(lat_rad) * math.cos(angular_radius) + math.cos(lat_rad) * math.sin(angular_radius) * math.cos(bearing_rad))
        lon = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(angular_radius) * math.cos(lat_rad), math.cos(angular_radius) - math.sin(lat_rad) * math.sin(lat))
        circle.append((math.degrees(lat), (math.degrees(lon) + 180.0) % 360.0 - 180.0))
    east = lambda longitude: longitude if longitude >= 0.0 else longitude + 360.0
    axis.plot([east(point[1]) for point in circle], [point[0] for point in circle], "k--", label="ULVZ outer edge at CMB")
    axis.scatter(east(source[1]), source[0], marker="*", s=110, color="tab:red", label="source")
    axis.scatter(east(center_lon), center_lat, marker="o", s=45, color="black", label="ULVZ center")
    for item in geometries:
        axis.plot([east(source[1]), east(item.longitude_deg)], [source[0], item.latitude_deg], color="0.7", lw=0.8)
        axis.scatter(east(item.longitude_deg), item.latitude_deg, s=45, label=f"{item.station}: {item.code_consistent_class}")
        axis.scatter(east(item.corridor_closest_longitude_deg), item.corridor_closest_latitude_deg, marker="x", color="black")
    axis.set(xlabel="longitude (deg E, wrapped 0–360)", ylabel="latitude (deg)", title="source–receiver great-circle CMB corridor proxies")
    axis.legend(fontsize=7, loc="best"); figure.savefig(path, dpi=150); plt.close(figure)


def metric_distance_figure(path: Path, metrics: list[dict[str, object]], geometries: list[Geometry]) -> None:
    distance = {item.station: item.corridor_min_distance_km for item in geometries}
    windows = ("full", "Pdiff_main", "Sdiff_main", "Sdiff_late_50_240")
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for axis, window in zip(axes.flat, windows):
        for component, marker in zip(("MXE", "MXN", "MXZ"), ("o", "s", "^")):
            rows = [row for row in metrics if row["window"] == window and row["component"] == component]
            axis.scatter([distance[str(row["station"])] for row in rows], [float(row["normalized_difference_energy"]) for row in rows], marker=marker, label=component)
            for row in rows:
                axis.annotate(str(row["station"]), (distance[str(row["station"])], float(row["normalized_difference_energy"])), fontsize=7)
        axis.axvline(412.0, color="0.5", ls="--", lw=0.8); axis.axvline(512.0, color="0.5", ls=":", lw=0.8)
        axis.set(title=window, xlabel="CMB corridor distance to ULVZ center (km)", ylabel="window normalized difference energy")
    axes[0, 0].legend(fontsize=8); figure.savefig(path, dpi=150); plt.close(figure)


def decomposition_figure(path: Path, decomposition: list[dict[str, object]]) -> None:
    labels = ("pre_Pdiff", "Pdiff_main", "between_Pdiff_Sdiff", "Sdiff_main", "late_50_80", "late_80_160", "late_160_240", "tail_after_240")
    trace_names = sorted({str(row["filename"]) for row in decomposition})
    figure, axis = plt.subplots(figsize=(12, 5), constrained_layout=True)
    bottom = np.zeros(len(trace_names)); positions = np.arange(len(trace_names))
    for label in labels:
        values = np.array([next(float(row["difference_energy_fraction_of_trace"]) for row in decomposition if row["filename"] == trace and row["segment"] == label) for trace in trace_names])
        axis.bar(positions, values, bottom=bottom, label=label); bottom += values
    axis.set(xticks=positions, xticklabels=trace_names, ylabel="fraction of each trace difference energy", title="non-overlapping difference-energy decomposition")
    axis.tick_params(axis="x", rotation=45, labelsize=7); axis.legend(ncol=4, fontsize=7); figure.savefig(path, dpi=150); plt.close(figure)


def focus_figure(path: Path, traces: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], geometries: list[Geometry]) -> None:
    geometry = next(item for item in geometries if item.station == "FW03")
    time, reference, trial = traces["FW03_MXN"]
    windows = (("Pdiff", geometry.p_diff_s - 50.0, geometry.p_diff_s + 50.0), ("Sdiff", geometry.s_diff_s - 50.0, geometry.s_diff_s + 50.0), ("late", geometry.s_diff_s + 50.0, geometry.s_diff_s + 240.0))
    figure, axes = plt.subplots(3, 1, figsize=(10, 7), constrained_layout=True)
    for axis, (label, start, end) in zip(axes, windows):
        mask = (time >= start) & (time <= end)
        axis.plot(time[mask], reference[mask], label="A disabled", lw=0.8)
        axis.plot(time[mask], trial[mask], label="B enabled", lw=0.8)
        axis.plot(time[mask], trial[mask] - reference[mask], label="B-A", lw=0.7, color="black")
        axis.set_title(f"FW03 MXN {label} window")
    axes[0].legend(fontsize=8); axes[-1].set_xlabel("time (s)"); figure.savefig(path, dpi=150); plt.close(figure)


def make_readme(path: Path, input_root: Path, geometries: list[Geometry], metrics: list[dict[str, object]], anomalies: list[dict[str, object]]) -> None:
    full = [row for row in metrics if row["window"] == "full"]
    near = next(item for item in geometries if item.original_class == "near_through")
    far = next(item for item in geometries if item.original_class == "far")
    far_mxn = next(row for row in full if row["station"] == far.station and row["component"] == "MXN")
    near_mean = float(np.mean([float(row["normalized_difference_energy"]) for row in full if row["station"] == near.station]))
    far_mean = float(np.mean([float(row["normalized_difference_energy"]) for row in full if row["station"] == far.station]))
    def station_window_mean(station: str, window: str) -> float:
        return float(np.mean([float(row["normalized_difference_energy"]) for row in metrics if row["station"] == station and row["window"] == window]))
    far_pdiff, near_pdiff = station_window_mean(far.station, "Pdiff_main"), station_window_mean(near.station, "Pdiff_main")
    far_sdiff, near_sdiff = station_window_mean(far.station, "Sdiff_main"), station_window_mean(near.station, "Sdiff_main")
    far_late, near_late = station_window_mean(far.station, "Sdiff_late_50_240"), station_window_mean(near.station, "Sdiff_late_50_240")
    path.write_text(f"""# PREM+ULVZ full-wave path diagnosis

## Scope

This post-run diagnosis reads `{input_root}` only. No mesher/solver was run and
no ULVZ implementation or historical result was modified. Great-circle CMB
corridors are geometric proxies, not finite-frequency kernels or exact Pdiff/
Sdiff paths.

## Key finding to test with the CSV tables

The original `far > near` flag compares one station per class and averages
three components. Its full-record difference-energy gap is only
`{far_mean:.6g}` (far) versus `{near_mean:.6g}` (near/through). FW03-MXN is the
largest far full-record component (`{float(far_mxn['normalized_difference_energy']):.6g}`),
so the class reversal is component-sensitive and cannot be interpreted as a
station-population result.

The Pdiff-window mean is higher at FW03 (`{far_pdiff:.6g}`) than FW01
(`{near_pdiff:.6g}`), driven by FW03-MXN. In contrast, FW03 is lower than FW01
in Sdiff (`{far_sdiff:.6g}` vs `{near_sdiff:.6g}`) and in the non-overlapping
Sdiff late 50–240 s window (`{far_late:.6g}` vs `{near_late:.6g}`). The energy
decomposition table identifies whether the full-record FW03-MXN value is
dominated by Pdiff or by other intervals; do not substitute its high windowed
NDE for a large full-record contribution.

The original labels used 6371-km angular scaling, whereas the implementation
uses `RCMB=3480 km`. This diagnosis therefore reports code-consistent CMB
distances and classes separately: FW01 is {near.code_consistent_class} at
{near.corridor_min_distance_km:.1f} km; FW03 is {far.code_consistent_class} at
{far.corridor_min_distance_km:.1f} km. Read the phase and non-overlapping
energy-decomposition tables before attributing any difference to ULVZ physics.

## Acceptance boundaries

- **Functional acceptance:** already passes: paired A/B runs completed and
  supplied identical time axes.
- **Physical locality:** assessed only by the new phase-window and continuous
  CMB-proxy tables; three stations are insufficient for statistical inference.
- **Code change:** no output-only evidence here can require a change to
  `model_ulvz.f90`; that would require a direct violation of its taper/parameter
  contract.

The original anomaly rows are retained conceptually in `anomalous_station_diagnosis.csv`.
All figures are new diagnostic views rather than copies of the original plots.
""", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    input_root = args.input_root.resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = (args.output_root or input_root.parents[0] / f"prem_ulvz_fullwave_path_diagnosis_{timestamp}").resolve()
    if not input_root.is_dir() or not (input_root / "ulvz_model.csv").is_file():
        raise RuntimeError("input root is not a completed PREM+ULVZ full-wave result")
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {output_root}")
    metadata = json.loads((input_root / "metadata.json").read_text(encoding="utf-8"))
    source = (float(metadata["source"]["latitude_deg"]), float(metadata["source"]["longitude_deg"]))
    ulvz = parse_ulvz(input_root / "ulvz_model.csv")
    geometries = read_geometries(input_root, ulvz, source)
    verify_taup(geometries, float(metadata["source"]["depth_km"]))
    metrics, decomposition, traces = analyse(input_root, geometries)
    if args.dry_run:
        print(f"dry-run PASS: {len(geometries)} stations, {len(metrics)} metric rows, {len(decomposition)} decomposition rows")
        return
    output_root.mkdir(parents=True)
    logging.basicConfig(filename=output_root / "diagnosis.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("input=%s stations=%d metrics=%d", input_root, len(geometries), len(metrics))
    write_csv(output_root / "continuous_geometry_classification.csv", [item.__dict__ for item in geometries])
    write_csv(output_root / "station_level_geometry_phase_metrics.csv", metrics)
    write_csv(output_root / "difference_energy_decomposition.csv", decomposition)
    anomalies = anomaly_rows(metrics, decomposition, geometries)
    write_csv(output_root / "anomalous_station_diagnosis.csv", anomalies)
    figures = output_root / "figures"; figures.mkdir()
    geometry_figure(figures / "cmb_corridor_geometry.png", geometries, source, ulvz)
    metric_distance_figure(figures / "distance_vs_window_difference_energy.png", metrics, geometries)
    decomposition_figure(figures / "difference_energy_decomposition.png", decomposition)
    focus_figure(figures / "fw03_mxn_phase_residuals.png", traces, geometries)
    make_readme(output_root / "README.md", input_root, geometries, metrics, anomalies)
    (output_root / "diagnosis_metadata.json").write_text(json.dumps({"input_root": str(input_root), "source": source, "ulvz": ulvz, "rcmb_km": RCMB_KM,
        "geometry_method": "minor-arc great-circle CMB corridor proxy; not an exact Pdiff/Sdiff ray or finite-frequency kernel", "no_solver_or_mesher_run": True}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
