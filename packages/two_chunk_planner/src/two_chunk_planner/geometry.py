# SPDX-License-Identifier: GPL-3.0-or-later
"""Small spherical-geometry primitives used by the planner.

All public geographic coordinates are degrees.  Cartesian coordinates are
unit vectors unless a caller explicitly supplies a radius.
"""
from __future__ import annotations

import math
from typing import Iterable

Vec3 = tuple[float, float, float]
EARTH_RADIUS_KM = 6371.0
DEG = math.pi / 180.0


def dot(a: Vec3, b: Vec3) -> float:
    return sum(x * y for x, y in zip(a, b))


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3:
    length = norm(a)
    if length == 0.0:
        raise ValueError("zero Cartesian vector")
    return (a[0] / length, a[1] / length, a[2] / length)


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(value: float, vector: Vec3) -> Vec3:
    return (value * vector[0], value * vector[1], value * vector[2])


def latlon_to_unit(latitude_deg: float, longitude_deg: float) -> Vec3:
    lat, lon = latitude_deg * DEG, longitude_deg * DEG
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def unit_to_latlon(vector: Vec3) -> tuple[float, float]:
    x, y, z = unit(vector)
    return math.degrees(math.asin(max(-1.0, min(1.0, z)))), normalize_longitude(math.degrees(math.atan2(y, x)))


def normalize_longitude(longitude_deg: float) -> float:
    value = (longitude_deg + 180.0) % 360.0 - 180.0
    return 180.0 if value == -180.0 and longitude_deg > 0.0 else value


def angular_distance_deg(a: Vec3, b: Vec3) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(unit(a), unit(b))))))


def angular_distance_km(a: Vec3, b: Vec3, radius_km: float = EARTH_RADIUS_KM) -> float:
    return radius_km * math.radians(angular_distance_deg(a, b))


def slerp(a: Vec3, b: Vec3, fraction: float) -> Vec3:
    angle = math.radians(angular_distance_deg(a, b))
    if angle < 1.0e-14:
        return unit(a)
    sin_angle = math.sin(angle)
    return unit(add(scale(math.sin((1.0 - fraction) * angle) / sin_angle, a), scale(math.sin(fraction * angle) / sin_angle, b)))


def great_circle_samples(a: Vec3, b: Vec3, count: int) -> list[Vec3]:
    if count < 2:
        raise ValueError("great-circle sample count must be at least two")
    return [slerp(a, b, index / (count - 1)) for index in range(count)]


def point_to_arc_distance_deg(point: Vec3, start: Vec3, end: Vec3) -> float:
    """Minimum angular distance to the finite minor great-circle arc."""
    p, a, b = unit(point), unit(start), unit(end)
    normal = cross(a, b)
    if norm(normal) < 1.0e-14:
        return min(angular_distance_deg(p, a), angular_distance_deg(p, b))
    normal = unit(normal)
    projected = add(p, scale(-dot(p, normal), normal))
    if norm(projected) > 1.0e-14:
        q = unit(projected)
        arc = angular_distance_deg(a, b)
        if abs((angular_distance_deg(a, q) + angular_distance_deg(q, b)) - arc) < 1.0e-8:
            return angular_distance_deg(p, q)
        q = scale(-1.0, q)
        if abs((angular_distance_deg(a, q) + angular_distance_deg(q, b)) - arc) < 1.0e-8:
            return angular_distance_deg(p, q)
    return min(angular_distance_deg(p, a), angular_distance_deg(p, b))


def chord_length_km(points: Iterable[tuple[float, float, float]], radius_km: float = EARTH_RADIUS_KM) -> float:
    """Sum 3-D chord lengths for (latitude, longitude, depth_km) samples."""
    vectors = [scale(max(0.0, radius_km - depth), latlon_to_unit(lat, lon)) for lat, lon, depth in points]
    return sum(norm(add(right, scale(-1.0, left))) for left, right in zip(vectors, vectors[1:]))


def split_dateline(points: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
    """Split lon/lat lines for Matplotlib rather than drawing a map-wide chord."""
    if not points:
        return []
    result: list[list[tuple[float, float]]] = [[points[0]]]
    for point in points[1:]:
        if abs(point[1] - result[-1][-1][1]) > 180.0:
            result.append([point])
        else:
            result[-1].append(point)
    return result
