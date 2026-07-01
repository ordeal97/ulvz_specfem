#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt

from ulvz_mesh_viz.data import PlotDataError, load_dataset, unique_points
from ulvz_mesh_viz.geometry import auto_section_half_width_km, ensure_section_coordinates
from ulvz_mesh_viz.plotting import (
    add_common_args,
    add_disclaimer,
    category_scatter,
    parse_formats,
    save_figure,
    write_plot_summary,
)
from ulvz_mesh_viz.schema import validate_dataset


STEM = "03_vertical_ulvz_section"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot a vertical ULVZ section.")
    add_common_args(parser)
    parser.add_argument("--section-azimuth-deg", type=float)
    parser.add_argument("--section-half-width-km", type=float)
    return parser


def run(args: argparse.Namespace) -> dict:
    metadata, points, comparison, _ = load_dataset(
        args.data_dir, args.metadata, args.points, args.comparison_summary
    )
    validate_dataset(metadata, points, comparison)
    unique = unique_points(points)
    azimuth = (
        float(args.section_azimuth_deg)
        if args.section_azimuth_deg is not None
        else float(metadata.get("default_section_azimuth_deg", 0.0))
    )
    section_points = ensure_section_coordinates(unique, azimuth)
    half_width = (
        float(args.section_half_width_km)
        if args.section_half_width_km is not None
        else float(metadata.get("default_section_half_width_km", auto_section_half_width_km(section_points)))
    )
    window = section_points[section_points["cross_section_offset_km"] <= half_width]
    counts = window["category"].value_counts().to_dict()
    missing = [category for category in ["outside", "taper", "core"] if counts.get(category, 0) == 0]
    if missing:
        raise PlotDataError(
            "section window lacks "
            + ", ".join(missing)
            + "; rerun with explicit --section-half-width-km"
        )
    formats = parse_formats(args.formats)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    category_scatter(ax, window, "section_distance_km", "height_above_cmb_km", s=20)
    ax.axhline(0.0, color="black", lw=0.8)
    ax.set_xlabel("Signed section distance (km)")
    ax.set_ylabel("Height above CMB (km)")
    ax.set_title("Vertical ULVZ validation section")
    ax.grid(True, alpha=0.25)
    add_disclaimer(fig, metadata)
    output_files = save_figure(fig, args.out_dir, STEM, formats)
    return write_plot_summary(
        args.out_dir,
        STEM,
        metadata,
        window,
        output_files,
        {"formats": formats, "section_azimuth_deg": azimuth, "section_half_width_km": half_width},
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (PlotDataError, ValueError) as exc:
        print(f"{STEM}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
