"""Command-line interface for standalone STF convolution."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from .asdf import read_asdf_waveforms, write_asdf_waveforms
from .convolution import convolve_waveform
from .errors import StfConvolutionError
from .io import _resolve_format, read_waveform, write_waveform
from .stf import builtin_stf, fortran_compatible_stf, read_numeric_stf, resample_stf


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ulvz-convolve-stf", description="Convolve a SPECFEM base waveform with a moment-rate STF.")
    parser.add_argument("--input", nargs="+", required=True, help="one or more waveform paths or quoted glob patterns")
    parser.add_argument("--output", required=True, help="output file for one input, or output directory for multiple inputs")
    parser.add_argument("--input-format", choices=("auto", "ascii", "sac", "asdf"), default="auto")
    parser.add_argument("--output-format", choices=("auto", "ascii", "sac", "asdf"), default="auto")
    parser.add_argument("--stf-kind", choices=("gaussian", "triangle", "numeric"), required=True)
    parser.add_argument("--half-duration", type=float)
    parser.add_argument("--stf-file")
    parser.add_argument("--stf-time-shift", type=float, default=0.0, help="seconds; positive values delay the STF")
    parser.add_argument("--mode", choices=("same", "full", "fortran"), default="same")
    parser.add_argument("--compat", choices=("fortran",), help="alias for --mode fortran")
    parser.add_argument("--method", choices=("auto", "direct", "fft"), default="auto")
    parser.add_argument("--no-normalize", action="store_true", help="do not area-normalize a numeric STF")
    parser.add_argument("--allow-coarse-stf", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", help="write JSON run metadata (not permitted with --dry-run)")
    return parser


def _inputs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matched = [Path(item) for item in glob.glob(pattern)]
        if not matched:
            candidate = Path(pattern)
            if candidate.exists():
                matched = [candidate]
        paths.extend(matched)
    unique = list(dict.fromkeys(path.resolve() for path in paths))
    if not unique:
        raise StfConvolutionError("no input waveform matched --input")
    return unique


def _output_path(input_path: Path, output: Path, multiple: bool, output_format: str, input_format: str) -> Path:
    if not multiple:
        return output
    selected = input_format if output_format == "auto" else output_format
    suffix = {"sac": ".sac", "asdf": ".h5"}.get(selected, input_path.suffix)
    return output / f"{input_path.stem}.convolved{suffix}"


def _report_item(input_path: Path, output_path: Path, result) -> dict:
    return {
        "input": str(input_path),
        "output": str(output_path),
        "dt": result.waveform.dt,
        "input_npts": None,
        "output_npts": len(result.waveform.amplitudes),
        "stf_kind": result.stf.kind,
        "stf_time_range_seconds": [float(result.stf.times[0]), float(result.stf.times[-1])],
        "stf_original_integral": result.stf.original_integral,
        "stf_normalized_integral": result.stf.normalized_integral,
        "mode": result.mode,
        "method": result.method,
        "stf_metadata": result.stf.metadata,
        "warnings": list(result.warnings),
    }


def _convolve_one(waveform, args):
    if args.stf_kind == "numeric":
        raw_stf = read_numeric_stf(args.stf_file, normalize=not args.no_normalize)
        stf = resample_stf(raw_stf, waveform.dt, time_shift=args.stf_time_shift,
                           allow_coarse_stf=args.allow_coarse_stf, normalize=not args.no_normalize)
    elif args.mode == "fortran":
        if args.stf_time_shift != 0.0:
            raise StfConvolutionError("Fortran mode does not support STF time shifts")
        stf = fortran_compatible_stf(args.stf_kind, args.half_duration, waveform.dt)
    else:
        raw_stf = builtin_stf(args.stf_kind, args.half_duration, waveform.dt, modern=True)
        stf = resample_stf(raw_stf, waveform.dt, time_shift=args.stf_time_shift,
                           allow_coarse_stf=args.allow_coarse_stf, normalize=False)
    return convolve_waveform(waveform, stf, mode=args.mode, method=args.method)


def _convolve_asdf(path: Path, destination: Path, args) -> dict:
    traces = read_asdf_waveforms(path)
    results = [_convolve_one(trace, args) for trace in traces]
    report = {
        "input": str(path),
        "output": str(destination),
        "format": "asdf",
        "trace_count": len(results),
        "input_npts": sum(len(trace.amplitudes) for trace in traces),
        "output_npts": sum(len(result.waveform.amplitudes) for result in results),
        "traces": [
            {
                "dataset": result.waveform.asdf_dataset_path,
                "dt": result.waveform.dt,
                "input_npts": len(trace.amplitudes),
                "output_npts": len(result.waveform.amplitudes),
                "method": result.method,
            }
            for trace, result in zip(traces, results, strict=True)
        ],
    }
    if not args.dry_run:
        write_asdf_waveforms(path, destination, [result.waveform for result in results], overwrite=args.overwrite)
    return report


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.compat:
            if args.mode != "same":
                raise StfConvolutionError("--compat fortran cannot be combined with an explicit non-default --mode")
            args.mode = "fortran"
        if args.report and args.dry_run:
            raise StfConvolutionError("--report is not permitted with --dry-run")
        if args.stf_kind == "numeric":
            if not args.stf_file or args.half_duration is not None:
                raise StfConvolutionError("numeric STF requires --stf-file and does not accept --half-duration")
            if args.mode == "fortran":
                raise StfConvolutionError("Fortran mode does not support numeric STF")
        elif args.half_duration is None or args.stf_file:
            raise StfConvolutionError("builtin STF requires --half-duration and does not accept --stf-file")
        paths = _inputs(args.input)
        output = Path(args.output)
        if len(paths) > 1 and output.suffix:
            raise StfConvolutionError("multiple inputs require --output to be a directory path")
        input_formats = {_resolve_format(path, args.input_format) for path in paths}
        if len(input_formats) != 1:
            raise StfConvolutionError("a single invocation cannot mix ASDF, ASCII, and SAC inputs")
        input_format = input_formats.pop()
        if input_format == "asdf" and args.output_format not in {"auto", "asdf"}:
            raise StfConvolutionError("ASDF input requires --output-format asdf (or auto)")
        if input_format != "asdf" and args.output_format == "asdf":
            raise StfConvolutionError("ASDF output requires ASDF input")

        reports = []
        for path in paths:
            destination = _output_path(path, output, len(paths) > 1, args.output_format, input_format)
            if input_format == "asdf":
                report = _convolve_asdf(path, destination, args)
                reports.append(report)
                print(json.dumps(report, ensure_ascii=False, sort_keys=True), file=sys.stderr)
                continue
            waveform = read_waveform(path, format=args.input_format)
            result = _convolve_one(waveform, args)
            report = _report_item(path, destination, result)
            report["input_npts"] = len(waveform.amplitudes)
            reports.append(report)
            if not args.dry_run:
                write_waveform(result.waveform, destination, format=args.output_format, overwrite=args.overwrite)
            print(json.dumps(report, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        if args.report:
            report_path = Path(args.report)
            if report_path.exists() and not args.overwrite:
                raise StfConvolutionError(f"refusing to overwrite existing report: {report_path}")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"runs": reports}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except StfConvolutionError as exc:
        print(f"ulvz-convolve-stf: error: {exc}", file=sys.stderr)
        return 2
    return 0
