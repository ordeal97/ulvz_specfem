# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic coarse-to-fine search and compatible resource enumeration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product

from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.io import Source, Station, TargetRegion, compatible_nex
from two_chunk_planner.objective import GeometryCandidate, evaluate_geometry
from two_chunk_planner.paths import PathRecord
from two_chunk_planner.transforms import EulerTransform


@dataclass(frozen=True)
class SearchSettings:
    latitude_min: float = -90.0
    latitude_max: float = 90.0
    longitude_min: float = -180.0
    longitude_max: float = 180.0
    gamma_min: float = 0.0
    gamma_max: float = 360.0
    coarse_latitude_step: float = 10.0
    coarse_longitude_step: float = 10.0
    coarse_gamma_step: float = 15.0
    local_latitude_step: float = 2.0
    local_longitude_step: float = 2.0
    local_gamma_step: float = 3.0
    final_latitude_step: float = 0.5
    final_longitude_step: float = 0.5
    final_gamma_step: float = 0.5


@dataclass(frozen=True)
class ResourceSuggestion:
    nex_xi: int
    nex_eta: int
    nproc_xi: int
    nproc_eta: int
    total_ranks: int
    relative_lateral_work_per_rank: float
    validation_status: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResult:
    candidates: list[GeometryCandidate]
    all_candidate_count: int
    deduplicated_candidate_count: int
    evaluated_count: int
    feasible_count: int
    rejected_count: int
    rejection_summary: dict[str, int]


def _values(start: float, stop: float, step: float, include_stop: bool = False) -> list[float]:
    if abs(start - stop) < 1.0e-10:
        return [round(start, 10)]
    values: list[float] = []
    value = start
    while value < stop - 1.0e-10 or (include_stop and value <= stop + 1.0e-10):
        values.append(round(value, 10))
        value += step
    return values


def _canonical_parameters(latitude: float, longitude: float, gamma: float) -> tuple[float, float, float]:
    longitude = ((longitude + 180.0) % 360.0) - 180.0
    gamma = gamma % 360.0
    if abs(abs(latitude) - 90.0) < 1.0e-10:
        # Longitude and gamma are non-unique at a pole. Preserve the physical
        # Euler orientation while choosing longitude=0: north uses alpha+gamma
        # and south uses gamma-alpha in the current Euler matrix.
        pole_gamma = gamma + longitude if latitude > 0.0 else gamma - longitude
        return (90.0 if latitude > 0 else -90.0, 0.0, round(pole_gamma % 360.0, 10))
    return (round(latitude, 10), round(longitude, 10), round(gamma, 10))


def _grid(settings: SearchSettings) -> list[tuple[float, float, float]]:
    return [_canonical_parameters(latitude, longitude, gamma) for latitude, longitude, gamma in product(
        _values(settings.latitude_min, settings.latitude_max, settings.coarse_latitude_step, True),
        _values(settings.longitude_min, settings.longitude_max, settings.coarse_longitude_step),
        _values(settings.gamma_min, settings.gamma_max, settings.coarse_gamma_step),
    )]


def _within(parameters: tuple[float, float, float], settings: SearchSettings) -> bool:
    latitude, longitude, gamma = parameters
    if not settings.latitude_min - 1.0e-10 <= latitude <= settings.latitude_max + 1.0e-10:
        return False
    if abs(abs(latitude) - 90.0) < 1.0e-10:
        # Canonical pole coordinates no longer retain the caller's redundant
        # longitude/gamma representation; latitude bounds remain meaningful.
        return True
    if not settings.longitude_min - 1.0e-10 <= longitude <= settings.longitude_max + 1.0e-10:
        return False
    if settings.gamma_max - settings.gamma_min < 360.0 - 1.0e-10 and not settings.gamma_min - 1.0e-10 <= gamma <= settings.gamma_max + 1.0e-10:
        return False
    return True


def _around(candidate: GeometryCandidate, half_lat: float, half_lon: float, half_gamma: float, lat_step: float, lon_step: float, gamma_step: float, settings: SearchSettings) -> list[tuple[float, float, float]]:
    if (abs(settings.latitude_min - settings.latitude_max) < 1.0e-10 and abs(settings.longitude_min - settings.longitude_max) < 1.0e-10 and abs(settings.gamma_min - settings.gamma_max) < 1.0e-10):
        return [(candidate.center_latitude_deg, candidate.center_longitude_deg, candidate.gamma_rotation_azimuth_deg)]
    return [parameters for parameters in (_canonical_parameters(latitude, longitude, gamma) for latitude, longitude, gamma in product(
        _values(candidate.center_latitude_deg - half_lat, candidate.center_latitude_deg + half_lat + lat_step, lat_step),
        _values(candidate.center_longitude_deg - half_lon, candidate.center_longitude_deg + half_lon + lon_step, lon_step),
        _values(candidate.gamma_rotation_azimuth_deg - half_gamma, candidate.gamma_rotation_azimuth_deg + half_gamma + gamma_step, gamma_step),
    )) if _within(parameters, settings)]


def search(source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None, ellipticity: bool, minimum_coverage: float, settings: SearchSettings, weights: dict[str, float] | None = None) -> SearchResult:
    all_count = 0
    seen: set[tuple[float, float, float]] = set()
    evaluated_count = feasible_count = rejected_count = 0
    summary: dict[str, int] = {}
    rank = lambda item: (-item.total_score, item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg)
    best_feasible: list[GeometryCandidate] = []

    def evaluate(parameters: list[tuple[float, float, float]], keep: int) -> list[GeometryCandidate]:
        nonlocal all_count, evaluated_count, feasible_count, rejected_count
        all_count += len(parameters)
        retained: list[GeometryCandidate] = []
        for latitude, longitude, gamma in parameters:
            key = (latitude, longitude, gamma)
            if key in seen:
                continue
            seen.add(key)
            domain = CanonicalTwoChunkDomain(EulerTransform(latitude, longitude, gamma, ellipticity))
            item = evaluate_geometry(domain, latitude, longitude, gamma, source, stations, paths, target, minimum_coverage, weights)
            evaluated_count += 1
            if item.feasible:
                feasible_count += 1
                best_feasible.append(item)
                if len(best_feasible) > 10:
                    best_feasible[:] = sorted(best_feasible, key=rank)[:5]
            else:
                rejected_count += 1
                for reason in item.rejection_reasons:
                    summary[reason] = summary.get(reason, 0) + 1
            retained.append(item)
            if len(retained) > keep * 2:
                retained = sorted(retained, key=rank)[:keep]
        return sorted(retained, key=rank)[:keep]

    coarse_top = evaluate(_grid(settings), 20)
    local_top = evaluate([parameters for item in coarse_top for parameters in _around(item, 10.0, 10.0, 15.0, settings.local_latitude_step, settings.local_longitude_step, settings.local_gamma_step, settings)], 20)
    final_top = evaluate([parameters for item in local_top[:5] for parameters in _around(item, 2.0, 2.0, 2.0, settings.final_latitude_step, settings.final_longitude_step, settings.final_gamma_step, settings)], 20)
    del coarse_top, local_top, final_top
    unique_feasible: dict[tuple[float, float, float], GeometryCandidate] = {(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg): item for item in best_feasible}
    return SearchResult(sorted(unique_feasible.values(), key=rank)[:5], all_count, len(seen), evaluated_count, feasible_count, rejected_count, dict(sorted(summary.items())))


def resource_suggestions(nex_candidates: list[tuple[int, int]], available_ranks: list[int], par: dict[str, str], validation: dict) -> list[ResourceSuggestion]:
    suggestions: list[ResourceSuggestion] = []
    for nex_xi, nex_eta in nex_candidates:
        for ranks in sorted(set(available_ranks)):
            for nproc_xi in range(1, ranks + 1):
                if ranks % (2 * nproc_xi):
                    continue
                nproc_eta = ranks // (2 * nproc_xi)
                compatible, _ = compatible_nex(nex_xi, nex_eta, nproc_xi, nproc_eta, par)
                if compatible:
                    status = "project_validated" if ranks in set(validation["project_validated_total_ranks"]) and [nex_xi, nex_eta] == validation["project_validated_nex"] else "mathematically_compatible_not_project_validated"
                    suggestions.append(ResourceSuggestion(nex_xi, nex_eta, nproc_xi, nproc_eta, ranks, nex_xi * nex_eta / (nproc_xi * nproc_eta), status))
    return sorted(suggestions, key=lambda item: (item.relative_lateral_work_per_rank, item.total_ranks, item.nproc_xi, item.nproc_eta))
