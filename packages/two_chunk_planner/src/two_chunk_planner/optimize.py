# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic coarse-to-fine search and compatible resource enumeration."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from typing import Callable

from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.io import Source, Station, TargetRegion, compatible_nex
from two_chunk_planner.objective import GeometryCandidate, GeometryEvaluation, evaluate_geometry, evaluate_geometry_scalar_summary, evaluate_geometry_summaries, prepare_geometry_inputs
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


@dataclass(frozen=True)
class SearchItem:
    center_latitude_deg: float
    center_longitude_deg: float
    gamma_rotation_azimuth_deg: float
    evaluation: GeometryEvaluation

    @property
    def feasible(self) -> bool:
        return self.evaluation.feasible

    @property
    def total_score(self) -> float:
        return self.evaluation.total_score


@dataclass
class SearchTrace:
    """Optional test-only record of the exact three-stage keeper sequence."""
    generated: dict[str, list[tuple[float, float, float]]]
    evaluated: dict[str, list[SearchItem]]
    keepers: dict[str, list[tuple[float, float, float]]]

    @classmethod
    def empty(cls) -> "SearchTrace":
        return cls({}, {}, {})


@dataclass
class StageDiagnostics:
    generated: int = 0
    deduplicated: int = 0
    cheap_precheck_rejected: int = 0
    path_evaluated: int = 0
    batch_only: int = 0
    batch_scalar_exact: int = 0
    numerical_guard_candidates: int = 0
    scalar_fallback: int = 0
    keeper_cutoff_fallback: int = 0
    keeper_count: int = 0
    path_seconds: float = 0.0


@dataclass
class SearchDiagnostics:
    """Internal-only counters for performance validation; never emitted by CLI."""

    stages: dict[str, StageDiagnostics]
    batch_path_calls: int = 0
    batch_path_seconds: float = 0.0
    scalar_seconds: float = 0.0
    scalar_reasons: dict[str, int] | None = None
    scalar_cache_hits: int = 0
    scalar_cache_misses: int = 0
    progress_callback: Callable[[str, int, StageDiagnostics], None] | None = None

    @classmethod
    def empty(cls) -> "SearchDiagnostics":
        return cls({}, scalar_reasons={})


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


def _around(candidate: GeometryCandidate | SearchItem, half_lat: float, half_lon: float, half_gamma: float, lat_step: float, lon_step: float, gamma_step: float, settings: SearchSettings) -> list[tuple[float, float, float]]:
    if (abs(settings.latitude_min - settings.latitude_max) < 1.0e-10 and abs(settings.longitude_min - settings.longitude_max) < 1.0e-10 and abs(settings.gamma_min - settings.gamma_max) < 1.0e-10):
        return [(candidate.center_latitude_deg, candidate.center_longitude_deg, candidate.gamma_rotation_azimuth_deg)]
    return [parameters for parameters in (_canonical_parameters(latitude, longitude, gamma) for latitude, longitude, gamma in product(
        _values(candidate.center_latitude_deg - half_lat, candidate.center_latitude_deg + half_lat + lat_step, lat_step),
        _values(candidate.center_longitude_deg - half_lon, candidate.center_longitude_deg + half_lon + lon_step, lon_step),
        _values(candidate.gamma_rotation_azimuth_deg - half_gamma, candidate.gamma_rotation_azimuth_deg + half_gamma + gamma_step, gamma_step),
    )) if _within(parameters, settings)]


def search(source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None, ellipticity: bool, minimum_coverage: float, settings: SearchSettings, weights: dict[str, float] | None = None, trace: SearchTrace | None = None, diagnostics: SearchDiagnostics | None = None, orientation_batch_size: int = 8) -> SearchResult:
    """Run the unchanged ordered three-stage search.

    ``diagnostics`` and ``orientation_batch_size`` are internal Python API
    hooks for performance validation.  The command-line interface neither
    exposes nor prints them.
    """
    if orientation_batch_size < 1:
        raise ValueError("orientation batch size must be positive")
    from time import perf_counter

    all_count = 0
    seen: set[tuple[float, float, float]] = set()
    evaluated_count = feasible_count = rejected_count = 0
    summary: dict[str, int] = {}
    rank = lambda item: (-item.total_score, item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg)
    prepared = prepare_geometry_inputs(source, stations, paths, target, ellipticity)
    best_feasible: list[SearchItem] = []
    # The cache lives only for this search invocation.  ``prepared`` and every
    # scoring input are immutable closure state, so canonical orientation is a
    # complete key within this one run and cannot leak across CLI executions.
    scalar_cache: dict[tuple[float, float, float], SearchItem] = {}

    def scalar_item(item: SearchItem, domain: CanonicalTwoChunkDomain, reason: str, stage_diagnostics: StageDiagnostics) -> SearchItem:
        start = perf_counter()
        evaluation = evaluate_geometry_scalar_summary(
            domain, item.center_latitude_deg, item.center_longitude_deg,
            item.gamma_rotation_azimuth_deg, source, stations, paths, target,
            minimum_coverage, weights, prepared,
        )
        elapsed = perf_counter() - start
        stage_diagnostics.scalar_fallback += 1
        if reason == "keeper_cutoff":
            stage_diagnostics.keeper_cutoff_fallback += 1
        if diagnostics is not None:
            diagnostics.scalar_seconds += elapsed
            assert diagnostics.scalar_reasons is not None
            diagnostics.scalar_reasons[reason] = diagnostics.scalar_reasons.get(reason, 0) + 1
        return SearchItem(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg, evaluation)

    def evaluate(stage: str, parameters: list[tuple[float, float, float]], keep: int) -> list[SearchItem]:
        nonlocal all_count, evaluated_count, feasible_count, rejected_count
        all_count += len(parameters)
        stage_diagnostics = StageDiagnostics(generated=len(parameters))
        if diagnostics is not None:
            diagnostics.stages[stage] = stage_diagnostics
        if trace is not None:
            trace.generated[stage] = list(parameters)
            trace.evaluated[stage] = []
        retained: list[SearchItem] = []
        pending: list[tuple[float, float, float, CanonicalTwoChunkDomain]] = []
        for latitude, longitude, gamma in parameters:
            key = (latitude, longitude, gamma)
            if key in seen:
                continue
            seen.add(key)
            pending.append((latitude, longitude, gamma, CanonicalTwoChunkDomain(EulerTransform(latitude, longitude, gamma, ellipticity))))
        stage_diagnostics.deduplicated = len(pending)

        def scalar_checked(item: SearchItem, domain: CanonicalTwoChunkDomain, reason: str) -> SearchItem:
            key = (item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg)
            cached = scalar_cache.get(key)
            if cached is not None:
                if diagnostics is not None:
                    diagnostics.scalar_cache_hits += 1
                return cached
            if diagnostics is not None:
                diagnostics.scalar_cache_misses += 1
            checked = scalar_item(item, domain, reason, stage_diagnostics)
            scalar_cache[key] = checked
            return checked

        def retain(item: SearchItem, domain: CanonicalTwoChunkDomain, uncertain: bool) -> None:
            nonlocal retained, feasible_count, rejected_count
            # Only predicate uncertainty requires immediate scalar fallback.
            # Score intervals are checked at the actual legacy prune point;
            # before then no candidate is discarded from the stage reservoir.
            if uncertain:
                item = scalar_checked(item, domain, "numerical_guard")
            if trace is not None:
                trace.evaluated[stage].append(item)
            if item.feasible:
                feasible_count += 1
                best_feasible.append(item)
                if len(best_feasible) > 10:
                    best_feasible[:] = sorted(best_feasible, key=rank)[:5]
            else:
                rejected_count += 1
                for reason in item.evaluation.rejection_reasons:
                    summary[reason] = summary.get(reason, 0) + 1
            retained.append(item)
            if len(retained) > keep * 2:
                # Verify the provisional cutoff and every interval that can
                # cross it before preserving the legacy top-``keep`` list.
                while True:
                    provisional = sorted(retained, key=rank)
                    cutoff = provisional[keep - 1].total_score
                    changed = False
                    for index, candidate in enumerate(retained):
                        key = (candidate.center_latitude_deg, candidate.center_longitude_deg, candidate.gamma_rotation_azimuth_deg)
                        if not candidate.evaluation.scalar_exact and abs(candidate.total_score - cutoff) <= 1.0e-10 and key not in scalar_cache:
                            domain = CanonicalTwoChunkDomain(EulerTransform(*key, ellipticity))
                            retained[index] = scalar_checked(candidate, domain, "keeper_cutoff")
                            changed = True
                    if not changed:
                        break
                retained = sorted(retained, key=rank)[:keep]

        for batch_start in range(0, len(pending), orientation_batch_size):
            batch = pending[batch_start:batch_start + orientation_batch_size]
            start = perf_counter()
            evaluations, uncertain = evaluate_geometry_summaries(
                tuple(item[3] for item in batch), source, stations, paths,
                target, prepared, minimum_coverage, weights,
            )
            elapsed = perf_counter() - start
            stage_diagnostics.path_evaluated += len(batch)
            stage_diagnostics.path_seconds += elapsed
            stage_diagnostics.batch_scalar_exact += sum(item.scalar_exact for item in evaluations)
            stage_diagnostics.numerical_guard_candidates += int(sum(uncertain))
            if diagnostics is not None:
                diagnostics.batch_path_calls += 1
                diagnostics.batch_path_seconds += elapsed
            for (latitude, longitude, gamma, domain), evaluation, is_uncertain in zip(batch, evaluations, uncertain):
                evaluated_count += 1
                retain(SearchItem(latitude, longitude, gamma, evaluation), domain, bool(is_uncertain))
            if diagnostics is not None and diagnostics.progress_callback is not None:
                diagnostics.progress_callback(stage, stage_diagnostics.path_evaluated, stage_diagnostics)
        # ``scalar_exact`` is set only when the batch guard proves all boolean
        # predicates are separated from their thresholds and the winning
        # boundary point has already been recomputed by the legacy scalar arc
        # routine.  Other keepers retain the authoritative full scalar path.
        # Re-sort after replacement to preserve legacy ranking.
        selected = sorted(retained, key=rank)[:keep]
        selected = [
            item if item.evaluation.scalar_exact else scalar_checked(
                item,
                CanonicalTwoChunkDomain(EulerTransform(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg, ellipticity)),
                "keeper_cutoff",
            )
            for item in selected
        ]
        selected = sorted(selected, key=rank)[:keep]
        stage_diagnostics.batch_only = stage_diagnostics.deduplicated - stage_diagnostics.scalar_fallback
        stage_diagnostics.keeper_count = len(selected)
        if trace is not None:
            trace.keepers[stage] = [(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg) for item in selected]
        return selected

    coarse_top = evaluate("coarse", _grid(settings), 20)
    local_top = evaluate("local", [parameters for item in coarse_top for parameters in _around(item, 10.0, 10.0, 15.0, settings.local_latitude_step, settings.local_longitude_step, settings.local_gamma_step, settings)], 20)
    final_top = evaluate("final", [parameters for item in local_top[:5] for parameters in _around(item, 2.0, 2.0, 2.0, settings.final_latitude_step, settings.final_longitude_step, settings.final_gamma_step, settings)], 20)
    del coarse_top, local_top, final_top
    unique_feasible: dict[tuple[float, float, float], SearchItem] = {(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg): item for item in best_feasible}
    chosen = sorted(unique_feasible.values(), key=rank)[:5]
    candidates = [evaluate_geometry(CanonicalTwoChunkDomain(EulerTransform(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg, ellipticity)), item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg, source, stations, paths, target, minimum_coverage, weights) for item in chosen]
    return SearchResult(candidates, all_count, len(seen), evaluated_count, feasible_count, rejected_count, dict(sorted(summary.items())))


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
