from __future__ import annotations

import argparse
import sys

from ulvz_model_postprocess.errors import ModelPostprocessError
from ulvz_model_postprocess import compare, extract, paraview, plotting


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ulvz_model_postprocess")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate a DATABASES_MPI input")
    extract.add_arguments(validate_parser)
    validate_parser.set_defaults(func=extract.run, extract_mode="summary")

    extract_parser = subparsers.add_parser("extract", help="extract a model product")
    extract.add_arguments(extract_parser)
    extract_parser.set_defaults(func=extract.run)

    compare_parser = subparsers.add_parser("compare", help="compare two extracted products")
    compare.add_arguments(compare_parser)
    compare_parser.set_defaults(func=compare.run)

    plot_parser = subparsers.add_parser("plot", help="make static plots without VTK")
    plotting.add_arguments(plot_parser)
    plot_parser.set_defaults(func=plotting.run)

    paraview_parser = subparsers.add_parser("paraview", help="export ParaView metadata/products")
    paraview.add_arguments(paraview_parser)
    paraview_parser.set_defaults(func=paraview.run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ModelPostprocessError, ValueError, KeyError) as exc:
        print(f"ulvz_model_postprocess: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
