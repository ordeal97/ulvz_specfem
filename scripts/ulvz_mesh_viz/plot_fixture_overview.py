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


STEM = "01_fixture_domain_ulvz_footprint"


def build_parser() -> argparse.ArgumentParser:
    return add_common_args(argparse.ArgumentParser(description="Plot fixture domain and ULVZ footprint."))


def run(args: argparse.Namespace) -> dict:
    metadata, points, comparison, _ = load_dataset(
        args.data_dir, args.metadata, args.points, args.comparison_summary
    )
    validate_dataset(metadata, points, comparison)
    unique = unique_points(points)
    if unique.empty:
        raise PlotDataError("no valid unique coordinates")
    formats = parse_formats(args.formats)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    category_scatter(ax, unique, "longitude_deg", "latitude_deg", s=14)
    ulvz = metadata.get("ulvz", {})
    ax.scatter(
        [ulvz.get("center_longitude_deg", 140.0)],
        [ulvz.get("center_latitude_deg", 45.0)],
        marker="*",
        s=120,
        color="black",
        label="ULVZ center",
    )
    ax.set_xlabel("Longitude (deg)")
    ax.set_ylabel("Latitude (deg)")
    ax.set_title("Task 3D fixture domain and ULVZ footprint")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", frameon=False)
    add_disclaimer(fig, metadata)
    output_files = save_figure(fig, args.out_dir, STEM, formats)
    return write_plot_summary(args.out_dir, STEM, metadata, unique, output_files, {"formats": formats})


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
