"""Great-circle and optional TauP ray-path adapters.

TauP phase paths are deliberately not used for external-boundary return times.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable

from two_chunk_planner.errors import PlannerError
from two_chunk_planner.geometry import angular_distance_deg, chord_length_km, great_circle_samples, latlon_to_unit, unit_to_latlon
from two_chunk_planner.io import Source, Station


@dataclass
class PathRecord:
    station_id: str
    phase: str | None
    requested_phase: str | None
    returned_phase: str | None
    mode: str
    points: list[tuple[float, float]]
    arrival_time_s: float | None
    raypath_length_km: float | None
    raypath_length_status: str
    maximum_sampled_depth_km: float | None
    cmb_near_proxy: dict | None
    metadata: dict

    def to_dict(self) -> dict:
        return asdict(self)


def geometry_path(source: Source, station: Station, samples: int = 181) -> PathRecord:
    points = [unit_to_latlon(item) for item in great_circle_samples(latlon_to_unit(source.latitude_deg, source.longitude_deg), latlon_to_unit(station.latitude_deg, station.longitude_deg), samples)]
    return PathRecord(station.identifier, None, None, None, "geometry-only", points, None, None, "not_applicable", None, None, {"sample_count": samples, "great_circle_distance_deg": angular_distance_deg(latlon_to_unit(source.latitude_deg, source.longitude_deg), latlon_to_unit(station.latitude_deg, station.longitude_deg))})


def geometry_paths(source: Source, stations: Iterable[Station], samples: int = 181) -> list[PathRecord]:
    return [geometry_path(source, station, samples) for station in stations]


def _field(path, name: str):
    if path.dtype.names is None or name not in path.dtype.names:
        raise PlannerError(f"TauP geographic ray path lacks required '{name}' samples")
    return path[name]


def _taup_samples(path, model_radius_km: float) -> list[tuple[float, float, float]]:
    latitudes, longitudes, depths = _field(path, "lat"), _field(path, "lon"), _field(path, "depth")
    samples = [(float(lat), float(lon), float(depth)) for lat, lon, depth in zip(latitudes, longitudes, depths)]
    if len(samples) < 2:
        raise PlannerError("TauP geographic ray path has fewer than two samples")
    for latitude, longitude, depth in samples:
        if not all(math.isfinite(value) for value in (latitude, longitude, depth)):
            raise PlannerError("TauP geographic ray path contains non-finite coordinates")
        if not -90.0 <= latitude <= 90.0 or not -360.0 <= longitude <= 360.0:
            raise PlannerError("TauP geographic ray path has latitude/longitude outside numeric range")
        if not 0.0 <= depth <= model_radius_km:
            raise PlannerError("TauP geographic ray path has depth outside the model radius")
    return samples


def _cmb_near_proxy(samples: list[tuple[float, float, float]], depth_tolerance_km: float) -> dict:
    maximum_depth = max(item[2] for item in samples)
    selected = [item for item in samples if item[2] >= maximum_depth - depth_tolerance_km]
    return {
        "kind": "maximum_sampled_depth_proxy_not_physical_boundary",
        "approximation": True,
        "depth_tolerance_km": depth_tolerance_km,
        "reference_depth_km": maximum_depth,
        "sample_count": len(selected),
        "segment_samples": [
            {"latitude_deg": latitude, "longitude_deg": longitude, "depth_km": depth}
            for latitude, longitude, depth in selected
        ],
    }


def taup_paths(source: Source, stations: Iterable[Station], phases: list[str], model_name: str, resample: bool, ray_param_tol: float, allow_partial: bool = False, cmb_near_depth_tolerance_km: float = 25.0) -> tuple[list[PathRecord], list[dict]]:
    try:
        from obspy.taup import TauPyModel
    except ImportError as exc:
        raise PlannerError("phase-aware mode requires optional dependency obspy") from exc
    if cmb_near_depth_tolerance_km < 0.0:
        raise PlannerError("CMB-near proxy depth tolerance must be non-negative")
    model = TauPyModel(model_name)
    model_radius_km = float(model.model.radius_of_planet)
    records: list[PathRecord] = []
    missing: list[dict] = []
    for station in stations:
        for phase in phases:
            try:
                arrivals = model.get_ray_paths_geo(
                    source.depth_km, source.latitude_deg, source.longitude_deg, station.latitude_deg, station.longitude_deg,
                    phase_list=[phase], resample=resample, ray_param_tol=ray_param_tol,
                )
            except (ValueError, KeyError) as exc:
                missing.append({"station_id": station.identifier, "requested_phase": phase, "reason": f"TauP request failed: {exc}"})
                continue
            candidates = [arrival for arrival in arrivals if arrival.name == phase]
            if not candidates:
                missing.append({"station_id": station.identifier, "requested_phase": phase, "reason": "no_matching_taup_arrival"})
                continue
            arrival = min(candidates, key=lambda item: item.time)
            path = arrival.path
            try:
                samples = _taup_samples(path, model_radius_km)
            except PlannerError as exc:
                missing.append({"station_id": station.identifier, "requested_phase": phase, "reason": str(exc)})
                continue
            raypath_length_km = chord_length_km(samples)
            if not math.isfinite(raypath_length_km) or raypath_length_km <= 0.0:
                missing.append({"station_id": station.identifier, "requested_phase": phase, "reason": "TauP geographic ray path has non-finite or non-positive Cartesian chord length"})
                continue
            records.append(PathRecord(
                station.identifier, phase, phase, str(arrival.name), "phase-aware", [(lat, lon) for lat, lon, _ in samples], float(arrival.time),
                raypath_length_km, "taup_raypath_polyline_estimate", max(item[2] for item in samples), _cmb_near_proxy(samples, cmb_near_depth_tolerance_km),
                {
                    "taup_model": model_name,
                    "resample": resample,
                    "ray_param_tol": ray_param_tol,
                    "path_point_count": len(samples),
                    "model_radius_km": model_radius_km,
                    "sample_coordinates_finite": True,
                    "depth_range_valid": True,
                    "boundary_time_use": "forbidden",
                },
            ))
    if missing and not allow_partial:
        labels = [f"{item['requested_phase']} at {item['station_id']} ({item['reason']})" for item in missing]
        raise PlannerError("TauP did not provide requested geographic phase paths: " + "; ".join(labels) + ". get_ray_paths_geo may require geographiclib.")
    return records, missing
