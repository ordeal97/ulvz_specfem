# SPDX-License-Identifier: GPL-3.0-or-later
"""Hard constraints and transparent deterministic scoring."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from two_chunk_planner.domain import CanonicalTwoChunkDomain, path_coverage_for_global_arrays
from two_chunk_planner.geometry import EARTH_RADIUS_KM, Vec3, cross, great_circle_samples, latlon_to_unit, unit, unit_to_latlon
from two_chunk_planner.io import Source, Station, TargetRegion
from two_chunk_planner.paths import PathRecord
from two_chunk_planner.transforms import geographic_to_global_vector


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


@dataclass(frozen=True)
class PreparedGeometryInputs:
    source_vector: Vec3
    station_vectors: tuple[Vec3, ...]
    path_vectors: tuple[np.ndarray, ...]
    path_vector_array: np.ndarray
    path_offsets: np.ndarray
    target_vectors: tuple[Vec3, ...] | None
    target_method: str | None


@dataclass(frozen=True)
class GeometryEvaluation:
    feasible: bool
    rejection_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    coverage: float
    external_margin: float
    endpoint_margin: float
    total_score: float
    scalar_exact: bool = False


def prepare_geometry_inputs(source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None, ellipticity: bool) -> PreparedGeometryInputs:
    """Precompute geographic vectors and optional target sampling once per run."""
    vector = lambda latitude, longitude: geographic_to_global_vector(latitude, longitude, ellipticity)
    target_points, target_method = target_samples(target) if target is not None else (None, None)
    path_vectors = tuple(np.ascontiguousarray([vector(latitude, longitude) for latitude, longitude in path.points], dtype=np.float64) for path in paths)
    path_offsets = np.zeros(len(path_vectors) + 1, dtype=np.int64)
    if path_vectors:
        path_offsets[1:] = np.cumsum([len(item) for item in path_vectors], dtype=np.int64)
        path_vector_array = np.ascontiguousarray(np.concatenate(path_vectors, axis=0))
    else:
        path_vector_array = np.empty((0, 3), dtype=np.float64)
    return PreparedGeometryInputs(
        vector(source.latitude_deg, source.longitude_deg),
        tuple(vector(station.latitude_deg, station.longitude_deg) for station in stations),
        path_vectors,
        path_vector_array,
        path_offsets,
        None if target_points is None else tuple(vector(latitude, longitude) for latitude, longitude in target_points),
        target_method,
    )


def _score(coverage: float, external_margin: float, endpoint_margin: float, weights: dict[str, float] | None) -> float:
    active = dict(DEFAULT_WEIGHTS if weights is None else weights)
    total_weight = sum(active.values())
    normalized = {
        "coverage": coverage,
        "external_margin": min(1.0, external_margin / 45.0),
        "endpoint_margin": min(1.0, endpoint_margin / 45.0),
        "cost": 1.0,
    }
    return sum(active.get(key, 0.0) * normalized[key] for key in normalized) / total_weight if total_weight else 0.0


def evaluate_geometry_summary(domain: CanonicalTwoChunkDomain, source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None, prepared: PreparedGeometryInputs, minimum_coverage: float, weights: dict[str, float] | None = None) -> GeometryEvaluation:
    """Evaluate exactly the existing constraints without materializing audits."""
    rejection: list[str] = []
    warnings: list[str] = []
    external_values: list[float] = []
    endpoint_values: list[float] = []
    coverage_values: list[float] = []
    records = [("source", prepared.source_vector), *[(station.identifier, vector) for station, vector in zip(stations, prepared.station_vectors)]]
    for label, vector in records:
        classification, c1, c2, external, on_interface, on_endpoint, on_external = domain.classification_components_for_global_vector(vector)
        if classification == "outside_two_chunk_domain":
            rejection.append(f"{label} is outside the canonical two-chunk domain")
        if on_endpoint or on_external:
            rejection.append(f"{label} lies on an endpoint or external boundary")
        if on_interface:
            warnings.append(f"{label} lies on the internal interface; this is not an absorbing boundary but is numerically sensitive")
        if external is not None:
            external_values.append(external)
        endpoint_values.extend((c1, c2))
    for path, vectors in zip(paths, prepared.path_vectors):
        _, coverage, external, endpoint = domain.path_coverage_for_global_array(vectors)
        if coverage < minimum_coverage:
            rejection.append(f"path {path.station_id} coverage {coverage:.3f} is below required {minimum_coverage:.3f}")
        coverage_values.append(coverage)
        if external is not None:
            external_values.append(external)
    if prepared.target_vectors is not None:
        _, coverage, external, _ = domain.path_coverage_for_global_vectors(prepared.target_vectors)
        if coverage < 1.0:
            rejection.append(f"target_region {target.name} is not fully covered by sampled containment audit")
        coverage_values.append(coverage)
        if external is not None:
            external_values.append(external)
    coverage = min(coverage_values) if coverage_values else 0.0
    external_margin = min(external_values) if external_values else 0.0
    endpoint_margin = min(endpoint_values) if endpoint_values else 0.0
    return GeometryEvaluation(not rejection, tuple(sorted(set(rejection))), tuple(sorted(set(warnings))), coverage, external_margin, endpoint_margin, _score(coverage, external_margin, endpoint_margin, weights))


def evaluate_geometry_summaries(
    domains: tuple[CanonicalTwoChunkDomain, ...],
    source: Source,
    stations: list[Station],
    paths: list[PathRecord],
    target: TargetRegion | None,
    prepared: PreparedGeometryInputs,
    minimum_coverage: float,
    weights: dict[str, float] | None = None,
) -> tuple[tuple[GeometryEvaluation, ...], np.ndarray]:
    """Evaluate an ordered orientation batch without materialising audits.

    Source/station and optional target checks deliberately retain the existing
    scalar semantics.  The expensive path-point work is shared across the
    batch by rotating only fixed domain geometry into global coordinates.
    """
    if not domains:
        return (), np.empty(0, dtype=bool)
    path_batch = path_coverage_for_global_arrays(
        prepared.path_vector_array,
        prepared.path_offsets,
        tuple(domain.transform for domain in domains),
    )
    evaluations: list[GeometryEvaluation] = []
    records = [("source", prepared.source_vector), *[(station.identifier, vector) for station, vector in zip(stations, prepared.station_vectors)]]
    for index, domain in enumerate(domains):
        rejection: list[str] = []
        warnings: list[str] = []
        external_values: list[float] = []
        endpoint_values: list[float] = []
        coverage_values: list[float] = []
        for label, vector in records:
            classification, c1, c2, external, on_interface, on_endpoint, on_external = domain.classification_components_for_global_vector(vector)
            if classification == "outside_two_chunk_domain":
                rejection.append(f"{label} is outside the canonical two-chunk domain")
            if on_endpoint or on_external:
                rejection.append(f"{label} lies on an endpoint or external boundary")
            if on_interface:
                warnings.append(f"{label} lies on the internal interface; this is not an absorbing boundary but is numerically sensitive")
            if external is not None:
                external_values.append(external)
            endpoint_values.extend((c1, c2))
        for path_index, path in enumerate(paths):
            coverage = float(path_batch.coverage[index, path_index])
            if coverage < minimum_coverage:
                rejection.append(f"path {path.station_id} coverage {coverage:.3f} is below required {minimum_coverage:.3f}")
            coverage_values.append(coverage)
        global_path_external = float(path_batch.global_external_margins[index])
        if math.isfinite(global_path_external):
            external_values.append(global_path_external)
        if prepared.target_vectors is not None:
            _, coverage, external, _ = domain.path_coverage_for_global_vectors(prepared.target_vectors)
            if coverage < 1.0:
                rejection.append(f"target_region {target.name} is not fully covered by sampled containment audit")
            coverage_values.append(coverage)
            if external is not None:
                external_values.append(external)
        coverage = min(coverage_values) if coverage_values else 0.0
        external_margin = min(external_values) if external_values else 0.0
        endpoint_margin = min(endpoint_values) if endpoint_values else 0.0
        # With no interior path points, all path contributions are exactly the
        # scalar values (coverage=0 and no external margin).  Source/station
        # metrics above are already scalar.  This gives a zero-width score
        # interval for keeper tie handling without weakening any threshold.
        scalar_exact = prepared.target_vectors is None and not bool(path_batch.uncertain[index])
        evaluations.append(GeometryEvaluation(not rejection, tuple(sorted(set(rejection))), tuple(sorted(set(warnings))), coverage, external_margin, endpoint_margin, _score(coverage, external_margin, endpoint_margin, weights), scalar_exact))
    return tuple(evaluations), path_batch.uncertain


def evaluate_geometry_scalar_summary(
    domain: CanonicalTwoChunkDomain,
    center_latitude_deg: float,
    center_longitude_deg: float,
    gamma_deg: float,
    source: Source,
    stations: list[Station],
    paths: list[PathRecord],
    target: TargetRegion | None,
    minimum_coverage: float,
    weights: dict[str, float] | None = None,
    prepared: PreparedGeometryInputs | None = None,
) -> GeometryEvaluation:
    """Authoritative scalar fallback without building audit dictionaries."""
    prepared = prepared or prepare_geometry_inputs(source, stations, paths, target, domain.transform.ellipticity)
    rejection: list[str] = []
    warnings: list[str] = []
    external_values: list[float] = []
    endpoint_values: list[float] = []
    coverage_values: list[float] = []
    records = [("source", prepared.source_vector), *[(station.identifier, vector) for station, vector in zip(stations, prepared.station_vectors)]]
    for label, vector in records:
        classification, c1, c2, external, on_interface, on_endpoint, on_external = domain.classification_components_for_global_vector(vector)
        if classification == "outside_two_chunk_domain":
            rejection.append(f"{label} is outside the canonical two-chunk domain")
        if on_endpoint or on_external:
            rejection.append(f"{label} lies on an endpoint or external boundary")
        if on_interface:
            warnings.append(f"{label} lies on the internal interface; this is not an absorbing boundary but is numerically sensitive")
        if external is not None:
            external_values.append(external)
        endpoint_values.extend((c1, c2))
    for path, vectors in zip(paths, prepared.path_vectors):
        _, coverage, external, _ = domain.path_coverage_for_global_vectors(vectors)
        if coverage < minimum_coverage:
            rejection.append(f"path {path.station_id} coverage {coverage:.3f} is below required {minimum_coverage:.3f}")
        coverage_values.append(coverage)
        if external is not None:
            external_values.append(external)
    if prepared.target_vectors is not None:
        _, coverage, external, _ = domain.path_coverage_for_global_vectors(prepared.target_vectors)
        if coverage < 1.0:
            rejection.append(f"target_region {target.name} is not fully covered by sampled containment audit")
        coverage_values.append(coverage)
        if external is not None:
            external_values.append(external)
    coverage = min(coverage_values) if coverage_values else 0.0
    external_margin = min(external_values) if external_values else 0.0
    endpoint_margin = min(endpoint_values) if endpoint_values else 0.0
    return GeometryEvaluation(not rejection, tuple(sorted(set(rejection))), tuple(sorted(set(warnings))), coverage, external_margin, endpoint_margin, _score(coverage, external_margin, endpoint_margin, weights), True)


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
    normalized = {
        "coverage": components["coverage"],
        "external_margin": min(1.0, components["external_margin"] / 45.0),
        "endpoint_margin": min(1.0, components["endpoint_margin"] / 45.0),
        "cost": 1.0,
    }
    total = _score(components["coverage"], components["external_margin"], components["endpoint_margin"], weights)
    return GeometryCandidate(center_latitude_deg, center_longitude_deg, gamma_deg, not rejection, sorted(set(rejection)), sorted(set(warnings)), source_audit, station_audits, path_audits, target_audit, {**components, **{f"normalized_{key}": value for key, value in normalized.items()}, **{f"weight_{key}": active.get(key, 0.0) for key in normalized}}, total)
