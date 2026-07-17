"""Canonical two-face domain, classification, and boundary metrics."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from two_chunk_planner.geometry import Vec3, angular_distance_deg, great_circle_samples, point_to_arc_distance_deg, unit
from two_chunk_planner.transforms import EulerTransform

HALF_WIDTH_DEG = 45.0
EPS_DEG = 1.0e-8


@dataclass(frozen=True)
class BoundaryArc:
    name: str
    start_local: Vec3
    end_local: Vec3


@dataclass
class PointClassification:
    latitude_deg: float
    longitude_deg: float
    classification: str
    xi_deg: float | None
    eta_deg: float | None
    chunk: str | None
    shared_interface_margin_deg: float | None
    c1_margin_deg: float
    c2_margin_deg: float
    external_boundary_margin_deg: float | None
    external_boundary_name: str | None
    on_interface: bool
    on_endpoint: bool
    on_external_boundary: bool

    def to_dict(self) -> dict:
        return asdict(self)


class CanonicalTwoChunkDomain:
    """The accepted AB central + AC supported-left 90°×90° domain."""

    c1_local = unit((1.0, -1.0, 1.0))
    c2_local = unit((-1.0, -1.0, 1.0))

    def __init__(self, transform: EulerTransform):
        self.transform = transform
        self._interface = BoundaryArc("AB_xi_min__AC_xi_max", self.c1_local, self.c2_local)
        self._external = (
            BoundaryArc("AB_eta_min", self.c1_local, unit((1.0, 1.0, 1.0))),
            BoundaryArc("AB_xi_max", unit((1.0, 1.0, 1.0)), unit((-1.0, 1.0, 1.0))),
            BoundaryArc("AB_eta_max", unit((-1.0, 1.0, 1.0)), self.c2_local),
            BoundaryArc("AC_eta_min", self.c1_local, unit((1.0, -1.0, -1.0))),
            BoundaryArc("AC_xi_min", unit((1.0, -1.0, -1.0)), unit((-1.0, -1.0, -1.0))),
            BoundaryArc("AC_eta_max", unit((-1.0, -1.0, -1.0)), self.c2_local),
        )

    @property
    def interface(self) -> BoundaryArc:
        return self._interface

    @property
    def external_boundaries(self) -> tuple[BoundaryArc, ...]:
        return self._external

    def global_endpoint(self, name: str) -> Vec3:
        return self.transform.local_to_global(self.c1_local if name == "C1" else self.c2_local)

    def _chunk_candidates(self, local: Vec3) -> list[tuple[str, float, float]]:
        x, y, z = local
        candidates: list[tuple[str, float, float]] = []
        if z > 0.0:
            candidates.append(("chunk_1_central", math.degrees(math.atan(y / z)), math.degrees(math.atan(-x / z))))
        if y < 0.0:
            candidates.append(("chunk_2_left_attached", math.degrees(math.atan((-z) / y)), math.degrees(math.atan(x / y))))
        return [(name, xi, eta) for name, xi, eta in candidates if abs(xi) <= HALF_WIDTH_DEG + EPS_DEG and abs(eta) <= HALF_WIDTH_DEG + EPS_DEG]

    def classify(self, latitude_deg: float, longitude_deg: float) -> PointClassification:
        local = self.transform.geographic_to_local(latitude_deg, longitude_deg)
        valid = self._chunk_candidates(local)
        if len(valid) == 2:
            chunk, xi, eta = valid[0]
            label = "shared_interface"
        elif len(valid) == 1:
            chunk, xi, eta = valid[0]
            label = chunk
        else:
            c1, c2 = angular_distance_deg(local, self.c1_local), angular_distance_deg(local, self.c2_local)
            return PointClassification(latitude_deg, longitude_deg, "outside_two_chunk_domain", None, None, None, None, c1, c2, None, None, False, False, False)
        shared = point_to_arc_distance_deg(local, self.interface.start_local, self.interface.end_local)
        boundary_distances = [(point_to_arc_distance_deg(local, arc.start_local, arc.end_local), arc.name) for arc in self.external_boundaries]
        external, external_name = min(boundary_distances)
        c1, c2 = angular_distance_deg(local, self.c1_local), angular_distance_deg(local, self.c2_local)
        return PointClassification(
            latitude_deg, longitude_deg, label, xi, eta, chunk, shared, c1, c2, external, external_name,
            shared <= EPS_DEG, min(c1, c2) <= EPS_DEG, external <= EPS_DEG,
        )

    def boundary_distance(self, latitude_deg: float, longitude_deg: float) -> tuple[float | None, str | None]:
        result = self.classify(latitude_deg, longitude_deg)
        return result.external_boundary_margin_deg, result.external_boundary_name

    def interface_distance(self, latitude_deg: float, longitude_deg: float) -> float:
        local = self.transform.geographic_to_local(latitude_deg, longitude_deg)
        return point_to_arc_distance_deg(local, self.interface.start_local, self.interface.end_local)

    def global_arc(self, arc: BoundaryArc, count: int = 65) -> list[tuple[float, float]]:
        return [self.transform.local_to_geographic(point) for point in great_circle_samples(arc.start_local, arc.end_local, count)]

    def outline(self) -> dict[str, list[list[tuple[float, float]]]]:
        return {
            "interface": [self.global_arc(self.interface)],
            "external": [self.global_arc(arc) for arc in self.external_boundaries],
        }

    def path_coverage(self, points: list[tuple[float, float]]) -> dict:
        classifications = [self.classify(latitude, longitude) for latitude, longitude in points]
        inside = sum(item.classification != "outside_two_chunk_domain" for item in classifications)
        margins = [item.external_boundary_margin_deg for item in classifications if item.external_boundary_margin_deg is not None]
        endpoints = [min(item.c1_margin_deg, item.c2_margin_deg) for item in classifications]
        return {
            "sample_count": len(points),
            "inside_count": inside,
            "coverage_fraction": inside / len(points) if points else 0.0,
            "minimum_external_boundary_margin_deg": min(margins) if margins else None,
            "minimum_endpoint_margin_deg": min(endpoints) if endpoints else None,
            "method": "conservative_heuristic_sampled_path",
        }
