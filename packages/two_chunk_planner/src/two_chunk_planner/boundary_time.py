"""Boundary-risk reporting without conflating TauP phases and regional reflections."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.geometry import EARTH_RADIUS_KM, angular_distance_km, great_circle_samples, latlon_to_unit
from two_chunk_planner.io import Source, Station


@dataclass
class BoundaryTimeRecord:
    station_id: str
    source_to_boundary_km: float | None
    station_to_boundary_km: float | None
    heuristic_surface_return_path_km: float | None
    boundary_speed_upper_km_s: float | None
    heuristic_earliest_return_s: float | None
    status: str
    hard_constraint_eligible: bool
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_surface_arc_heuristic(domain: CanonicalTwoChunkDomain, source: Source, stations: list[Station], speed_upper_km_s: float | None, samples_per_arc: int = 181) -> list[BoundaryTimeRecord]:
    """Report a surface-arc proxy, explicitly not a conservative 3-D bound.

    The actual lateral absorbing faces are 3-D surfaces. This helper samples
    only their surface traces and is never permitted to reject a candidate.
    """
    source_vector = latlon_to_unit(source.latitude_deg, source.longitude_deg)
    records: list[BoundaryTimeRecord] = []
    for station in stations:
        station_vector = latlon_to_unit(station.latitude_deg, station.longitude_deg)
        source_margin, _ = domain.boundary_distance(source.latitude_deg, source.longitude_deg)
        station_margin, _ = domain.boundary_distance(station.latitude_deg, station.longitude_deg)
        candidates = []
        for arc in domain.external_boundaries:
            for point in great_circle_samples(domain.transform.local_to_global(arc.start_local), domain.transform.local_to_global(arc.end_local), samples_per_arc):
                candidates.append(angular_distance_km(source_vector, point) + angular_distance_km(point, station_vector))
        path = min(candidates) if candidates else None
        estimate = path / speed_upper_km_s if path is not None and speed_upper_km_s and speed_upper_km_s > 0.0 else None
        records.append(BoundaryTimeRecord(
            station.identifier,
            None if source_margin is None else EARTH_RADIUS_KM * source_margin * 3.141592653589793 / 180.0,
            None if station_margin is None else EARTH_RADIUS_KM * station_margin * 3.141592653589793 / 180.0,
            path, speed_upper_km_s, estimate, "heuristic_not_conservative",
            False,
            "Surface boundary-arc proxy only. It does not minimize over the full 3-D absorbing side surface and cannot be used as a hard time constraint. TauP paths are not used.",
        ))
    return records
