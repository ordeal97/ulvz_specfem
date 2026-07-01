#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt

from ulvz_mesh_viz.data import PlotDataError, load_dataset, unique_points
from ulvz_mesh_viz.geometry import nearest_neighbor_spacing
from ulvz_mesh_viz.plotting import add_common_args, add_disclaimer, parse_formats, save_figure, write_plot_summary
from ulvz_mesh_viz.schema import validate_dataset


STEM = "05_mesh_sampling_resolution"


def build_parser() -> argparse.ArgumentParser:
    return add_common_args(argparse.ArgumentParser(description="Plot mesh sampling resolution."))


def run(args: argparse.Namespace) -> dict:
    metadata, points, comparison, _ = load_dataset(
        args.data_dir, args.metadata, args.points, args.comparison_summary
    )
    validate_dataset(metadata, points, comparison)
    unique = unique_points(points)
    spacing = nearest_neighbor_spacing(unique)
    formats = parse_formats(args.formats)
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    for category in ["outside", "taper", "core"]:
        subset = spacing[spacing["category"] == category]
        if len(subset):
            ax.hist(
                subset["nearest_neighbor_spacing_km"],
                bins=min(20, max(3, len(subset))),
                alpha=0.45,
                label=category,
            )
    ax.set_xlabel("Nearest-neighbor spacing (km)")
    ax.set_ylabel("Count")
    ax.set_title("Task 3D fixture sampling spacing")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False)
    add_disclaimer(fig, metadata)
    output_files = save_figure(fig, args.out_dir, STEM, formats)
    csv_path = Path(args.out_dir) / "05_mesh_sampling_resolution_spacing.csv"
    spacing.to_csv(csv_path, index=False)
    output_files.append(str(csv_path))
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
