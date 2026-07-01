#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ulvz_mesh_viz.data import PlotDataError, load_dataset, write_json
from ulvz_mesh_viz.plotting import add_common_args
from ulvz_mesh_viz.schema import validate_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Task 3E ULVZ mesh plot data.")
    add_common_args(parser)
    parser.add_argument("--section-cells")
    return parser


def run(args: argparse.Namespace) -> dict:
    metadata, points, comparison, paths = load_dataset(
        args.data_dir, args.metadata, args.points, args.comparison_summary
    )
    summary = validate_dataset(metadata, points, comparison)
    summary.update(
        {
            "inputs": {name: str(path) for name, path in paths.items()},
            "fixture_disclaimer": metadata.get("fixture_disclaimer", ""),
        }
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "plot_data_validation_summary.json", summary)
    with (out_dir / "plot_data_validation_summary.txt").open("w", encoding="utf-8") as handle:
        handle.write("status: PASS\n")
        handle.write(f"schema_version: {metadata.get('schema_version')}\n")
        handle.write(f"category_counts: {summary['category_counts']}\n")
        handle.write(f"material_fields: {', '.join(summary['material_fields'])}\n")
        handle.write(metadata.get("fixture_disclaimer", "") + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except PlotDataError as exc:
        print(f"validate_plot_data: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
