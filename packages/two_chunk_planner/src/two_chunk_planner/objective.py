# SPDX-License-Identifier: GPL-3.0-or-later
"""Hard constraints and transparent deterministic scoring."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.geometry import EARTH_RADIUS_KM, cross, great_circle_samples, latlon_to_unit, unit, unit_to_latlon
from two_chunk_planner.io import Source, Station, TargetRegion
from two_chunk_planner.paths import PathRecord


DEFAULT_WEIGHTS = {"coverage": 0.35, "external_margin": 0.30, "endpoint_margin": 0.20, "cost": 0.15}


@dataclass
class GeometryCandidate:
    center_latitude_deg: float
    center_longitude_deg: float
    gamma_rotation_azimuth_deg: float
    feasible: bool
    rejection_reasons: list[str]
    warnings: list[str]
    source: dict
    stations: list[dict]
    path_audits: list[dict]
    target_audit: dict | None
    score_components: dict[str, float]
    total_score: float

    def to_dict(self) -> dict:
        return asdict(self)


def _circle_points(region: TargetRegion, count: int = 72) -> list[tuple[float, float]]:
    center = region.payload["center"]
    latitude, longitude, radius = float(center["latitude_deg"]), float(center["longitude_deg"]), float(region.payload["radius_km"])
    angular = radius / EARTH_RADIUS_KM
    c = latlon_to_unit(latitude, longitude)
    north = (0.0, 0.0, 1.0)
    east = (0.0, 1.0, 0.0) if abs(c[2]) > 0.99 else (-c[1], c[0], 0.0)
    east_length = math.sqrt(sum(value * value for value in east))
    east = tuple(value / east_length for value in east)
    north_tangent = (c[1] * east[2] - c[2] * east[1], c[2] * east[0] - c[0] * east[2], c[0] * east[1] - c[1] * east[0])
    result = [(latitude, longitude)]
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        vector = tuple(math.cos(angular) * c[i] + math.sin(angular) * (math.cos(angle) * east[i] + math.sin(angle) * north_tangent[i]) for i in range(3))
        result.append(unit_to_latlon(vector))
    return result


def target_samples(region: TargetRegion) -> tuple[list[tuple[float, float]], str]:
    if region.kind == "circle":
        return _circle_points(region), "conservative_heuristic_boundary_samples"
    key = "vertices" if region.kind == "polygon" else "centerline"
    points = [(float(item["latitude_deg"]), float(item["longitude_deg"])) for item in region.payload[key]]
    if region.kind == "polygon":
        output: list[tuple[float, float]] = []
        for left, right in zip(points, points[1:] + points[:1]):
            output.extend(unit_to_latlon(value) for value in great_circle_samples(latlon_to_unit(*left), latlon_to_unit(*right), 33))
        return output, "conservative_heuristic_polygon_edge_samples"
    output = []
    width = float(region.payload["half_width_km"]) / EARTH_RADIUS_KM
    for left, right in zip(points, points[1:]):
        start, end = latlon_to_unit(*left), latlon_to_unit(*right)
        plane_normal = unit(cross(start, end))
        for value in great_circle_samples(start, end, 65):
            tangent = unit(cross(plane_normal, value))
            left_edge = unit(tuple(math.cos(width) * value[i] + math.sin(width) * tangent[i] for i in range(3)))
            right_edge = unit(tuple(math.cos(width) * value[i] - math.sin(width) * tangent[i] for i in range(3)))
            output.extend((unit_to_latlon(value), unit_to_latlon(left_edge), unit_to_latlon(right_edge)))
    return output, "conservative_heuristic_corridor_edge_samples"


def evaluate_geometry(domain: CanonicalTwoChunkDomain, center_latitude_deg: float, center_longitude_deg: float, gamma_deg: float, source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None, minimum_coverage: float, weights: dict[str, float] | None = None) -> GeometryCandidate:
    source_audit = domain.classify(source.latitude_deg, source.longitude_deg).to_dict()
    station_audits = [{"id": station.identifier, **domain.classify(station.latitude_deg, station.longitude_deg).to_dict()} for station in stations]
    path_audits = [{"station_id": path.station_id, "phase": path.phase, **domain.path_coverage(path.points)} for path in paths]
    rejection: list[str] = []
    warnings: list[str] = []
    for label, item in [("source", source_audit), *[(station["id"], station) for station in station_audits]]:
        if item["classification"] == "outside_two_chunk_domain":
            rejection.append(f"{label} is outside the canonical two-chunk domain")
        if item["on_endpoint"] or item["on_external_boundary"]:
            rejection.append(f"{label} lies on an endpoint or external boundary")
        if item["on_interface"]:
            warnings.append(f"{label} lies on the internal interface; this is not an absorbing boundary but is numerically sensitive")
    for item in path_audits:
        if item["coverage_fraction"] < minimum_coverage:
            rejection.append(f"path {item['station_id']} coverage {item['coverage_fraction']:.3f} is below required {minimum_coverage:.3f}")
    target_audit = None
    if target is not None:
        samples, method = target_samples(target)
        coverage = domain.path_coverage(samples)
        target_audit = {"name": target.name, "type": target.kind, "containment_method": method, **coverage}
        if coverage["coverage_fraction"] < 1.0:
            rejection.append(f"target_region {target.name} is not fully covered by sampled containment audit")
    external_values = [value for value in [source_audit["external_boundary_margin_deg"], *[station["external_boundary_margin_deg"] for station in station_audits], *[path["minimum_external_boundary_margin_deg"] for path in path_audits]] if value is not None]
    endpoint_values = [source_audit["c1_margin_deg"], source_audit["c2_margin_deg"]]
    for item in station_audits:
        endpoint_values.extend((item["c1_margin_deg"], item["c2_margin_deg"]))
    coverage_values = [item["coverage_fraction"] for item in path_audits]
    if target_audit:
        coverage_values.append(target_audit["coverage_fraction"])
    # Raw monotonic score components are deliberately exposed, not hidden behind a model.
    components = {
        "coverage": min(coverage_values) if coverage_values else 0.0,
        "external_margin": min(external_values) if external_values else 0.0,
        "endpoint_margin": min(endpoint_values) if endpoint_values else 0.0,
        "cost": 0.0,
    }
    active = dict(DEFAULT_WEIGHTS if weights is None else weights)
    total_weight = sum(active.values())
    normalized = {
        "coverage": components["coverage"],
        "external_margin": min(1.0, components["external_margin"] / 45.0),
        "endpoint_margin": min(1.0, components["endpoint_margin"] / 45.0),
        "cost": 1.0,
    }
    total = sum(active.get(key, 0.0) * normalized[key] for key in normalized) / total_weight if total_weight else 0.0
    return GeometryCandidate(center_latitude_deg, center_longitude_deg, gamma_deg, not rejection, sorted(set(rejection)), sorted(set(warnings)), source_audit, station_audits, path_audits, target_audit, {**components, **{f"normalized_{key}": value for key, value in normalized.items()}, **{f"weight_{key}": active.get(key, 0.0) for key in normalized}}, total)
