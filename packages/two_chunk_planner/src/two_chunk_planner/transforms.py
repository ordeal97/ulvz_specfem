# SPDX-License-Identifier: GPL-3.0-or-later
"""SPECFEM-compatible Euler transforms for the canonical regional geometry."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from two_chunk_planner.geometry import DEG, Vec3, latlon_to_unit, normalize_longitude, unit_to_latlon

# WGS84-like Earth value used by current SPECFEM Earth model constants.
# The accepted fixture has ELLIPTICITY=.false.; ellipticity conversion remains
# explicit and is recorded whenever it is enabled.
EARTH_ONE_MINUS_F_SQUARED = 0.9933056200098587


def geocentric_colatitude(latitude_deg: float, ellipticity: bool) -> float:
    if not ellipticity:
        return math.pi / 2.0 - latitude_deg * DEG
    return math.pi / 2.0 - math.atan(EARTH_ONE_MINUS_F_SQUARED * math.tan(latitude_deg * DEG))


def geographic_latitude(colatitude_rad: float, ellipticity: bool) -> float:
    if ellipticity:
        colatitude_rad = math.atan(math.tan(colatitude_rad) / EARTH_ONE_MINUS_F_SQUARED)
    return math.degrees(math.pi / 2.0 - colatitude_rad)


@dataclass(frozen=True)
class EulerTransform:
    center_latitude_deg: float
    center_longitude_deg: float
    gamma_deg: float
    ellipticity: bool = False

    @lru_cache(maxsize=None)
    def matrix(self) -> tuple[tuple[float, float, float], ...]:
        alpha = self.center_longitude_deg * DEG
        beta = geocentric_colatitude(self.center_latitude_deg, self.ellipticity)
        gamma = self.gamma_deg * DEG
        sa, ca, sb, cb, sg, cg = math.sin(alpha), math.cos(alpha), math.sin(beta), math.cos(beta), math.sin(gamma), math.cos(gamma)
        return (
            (cg * cb * ca - sg * sa, -sg * cb * ca - cg * sa, sb * ca),
            (cg * cb * sa + sg * ca, -sg * cb * sa + cg * ca, sb * sa),
            (-cg * sb, sg * sb, cb),
        )

    def local_to_global(self, vector: Vec3) -> Vec3:
        matrix = self.matrix()
        return tuple(sum(matrix[row][column] * vector[column] for column in range(3)) for row in range(3))  # type: ignore[return-value]

    def global_to_local(self, vector: Vec3) -> Vec3:
        matrix = self.matrix()
        return tuple(sum(matrix[row][column] * vector[row] for row in range(3)) for column in range(3))  # type: ignore[return-value]

    def geographic_to_local(self, latitude_deg: float, longitude_deg: float) -> Vec3:
        theta = geocentric_colatitude(latitude_deg, self.ellipticity)
        vector = (math.sin(theta) * math.cos(longitude_deg * DEG), math.sin(theta) * math.sin(longitude_deg * DEG), math.cos(theta))
        return self.global_to_local(vector)

    def local_to_geographic(self, vector: Vec3) -> tuple[float, float]:
        x, y, z = self.local_to_global(vector)
        colatitude = math.acos(max(-1.0, min(1.0, z / math.sqrt(x * x + y * y + z * z))))
        return geographic_latitude(colatitude, self.ellipticity), normalize_longitude(math.degrees(math.atan2(y, x)))
