#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulvz_mesh_viz.data import PlotDataError, write_json
from ulvz_mesh_viz import SCHEMA_VERSION
from ulvz_mesh_viz import validate_plot_data
from ulvz_mesh_viz import plot_cmb_sampling
from ulvz_mesh_viz import plot_fixture_overview
from ulvz_mesh_viz import plot_material_response
from ulvz_mesh_viz import plot_mesh_resolution
from ulvz_mesh_viz import plot_vertical_section
from ulvz_mesh_viz.plotting import add_common_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run all required Task 3E static figures.")
    add_common_args(parser)
    parser.add_argument("--section-azimuth-deg", type=float)
    parser.add_argument("--section-half-width-km", type=float)
    return parser


def run(args: argparse.Namespace) -> dict:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not hasattr(args, "near_cmb_window_km"):
        args.near_cmb_window_km = 120.0
    if not hasattr(args, "fields"):
        args.fields = None
    validation = validate_plot_data.run(args)
    plot_args = argparse.Namespace(**vars(args))
    overview = plot_fixture_overview.run(plot_args)
    cmb = plot_cmb_sampling.run(plot_args)
    section = plot_vertical_section.run(plot_args)
    material = plot_material_response.run(plot_args)
    resolution = plot_mesh_resolution.run(plot_args)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "validation": validation,
        "figures": [overview, cmb, section, material, resolution],
    }
    write_json(out_dir / "all_figures_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (PlotDataError, ValueError) as exc:
        print(f"make_all_figures: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        raise SystemExit(exit_code)
