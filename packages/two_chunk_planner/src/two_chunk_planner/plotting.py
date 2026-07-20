# SPDX-License-Identifier: GPL-3.0-or-later
"""Static, dependency-light planner map."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.geometry import angular_distance_deg, latlon_to_unit, split_dateline
from two_chunk_planner.io import Source, Station, TargetRegion
from two_chunk_planner.objective import target_samples
from two_chunk_planner.paths import PathRecord


def write_map(path, domain: CanonicalTwoChunkDomain, source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None) -> None:
    figure, axis = plt.subplots(figsize=(11, 5.5), constrained_layout=True)
    def plot_wrapped_arc(arc, color, linewidth, label=None):
        """Plot one finite arc without joining it to any neighbouring arc."""
        for part in split_dateline(domain.global_arc(arc, 181)):
            # split_dateline starts a new part when abs(delta longitude) > 180°.
            axis.plot([point[1] for point in part], [point[0] for point in part], color=color, linewidth=linewidth, label=label)
            label = None

    for index, arc in enumerate(domain.external_boundaries):
        plot_wrapped_arc(arc, "black", 1.2, "outer boundary" if index == 0 else None)
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


def write_globe(path, domain: CanonicalTwoChunkDomain, source: Source, stations: list[Station], paths: list[PathRecord], target: TargetRegion | None) -> None:
    """Write a fixed-view, spherical companion to the geographic map."""
    figure = plt.figure(figsize=(8, 8), constrained_layout=True)
    axis = figure.add_subplot(projection="3d")
    longitude, latitude = np.meshgrid(np.linspace(-np.pi, np.pi, 121), np.linspace(-np.pi / 2, np.pi / 2, 61))
    axis.plot_surface(np.cos(latitude) * np.cos(longitude), np.cos(latitude) * np.sin(longitude), np.sin(latitude), color="0.85", alpha=0.28, linewidth=0, shade=False)

    source_vector = np.asarray(latlon_to_unit(source.latitude_deg, source.longitude_deg))
    station_vectors = np.asarray([latlon_to_unit(item.latitude_deg, item.longitude_deg) for item in stations])
    # This is also the camera-facing hemisphere used to hide back-side arcs.
    focus = source_vector + station_vectors.mean(axis=0)
    focus /= np.linalg.norm(focus)

    def draw(points, color, width, label=None, alpha=1.0, visible_only=False):
        vectors = np.asarray([latlon_to_unit(*point) for point in points])
        if not visible_only:
            axis.plot(vectors[:, 0], vectors[:, 1], vectors[:, 2], color=color, linewidth=width, alpha=alpha, label=label)
            return
        facing = vectors @ focus >= 0.0
        start = None
        for index, show in enumerate(facing):
            if show and start is None:
                start = index
            if start is not None and (not show or index == len(facing) - 1):
                stop = index if not show else index + 1
                axis.plot(vectors[start:stop, 0], vectors[start:stop, 1], vectors[start:stop, 2], color=color, linewidth=width, alpha=alpha, label=label)
                label = None
                start = None

    for index, arc in enumerate(domain.external_boundaries):
        draw(domain.global_arc(arc, 181), "black", 1.6, "outer boundary" if index == 0 else None, visible_only=True)
    draw(domain.global_arc(domain.interface, 181), "tab:orange", 2.4, "AB–AC interface", visible_only=True)
    for record in paths:
        draw(record.points, "0.55", 0.55, alpha=0.45)
    if target is not None:
        points, _ = target_samples(target)
        draw(points, "tab:green", 1.2, "target region", alpha=0.9)
    axis.scatter(*source_vector, marker="*", s=120, color="gold", edgecolor="black", label="source")
    axis.scatter(station_vectors[:, 0], station_vectors[:, 1], station_vectors[:, 2], s=14, color="tab:blue", label="stations")
    # View from the midpoint of source and station-cluster directions.  Global
    # Cartesian z remains geographic north, so north is visually up and south down.

    def draw_visible_grid(x, y, z):
        """Draw only the hemisphere facing the fixed camera direction."""
        visible = x * focus[0] + y * focus[1] + z * focus[2] >= 0.0
        start = None
        for index, show in enumerate(visible):
            if show and start is None:
                start = index
            if start is not None and (not show or index == len(visible) - 1):
                stop = index if not show else index + 1
                axis.plot(x[start:stop], y[start:stop], z[start:stop], color="0.65", linewidth=0.45, alpha=0.55)
                start = None

    grid_longitudes = np.linspace(-np.pi, np.pi, 181)
    grid_latitudes = np.linspace(-np.pi / 2, np.pi / 2, 91)
    for latitude_deg in (-60, -30, 30, 60):
        latitude_rad = np.radians(latitude_deg)
        draw_visible_grid(np.cos(latitude_rad) * np.cos(grid_longitudes), np.cos(latitude_rad) * np.sin(grid_longitudes), np.full_like(grid_longitudes, np.sin(latitude_rad)))
    for longitude_deg in range(-180, 181, 60):
        longitude_rad = np.radians(longitude_deg)
        draw_visible_grid(np.cos(grid_latitudes) * np.cos(longitude_rad), np.cos(grid_latitudes) * np.sin(longitude_rad), np.sin(grid_latitudes))

    def latitude_label(value):
        return "0°" if value == 0 else f"{abs(value)}°{'N' if value > 0 else 'S'}"

    def longitude_label(value):
        if value in (-180, 180):
            return "180°"
        return "0°" if value == 0 else f"{abs(value)}°{'E' if value > 0 else 'W'}"

    # One label per visible latitude/longitude line: selecting the point most
    # directly facing the camera avoids duplicate back-side labels and overlap.
    for latitude_deg in (-60, -30, 30, 60):
        latitude_rad = np.radians(latitude_deg)
        vectors = np.column_stack((np.cos(latitude_rad) * np.cos(grid_longitudes), np.cos(latitude_rad) * np.sin(grid_longitudes), np.full_like(grid_longitudes, np.sin(latitude_rad))))
        facing = vectors @ focus
        if float(np.max(facing)) < 0.20:
            continue
        index = int(np.argmax(facing))
        point = 1.035 * vectors[index]
        axis.text(*point, latitude_label(latitude_deg), color="0.35", fontsize=7)
    for longitude_deg in (-120, -60, 60, 120):
        longitude_rad = np.radians(longitude_deg)
        vectors = np.column_stack((np.cos(grid_latitudes) * np.cos(longitude_rad), np.cos(grid_latitudes) * np.sin(longitude_rad), np.sin(grid_latitudes)))
        facing = vectors @ focus
        if float(np.max(facing)) < 0.20:
            continue
        index = int(np.argmax(facing))
        point = 1.035 * vectors[index]
        axis.text(*point, longitude_label(longitude_deg), color="0.35", fontsize=7)
    focus_latitude = np.degrees(np.arcsin(focus[2]))
    focus_longitude = np.degrees(np.arctan2(focus[1], focus[0]))
    axis.view_init(elev=focus_latitude, azim=focus_longitude)
    axis.set_box_aspect((1, 1, 1))
    axis.set_axis_off()
    axis.set_title("Canonical two-chunk candidate — spherical view")
    axis.legend(loc="upper left", fontsize=8)
    figure.savefig(path, dpi=180, transparent=False)
    plt.close(figure)
