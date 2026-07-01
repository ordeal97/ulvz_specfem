from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from ulvz_mesh_viz.data import PlotDataError


def ensure_section_coordinates(
    points: pd.DataFrame, section_azimuth_deg: float
) -> pd.DataFrame:
    result = points.copy()
    point_az = np.deg2rad(result["point_azimuth_deg"].astype(float).to_numpy())
    lateral = result["lateral_distance_km"].astype(float).to_numpy()
    north = lateral * np.cos(point_az)
    east = lateral * np.sin(point_az)
    section_az = np.deg2rad(section_azimuth_deg)
    profile_east = np.sin(section_az)
    profile_north = np.cos(section_az)
    result["section_azimuth_deg"] = float(section_azimuth_deg)
    result["section_distance_km"] = east * profile_east + north * profile_north
    result["cross_section_offset_km"] = np.abs(east * profile_north - north * profile_east)
    return result


def auto_section_half_width_km(points: pd.DataFrame) -> float:
    near = points[points["height_above_cmb_km"] >= 0].copy()
    if len(near) < 3:
        return 100.0
    cutoff = near["radius_km"].quantile(0.1)
    near = near[near["radius_km"] <= cutoff]
    if len(near) < 3:
        near = points[points["height_above_cmb_km"] >= 0].copy()
    point_az = np.deg2rad(near["point_azimuth_deg"].astype(float).to_numpy())
    lateral = near["lateral_distance_km"].astype(float).to_numpy()
    xy = np.column_stack([lateral * np.sin(point_az), lateral * np.cos(point_az)])
    if len(xy) < 3:
        return 100.0
    tree = cKDTree(xy)
    distances, _ = tree.query(xy, k=2)
    median_spacing = float(np.median(distances[:, 1]))
    if not np.isfinite(median_spacing) or median_spacing <= 0:
        return 100.0
    return 2.0 * median_spacing


def nearest_neighbor_spacing(points: pd.DataFrame) -> pd.DataFrame:
    if len(points) < 3:
        raise PlotDataError("insufficient deduplicated points for spacing statistics")
    point_az = np.deg2rad(points["point_azimuth_deg"].astype(float).to_numpy())
    lateral = points["lateral_distance_km"].astype(float).to_numpy()
    xy = np.column_stack([lateral * np.sin(point_az), lateral * np.cos(point_az)])
    tree = cKDTree(xy)
    distances, _ = tree.query(xy, k=2)
    result = points[["rank", "iglob", "category"]].copy()
    result["nearest_neighbor_spacing_km"] = distances[:, 1]
    return result
