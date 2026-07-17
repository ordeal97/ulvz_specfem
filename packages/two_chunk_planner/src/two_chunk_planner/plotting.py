# SPDX-License-Identifier: GPL-3.0-or-later
"""Static, dependency-light planner map."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.geometry import angular_distance_deg, latlon_to_unit, split_dateline
from two_chunk_planner.io import Source, Station, TargetRegion
from two_chunk_planner.objective import target_samples
from two_chunk_planner.paths import PathRecord


def write_map(path, domain: CanonicalTwoChunkDomain, source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None) -> None:
    figure, axis = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    for line in domain.outline()["external"]:
        for part in split_dateline(line):
            axis.plot([point[1] for point in part], [point[0] for point in part], color="black", linewidth=1.2)
    for line in domain.outline()["interface"]:
        for part in split_dateline(line):
            axis.plot([point[1] for point in part], [point[0] for point in part], color="tab:orange", linewidth=2.0, label="AB–AC interface")
    for endpoint, color in (("C1", "tab:red"), ("C2", "tab:purple")):
        latitude, longitude = domain.transform.local_to_geographic(domain.c1_local if endpoint == "C1" else domain.c2_local)
        axis.scatter([longitude], [latitude], color=color, marker="x", s=48, label=endpoint)
    for record in paths:
        for part in split_dateline(record.points):
            axis.plot([point[1] for point in part], [point[0] for point in part], color="0.6", linewidth=0.7, alpha=0.7)
    if target is not None:
        points, _ = target_samples(target)
        for index, part in enumerate(split_dateline(points)):
            axis.plot([point[1] for point in part], [point[0] for point in part], color="tab:green", linewidth=1.0, alpha=0.8, label="target region" if index == 0 else None)
    axis.scatter([source.longitude_deg], [source.latitude_deg], marker="*", s=130, color="gold", edgecolor="black", label="source", zorder=3)
    axis.scatter([station.longitude_deg for station in stations], [station.latitude_deg for station in stations], s=26, color="tab:blue", label="stations", zorder=3)
    source_vector = latlon_to_unit(source.latitude_deg, source.longitude_deg)
    boundary_points = [(latitude, longitude) for arc in domain.external_boundaries for latitude, longitude in domain.global_arc(arc, 181)]
    closest = min(boundary_points, key=lambda point: angular_distance_deg(source_vector, latlon_to_unit(*point)))
    axis.scatter([closest[1]], [closest[0]], marker="^", s=38, color="black", label="nearest outer boundary (sampled)", zorder=3)
    if target is not None:
        axis.set_title(f"Canonical two-chunk candidate — target: {target.name}")
    else:
        axis.set_title("Canonical two-chunk candidate")
    axis.set(xlim=(-180, 180), ylim=(-90, 90), xlabel="longitude (deg)", ylabel="latitude (deg)")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="lower left", fontsize=8)
    figure.savefig(path, dpi=160)
    plt.close(figure)
