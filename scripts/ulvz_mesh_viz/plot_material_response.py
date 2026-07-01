#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np

from ulvz_mesh_viz.data import PlotDataError, load_dataset, present_fields
from ulvz_mesh_viz.plotting import add_common_args, add_disclaimer, parse_formats, save_figure, write_plot_summary
from ulvz_mesh_viz.schema import validate_dataset


STEM = "04_material_ratio_validation"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot material ratio validation.")
    add_common_args(parser)
    parser.add_argument("--fields", help="Comma-separated material fields to plot")
    return parser


def run(args: argparse.Namespace) -> dict:
    metadata, points, comparison, _ = load_dataset(
        args.data_dir, args.metadata, args.points, args.comparison_summary
    )
    validate_dataset(metadata, points, comparison)
    fields = present_fields(metadata)
    if args.fields:
        requested = [item.strip() for item in args.fields.split(",") if item.strip()]
        missing = [field for field in requested if field not in fields]
        if missing:
            raise PlotDataError(f"requested fields not present: {', '.join(missing)}")
        fields = requested
    if not fields:
        raise PlotDataError("no present material fields")
    formats = parse_formats(args.formats)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8))
    ax_ratio, ax_resid = axes
    x = points["w_expected"].astype(float).to_numpy()
    for field in fields:
        ax_ratio.scatter(x, points[f"{field}_ratio"], s=8, alpha=0.55, label=field)
        ax_resid.scatter(x, points[f"{field}_residual"], s=8, alpha=0.55, label=field)
    ax_ratio.set_xlabel("w_expected")
    ax_ratio.set_ylabel("Observed ratio")
    ax_ratio.set_title("Material ratios")
    ax_resid.set_xlabel("w_expected")
    ax_resid.set_ylabel("Absolute residual")
    ax_resid.set_title("Ratio residuals")
    ax_resid.set_yscale("symlog", linthresh=1.0e-10)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)
    if np.nanmax(points[[f"{field}_residual" for field in fields]].to_numpy()) == 0:
        ax_resid.set_ylim(-1.0e-9, 1.0e-8)
    add_disclaimer(fig, metadata)
    output_files = save_figure(fig, args.out_dir, STEM, formats)
    return write_plot_summary(
        args.out_dir,
        STEM,
        metadata,
        points,
        output_files,
        {"formats": formats, "fields": fields},
        material_fields=fields,
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
