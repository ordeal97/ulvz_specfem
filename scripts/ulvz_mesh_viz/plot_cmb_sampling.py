#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt

from ulvz_mesh_viz.data import PlotDataError, load_dataset, unique_points
from ulvz_mesh_viz.plotting import (
    add_common_args,
    add_disclaimer,
    category_scatter,
    parse_formats,
    save_figure,
    write_plot_summary,
)
from ulvz_mesh_viz.schema import validate_dataset


STEM = "02_cmb_ulvz_sampling"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot near-CMB ULVZ sampling categories.")
    add_common_args(parser)
    parser.add_argument("--near-cmb-window-km", type=float, default=120.0)
    return parser


def run(args: argparse.Namespace) -> dict:
    metadata, points, comparison, _ = load_dataset(
        args.data_dir, args.metadata, args.points, args.comparison_summary
    )
    validate_dataset(metadata, points, comparison)
    unique = unique_points(points)
    near = unique[
        (unique["height_above_cmb_km"] >= -1.0)
        & (unique["height_above_cmb_km"] <= float(args.near_cmb_window_km))
    ]
    if near.empty:
        raise PlotDataError("no near-CMB unique points")
    formats = parse_formats(args.formats)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    category_scatter(ax, near, "section_distance_km", "cross_section_offset_km", s=18)
    ax.set_xlabel("Local section distance (km)")
    ax.set_ylabel("Cross-section offset (km)")
    ax.set_title("Near-CMB ULVZ sampling categories")
    ax.grid(True, alpha=0.25)
    add_disclaimer(fig, metadata)
    output_files = save_figure(fig, args.out_dir, STEM, formats)
    return write_plot_summary(
        args.out_dir,
        STEM,
        metadata,
        near,
        output_files,
        {"formats": formats, "near_cmb_window_km": args.near_cmb_window_km},
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
