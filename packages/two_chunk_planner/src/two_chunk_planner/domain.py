# SPDX-License-Identifier: GPL-3.0-or-later
"""Canonical two-face domain, classification, and boundary metrics."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np

from two_chunk_planner.geometry import Vec3, add, angular_distance_deg, cross, dot, great_circle_samples, norm, point_to_arc_distance_deg, scale, unit
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


@dataclass(frozen=True)
class PathCoverageBatch:
    """Compact path metrics for an ordered batch of orientations.

    ``uncertain`` is deliberately conservative.  A true value requires the
    caller to use the scalar implementation before a result can affect a
    keeper.  The normal, well-separated case stays entirely vectorized.
    """

    inside_counts: np.ndarray
    coverage: np.ndarray
    external_margins: np.ndarray
    global_external_margins: np.ndarray
    endpoint_margins: np.ndarray
    uncertain: np.ndarray


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
        self._prepared_external = tuple((unit(arc.start_local), unit(arc.end_local), unit(cross(unit(arc.start_local), unit(arc.end_local))), angular_distance_deg(unit(arc.start_local), unit(arc.end_local)), arc.name) for arc in self._external)
        self._external_start = np.asarray([item[0] for item in self._prepared_external], dtype=np.float64)
        self._external_end = np.asarray([item[1] for item in self._prepared_external], dtype=np.float64)
        self._external_normal = np.asarray([item[2] for item in self._prepared_external], dtype=np.float64)
        self._external_arc = np.asarray([item[3] for item in self._prepared_external], dtype=np.float64)

    @staticmethod
    def _prepared_arc_distance(point: Vec3, start: Vec3, end: Vec3, normal: Vec3, arc_length: float) -> float:
        """Equivalent to point_to_arc_distance_deg with fixed arc work cached."""
        p = unit(point)
        projected = add(p, scale(-dot(p, normal), normal))
        if norm(projected) > 1.0e-14:
            q = unit(projected)
            if abs((angular_distance_deg(start, q) + angular_distance_deg(q, end)) - arc_length) < 1.0e-8:
                return angular_distance_deg(p, q)
            q = scale(-1.0, q)
            if abs((angular_distance_deg(start, q) + angular_distance_deg(q, end)) - arc_length) < 1.0e-8:
                return angular_distance_deg(p, q)
        return min(angular_distance_deg(p, start), angular_distance_deg(p, end))

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

    def _classification_components(self, local: Vec3) -> tuple[str, float | None, float | None, str | None, float, float, float | None, bool, bool, bool]:
        """Classify a local vector without allocating a public audit object."""
        valid = self._chunk_candidates(local)
        c1, c2 = angular_distance_deg(local, self.c1_local), angular_distance_deg(local, self.c2_local)
        if len(valid) == 2:
            label = "shared_interface"
        elif len(valid) == 1:
            label = valid[0][0]
        else:
            return "outside_two_chunk_domain", None, None, None, c1, c2, None, False, False, False
        shared = point_to_arc_distance_deg(local, self.interface.start_local, self.interface.end_local)
        external, external_name = min((self._prepared_arc_distance(local, start, end, normal, arc_length), name) for start, end, normal, arc_length, name in self._prepared_external)
        return label, shared, external, external_name, c1, c2, external, shared <= EPS_DEG, min(c1, c2) <= EPS_DEG, external <= EPS_DEG

    def classify(self, latitude_deg: float, longitude_deg: float) -> PointClassification:
        local = self.transform.geographic_to_local(latitude_deg, longitude_deg)
        valid = self._chunk_candidates(local)
        label, shared, external, external_name, c1, c2, external_margin, on_interface, on_endpoint, on_external = self._classification_components(local)
        if label == "outside_two_chunk_domain":
            return PointClassification(latitude_deg, longitude_deg, label, None, None, None, None, c1, c2, None, None, False, False, False)
        chunk, xi, eta = valid[0]
        return PointClassification(
            latitude_deg, longitude_deg, label, xi, eta, chunk, shared, c1, c2, external, external_name,
            on_interface, on_endpoint, on_external,
        )

    def classification_components_for_global_vector(self, vector: Vec3) -> tuple[str, float, float, float | None, bool, bool, bool]:
        """Return the scalar fields needed by the search for a prepared point."""
        label, _, _, _, c1, c2, external, on_interface, on_endpoint, on_external = self._classification_components(self.transform.global_to_local(vector))
        return label, c1, c2, external, on_interface, on_endpoint, on_external

    def path_coverage_for_global_vectors(self, vectors: tuple[Vec3, ...]) -> tuple[int, float, float | None, float | None]:
        """Compute path metrics without building per-point audit objects."""
        inside = 0
        external_margins: list[float] = []
        endpoint_margins: list[float] = []
        for vector in vectors:
            local = self.transform.global_to_local(vector)
            valid = self._chunk_candidates(local)
            c1, c2 = angular_distance_deg(local, self.c1_local), angular_distance_deg(local, self.c2_local)
            if valid:
                label = "shared_interface" if len(valid) == 2 else valid[0][0]
                external = min(self._prepared_arc_distance(local, start, end, normal, arc_length) for start, end, normal, arc_length, _ in self._prepared_external)
            else:
                label, external = "outside_two_chunk_domain", None
            if label != "outside_two_chunk_domain":
                inside += 1
            if external is not None:
                external_margins.append(external)
            endpoint_margins.append(min(c1, c2))
        count = len(vectors)
        return inside, inside / count if count else 0.0, min(external_margins) if external_margins else None, min(endpoint_margins) if endpoint_margins else None

    def path_coverage_for_global_array(self, vectors: np.ndarray, block_size: int = 8192) -> tuple[int, float, float | None, float | None]:
        """Batch equivalent of ``path_coverage_for_global_vectors`` for search."""
        if vectors.ndim != 2 or vectors.shape[1] != 3:
            raise ValueError("path vectors must have shape (N, 3)")
        matrix = np.asarray(self.transform.matrix(), dtype=np.float64)
        c1 = np.asarray(self.c1_local, dtype=np.float64)
        c2 = np.asarray(self.c2_local, dtype=np.float64)
        inside_count = 0
        external_min: float | None = None
        external_index: int | None = None
        endpoint_min: float | None = None
        radians_to_degrees = 180.0 / math.pi
        for start in range(0, len(vectors), block_size):
            local = vectors[start:start + block_size] @ matrix
            local /= np.linalg.norm(local, axis=1)[:, None]
            x, y, z = local[:, 0], local[:, 1], local[:, 2]
            with np.errstate(divide="ignore", invalid="ignore"):
                first = (z > 0.0) & (np.abs(np.arctan(y / z) * radians_to_degrees) <= HALF_WIDTH_DEG + EPS_DEG) & (np.abs(np.arctan(-x / z) * radians_to_degrees) <= HALF_WIDTH_DEG + EPS_DEG)
                second = (y < 0.0) & (np.abs(np.arctan((-z) / y) * radians_to_degrees) <= HALF_WIDTH_DEG + EPS_DEG) & (np.abs(np.arctan(x / y) * radians_to_degrees) <= HALF_WIDTH_DEG + EPS_DEG)
            inside = first | second
            inside_count += int(np.count_nonzero(inside))
            endpoint = np.minimum(np.arccos(np.clip(local @ c1, -1.0, 1.0)), np.arccos(np.clip(local @ c2, -1.0, 1.0))) * radians_to_degrees
            current_endpoint = float(np.min(endpoint))
            endpoint_min = current_endpoint if endpoint_min is None else min(endpoint_min, current_endpoint)
            if not np.any(inside):
                continue
            points = local[inside]
            distances = np.full(len(points), np.inf, dtype=np.float64)
            for arc_start, arc_end, normal, arc_length in zip(self._external_start, self._external_end, self._external_normal, self._external_arc):
                projection = points - (points @ normal)[:, None] * normal
                projection_norm = np.linalg.norm(projection, axis=1)
                valid_projection = projection_norm > 1.0e-14
                q = np.zeros_like(projection)
                q[valid_projection] = projection[valid_projection] / projection_norm[valid_projection, None]
                qa = np.arccos(np.clip(q @ arc_start, -1.0, 1.0)) * radians_to_degrees
                qb = np.arccos(np.clip(q @ arc_end, -1.0, 1.0)) * radians_to_degrees
                on_arc = valid_projection & (np.abs(qa + qb - arc_length) < 1.0e-8)
                q_neg = -q
                nqa = np.arccos(np.clip(q_neg @ arc_start, -1.0, 1.0)) * radians_to_degrees
                nqb = np.arccos(np.clip(q_neg @ arc_end, -1.0, 1.0)) * radians_to_degrees
                on_neg = valid_projection & ~on_arc & (np.abs(nqa + nqb - arc_length) < 1.0e-8)
                candidate = np.minimum(np.arccos(np.clip(points @ arc_start, -1.0, 1.0)), np.arccos(np.clip(points @ arc_end, -1.0, 1.0))) * radians_to_degrees
                candidate[on_arc] = np.arccos(np.clip(np.sum(points[on_arc] * q[on_arc], axis=1), -1.0, 1.0)) * radians_to_degrees
                candidate[on_neg] = np.arccos(np.clip(np.sum(points[on_neg] * q_neg[on_neg], axis=1), -1.0, 1.0)) * radians_to_degrees
                distances = np.minimum(distances, candidate)
            current_external = float(np.min(distances))
            if external_min is None or current_external < external_min:
                external_min = current_external
                external_index = start + int(np.flatnonzero(inside)[int(np.argmin(distances))])
        # Re-evaluate the selected minimum through the scalar implementation so
        # serialized margins and ranking retain the pre-batch floating result.
        if external_index is not None:
            local = self.transform.global_to_local(tuple(float(value) for value in vectors[external_index]))
            external_min = min(self._prepared_arc_distance(local, arc_start, arc_end, normal, arc_length) for arc_start, arc_end, normal, arc_length, _ in self._prepared_external)
        count = len(vectors)
        return inside_count, inside_count / count if count else 0.0, external_min, endpoint_min

    def boundary_distance(self, latitude_deg: float, longitude_deg: float) -> tuple[float | None, str | None]:
        result = self.classify(latitude_deg, longitude_deg)
        return result.external_boundary_margin_deg, result.external_boundary_name

    def interface_distance(self, latitude_deg: float, longitude_deg: float) -> float:
        local = self.transform.geographic_to_local(latitude_deg, longitude_deg)
        return point_to_arc_distance_deg(local, self.interface.start_local, self.interface.end_local)

    def global_arc(self, arc: BoundaryArc, count: int = 65) -> list[tuple[float, float]]:
        return [self.transform.local_to_geographic(point) for point in great_circle_samples(arc.start_local, arc.end_local, count)]

    def outline(self) -> dict[str, list[list[tuple[float, float]]]]:
        return {"interface": [self.global_arc(self.interface)], "external": [self.global_arc(arc) for arc in self.external_boundaries]}

    def path_coverage(self, points: list[tuple[float, float]]) -> dict:
        classifications = [self.classify(latitude, longitude) for latitude, longitude in points]
        inside = sum(item.classification != "outside_two_chunk_domain" for item in classifications)
        margins = [item.external_boundary_margin_deg for item in classifications if item.external_boundary_margin_deg is not None]
        endpoints = [min(item.c1_margin_deg, item.c2_margin_deg) for item in classifications]
        return {"sample_count": len(points), "inside_count": inside, "coverage_fraction": inside / len(points) if points else 0.0, "minimum_external_boundary_margin_deg": min(margins) if margins else None, "minimum_endpoint_margin_deg": min(endpoints) if endpoints else None, "method": "conservative_heuristic_sampled_path"}


def path_coverage_for_global_arrays(
    vectors: np.ndarray,
    path_offsets: np.ndarray,
    transforms: tuple[EulerTransform, ...],
    block_size: int = 4096,
) -> PathCoverageBatch:
    """Evaluate all paths for a small ordered orientation batch.

    The paths remain in global coordinates.  Only the two chunk endpoints,
    six finite-arc endpoints/normals, and the three local axes are rotated for
    each orientation.  This avoids materialising a complete local-vector
    array for every orientation while retaining every supplied path point.
    """
    if vectors.ndim != 2 or vectors.shape[1] != 3:
        raise ValueError("path vectors must have shape (N, 3)")
    if path_offsets.ndim != 1 or len(path_offsets) < 2 or path_offsets[0] != 0 or path_offsets[-1] != len(vectors):
        raise ValueError("path offsets must span path vectors")
    if not transforms:
        empty = np.empty((0, len(path_offsets) - 1), dtype=np.float64)
        return PathCoverageBatch(np.empty((0, len(path_offsets) - 1), dtype=np.int64), empty, np.empty(0, dtype=np.float64), empty, np.empty(0, dtype=bool))

    matrices = np.asarray([transform.matrix() for transform in transforms], dtype=np.float64)
    # Matrix columns are the local axes expressed globally.  Rotating the
    # small, fixed boundary vectors is substantially cheaper than rotating all
    # path vectors once per candidate.
    local_external = CanonicalTwoChunkDomain(EulerTransform(0.0, 0.0, 0.0))
    starts_local = local_external._external_start
    ends_local = local_external._external_end
    normals_local = local_external._external_normal
    arc_lengths = local_external._external_arc
    global_starts = np.einsum("oij,aj->oai", matrices, starts_local)
    global_ends = np.einsum("oij,aj->oai", matrices, ends_local)
    global_normals = np.einsum("oij,aj->oai", matrices, normals_local)
    # For q on an arc's great circle, q·(n×start) and q·(end×n)
    # locate q along the oriented finite arc.  This is equivalent to the
    # previous qa+qb arc-membership test but avoids four acos calls per arc.
    global_start_tangents = np.cross(global_normals, global_starts)
    global_end_tangents = np.cross(global_ends, global_normals)

    orientation_count = len(transforms)
    path_count = len(path_offsets) - 1
    lengths = np.diff(path_offsets)
    inside_counts = np.zeros((orientation_count, path_count), dtype=np.int64)
    external = np.full((orientation_count, path_count), np.inf, dtype=np.float64)
    endpoints = np.full((orientation_count, path_count), np.inf, dtype=np.float64)
    global_external = np.full(orientation_count, np.inf, dtype=np.float64)
    global_external_index = np.full(orientation_count, -1, dtype=np.int64)
    uncertain = np.zeros(orientation_count, dtype=bool)
    radians_to_degrees = 180.0 / math.pi
    # This guard is below the existing EPS and arc tolerances.  It captures
    # only round-off-sensitive decisions, not ordinary near-boundary geometry.
    guard_deg = 1.0e-10
    arc_tolerance = math.sin(math.radians(1.0e-8))
    arc_guard = math.sin(math.radians(guard_deg))

    for block_start in range(0, len(vectors), block_size):
        block_end = min(len(vectors), block_start + block_size)
        points = vectors[block_start:block_end]
        # local[o, p, component] is block-sized only.  The boundary-distance
        # work below uses global points and rotated fixed boundaries.
        local = np.matmul(points[None, :, :], matrices)
        local /= np.linalg.norm(local, axis=2)[:, :, None]
        x, y, z = local[:, :, 0], local[:, :, 1], local[:, :, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            first_x = np.arctan(-x / z) * radians_to_degrees
            first_y = np.arctan(y / z) * radians_to_degrees
            second_x = np.arctan(x / y) * radians_to_degrees
            second_z = np.arctan((-z) / y) * radians_to_degrees
            first = (z > 0.0) & (np.abs(first_x) <= HALF_WIDTH_DEG + EPS_DEG) & (np.abs(first_y) <= HALF_WIDTH_DEG + EPS_DEG)
            second = (y < 0.0) & (np.abs(second_x) <= HALF_WIDTH_DEG + EPS_DEG) & (np.abs(second_z) <= HALF_WIDTH_DEG + EPS_DEG)
        inside = first | second
        near_chunk = (
            (np.abs(np.abs(first_x) - (HALF_WIDTH_DEG + EPS_DEG)) <= guard_deg)
            | (np.abs(np.abs(first_y) - (HALF_WIDTH_DEG + EPS_DEG)) <= guard_deg)
            | (np.abs(np.abs(second_x) - (HALF_WIDTH_DEG + EPS_DEG)) <= guard_deg)
            | (np.abs(np.abs(second_z) - (HALF_WIDTH_DEG + EPS_DEG)) <= guard_deg)
        )
        uncertain |= np.any(near_chunk, axis=1)
        distances = np.full((orientation_count, len(points)), np.inf, dtype=np.float64)
        for orientation in range(orientation_count):
            point_indices = np.flatnonzero(inside[orientation])
            if not len(point_indices):
                continue
            interior = points[point_indices]
            interior_distances = np.full(len(interior), np.inf, dtype=np.float64)
            for arc_index in range(len(arc_lengths)):
                normal = global_normals[orientation, arc_index]
                start = global_starts[orientation, arc_index]
                end = global_ends[orientation, arc_index]
                start_tangent = global_start_tangents[orientation, arc_index]
                end_tangent = global_end_tangents[orientation, arc_index]
                normal_dot = interior @ normal
                projection = interior - normal_dot[:, None] * normal
                projection_norm = np.linalg.norm(projection, axis=1)
                valid_projection = projection_norm > 1.0e-14
                q = np.divide(projection, projection_norm[:, None], out=np.zeros_like(projection), where=valid_projection[:, None])
                start_coordinate = q @ start_tangent
                end_coordinate = q @ end_tangent
                on_arc = valid_projection & (start_coordinate >= -arc_tolerance) & (end_coordinate >= -arc_tolerance)
                on_neg = valid_projection & ~on_arc & (start_coordinate <= arc_tolerance) & (end_coordinate <= arc_tolerance)
                candidate = np.minimum(
                    np.arccos(np.clip(interior @ start, -1.0, 1.0)),
                    np.arccos(np.clip(interior @ end, -1.0, 1.0)),
                ) * radians_to_degrees
                projected_distance = np.arctan2(np.abs(normal_dot), projection_norm) * radians_to_degrees
                candidate[on_arc | on_neg] = projected_distance[on_arc | on_neg]
                near_arc = (np.abs(np.abs(start_coordinate) - arc_tolerance) <= arc_guard) | (np.abs(np.abs(end_coordinate) - arc_tolerance) <= arc_guard)
                uncertain[orientation] |= bool(np.any(near_arc))
                interior_distances = np.minimum(interior_distances, candidate)
            distances[orientation, point_indices] = interior_distances
        # Blocks are small; this loop is over path fragments, never points.
        first_path = int(np.searchsorted(path_offsets, block_start, side="right") - 1)
        last_path = int(np.searchsorted(path_offsets, block_end - 1, side="right") - 1)
        for path_index in range(first_path, last_path + 1):
            start = max(block_start, int(path_offsets[path_index])) - block_start
            end = min(block_end, int(path_offsets[path_index + 1])) - block_start
            inside_counts[:, path_index] += np.count_nonzero(inside[:, start:end], axis=1)
            external[:, path_index] = np.minimum(external[:, path_index], np.min(distances[:, start:end], axis=1))
        block_minimum = np.min(distances, axis=1)
        for orientation, value in enumerate(block_minimum):
            if value < global_external[orientation]:
                global_external[orientation] = value
                global_external_index[orientation] = block_start + int(np.argmin(distances[orientation]))

    external[~np.isfinite(external)] = np.nan
    # Ranking uses the minimum over all paths, not each individual path
    # margin.  Recompute only that single winning point by the legacy scalar
    # arc routine, preserving the exact scalar score without 127 rechecks.
    for orientation, point_index in enumerate(global_external_index):
        if point_index < 0:
            continue
        domain = CanonicalTwoChunkDomain(transforms[orientation])
        local = domain.transform.global_to_local(tuple(float(value) for value in vectors[point_index]))
        global_external[orientation] = min(domain._prepared_arc_distance(local, start, end, normal, arc_length) for start, end, normal, arc_length, _ in domain._prepared_external)
    global_external[~np.isfinite(global_external)] = np.nan
    return PathCoverageBatch(inside_counts, inside_counts / lengths[None, :], external, global_external, endpoints, uncertain)
