"""Command line interface for safe arrival annotation."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from obspy import UTCDateTime, read

from .core import DEFAULT_PHASES, annotate_run
from .storage import output_paths, read_sidecar, write_outputs


def _phases(value: str) -> tuple[str, ...]:
    result = tuple(item.strip() for item in value.split(",") if item.strip())
    if not result:
        raise argparse.ArgumentTypeError("--phases must not be empty")
    return result


def _primary_by_station(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {(row["network"], row["station"], row["requested_phase"]): row for row in rows
            if row["status"] == "ok" and row["is_primary"] == "true"}


def write_sac_picks(output_dir: Path, rows: list[dict[str, str]], traces) -> Path:
    slots = {"P": 0, "Pdiff": 1, "S": 2, "Sdiff": 3, "PP": 4, "SKS": 5, "SS": 6}
    destination = output_dir / "sac_picks"
    destination.mkdir(parents=True, exist_ok=True)
    primary = _primary_by_station(rows)
    for metadata in traces:
        stream = read(str(metadata.path))
        if len(stream) != 1:
            raise ValueError(f"{metadata.path}: expected one SAC trace")
        trace = stream[0]
        sac = dict(getattr(trace.stats, "sac", {}))
        reference = metadata.sac_reference_time
        if reference is None:
            raise ValueError(f"{metadata.path}: SAC reference time unavailable")
        for phase, slot in slots.items():
            row = primary.get((metadata.network, metadata.station, phase))
            key = f"t{slot}"
            label = f"kt{slot}"
            if row is None:
                sac[key] = None
                sac[label] = ""
            else:
                sac[key] = float(UTCDateTime(row["effective_arrival_time_utc"]) - reference)
                sac[label] = phase
        trace.stats.sac = sac
        trace.write(str(destination / metadata.path.name), format="SAC")
    return destination


def annotate_one(args: argparse.Namespace, run_dir: Path, output_dir: Path | None = None) -> tuple[bool, str]:
    target = output_dir or run_dir / "OUTPUT_FILES"
    sidecar, csv_path = output_paths(target)
    existing = (sidecar.exists(), csv_path.exists())
    if args.resume and any(existing):
        if not all(existing):
            raise RuntimeError("--resume found incomplete annotation outputs; use --overwrite to repair")
        read_sidecar(sidecar)
        return True, f"SKIP {run_dir}: existing annotation outputs are readable"
    selected, rows, traces = annotate_run(run_dir, input_format=args.format, model_name=args.model,
                                          phases=args.phases, stf_time_shift_s=args.stf_time_shift_s)
    if args.dry_run:
        return True, f"DRY-RUN {run_dir}: format={selected} rows={len(rows)} sidecar={sidecar} csv={csv_path}"
    provenance = {"run_dir": str(run_dir.resolve()), "input_format": selected, "model": args.model,
                  "phases": list(args.phases), "stf_time_shift_s": args.stf_time_shift_s}
    sidecar, csv_path = write_outputs(target, rows, provenance, overwrite=args.overwrite)
    if args.write_sac_picks:
        if selected != "sac":
            raise ValueError("--write-sac-picks requires --format sac")
        picks = write_sac_picks(target, rows, traces)
        return True, f"PASS {run_dir}: rows={len(rows)} sidecar={sidecar} csv={csv_path} sac_picks={picks}"
    return True, f"PASS {run_dir}: rows={len(rows)} sidecar={sidecar} csv={csv_path}"


def _manifest_runs(manifest: Path, root: Path) -> list[Path]:
    with manifest.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    if not records or "run_relative_path" not in records[0]:
        raise ValueError(f"{manifest}: requires run_relative_path column")
    return [(root / row["run_relative_path"]).resolve() for row in records]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Annotate SPECFEM ASDF or SAC synthetics with PREM/TauP arrivals.")
    parser.add_argument("run_dir", type=Path, nargs="?")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--format", choices=("auto", "asdf", "sac"), default="auto")
    parser.add_argument("--model", default="prem", choices=("prem",))
    parser.add_argument("--phases", type=_phases, default=DEFAULT_PHASES)
    parser.add_argument("--stf-time-shift-s", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true", help="skip complete, readable annotation outputs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, help="single-run output directory; defaults to <run>/OUTPUT_FILES")
    parser.add_argument("--write-sac-picks", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if bool(args.run_dir) == bool(args.manifest):
        raise SystemExit("provide exactly one of <run_dir> or --manifest")
    if args.manifest and args.root is None:
        raise SystemExit("--manifest requires --root")
    if args.manifest and args.output_dir:
        raise SystemExit("--output-dir is only supported for a single run")
    if args.manifest and args.write_sac_picks:
        raise SystemExit("--write-sac-picks is only supported for a single run")
    if args.overwrite and args.resume:
        raise SystemExit("--overwrite and --resume are mutually exclusive")
    runs = _manifest_runs(args.manifest, args.root) if args.manifest else [args.run_dir]
    failures = 0
    for run in runs:
        try:
            _, message = annotate_one(args, run, args.output_dir)
            print(message)
        except Exception as exc:
            failures += 1
            print(f"FAIL {run}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
