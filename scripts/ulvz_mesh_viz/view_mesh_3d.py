#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulvz_mesh_viz.data import load_metadata, load_points


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optional PyVista 3-D ULVZ mesh point viewer.")
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--points", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--off-screen", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        import pyvista as pv
    except Exception as exc:
        print(f"view_mesh_3d: PyVista/VTK unavailable: {exc}", file=sys.stderr)
        return 1
    metadata = load_metadata(args.metadata)
    points = load_points(args.points)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cloud = pv.PolyData(points[["x_norm", "y_norm", "z_norm"]].to_numpy())
    plotter = pv.Plotter(off_screen=args.off_screen)
    plotter.add_mesh(cloud, render_points_as_spheres=True, point_size=6)
    plotter.add_text(metadata.get("fixture_disclaimer", ""), font_size=8)
    screenshot = out_dir / "ulvz_mesh_points_3d.png"
    plotter.show(screenshot=str(screenshot) if args.off_screen else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
