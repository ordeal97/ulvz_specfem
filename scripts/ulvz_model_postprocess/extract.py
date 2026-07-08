from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from scripts.ulvz_model_postprocess.input_contracts import parse_labeled_path, validate_databases_mpi
from scripts.ulvz_model_postprocess.schema import read_json, write_json
from scripts.ulvz_model_postprocess.errors import ModelPostprocessError


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", required=True)
    parser.add_argument("--extract-mode", choices=["summary", "selected", "full"], default="summary")
    parser.add_argument("--allow-large", action="store_true")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--memory-limit-mb", type=int, default=2048)
    parser.add_argument("--max-points", type=int, default=10_000_000)
    parser.add_argument("--max-points-per-rank", type=int, default=2_000_000)
    parser.add_argument("--max-cells", type=int, default=1_000_000)
    parser.add_argument("--region", default="none")
    parser.add_argument("--cmb-window-km")
    parser.add_argument("--depth-km")
    parser.add_argument("--sample", default="none")
    parser.add_argument("--sample-stride", type=int)
    parser.add_argument("--extractor")


def run(args: argparse.Namespace) -> dict:
    label, path = parse_labeled_path(args.model)
    inventory = validate_databases_mpi(path)
    if args.extract_mode == "full" and not args.allow_large:
        raise ModelPostprocessError("--extract-mode full requires explicit --allow-large")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "PASS",
        "model_label": label,
        "input_contract": "complete-DATABASES_MPI-directory",
        "input_path": str(path),
        "extract_mode": args.extract_mode,
        "rank_inventory": inventory,
        "limits": {
            "memory_limit_mb": args.memory_limit_mb,
            "max_points": args.max_points,
            "max_points_per_rank": args.max_points_per_rank,
            "max_cells": args.max_cells,
        },
    }
    write_json(out_dir / "input_validation.json", summary)
    if args.extract_mode == "summary":
        write_json(out_dir / "model_manifest.json", _summary_manifest(label, path, inventory, args))
        return summary
    extractor = Path(args.extractor) if args.extractor else _default_extractor()
    if not extractor.exists():
        raise ModelPostprocessError(
            f"physical-field extraction requires xulvz_model_extract; missing extractor: {extractor}"
        )
    command = [
        str(extractor),
        "--extract-reg1",
        str(path),
        str(out_dir),
        label,
        args.extract_mode,
        str(args.memory_limit_mb),
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        details = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise ModelPostprocessError(f"physical-field extraction failed through xulvz_model_extract: {details}")
    manifest_path = out_dir / "model_manifest.json"
    if not manifest_path.exists():
        raise ModelPostprocessError("xulvz_model_extract completed but did not write model_manifest.json")
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != "ulvz_model_postprocess.v1":
        raise ModelPostprocessError("xulvz_model_extract wrote an unsupported model manifest schema")
    return manifest


def _summary_manifest(label: str, path: Path, inventory: list[dict], args: argparse.Namespace) -> dict:
    return {
        "schema_version": "ulvz_model_postprocess.v1",
        "model_label": label,
        "extraction_mode": "summary",
        "input_path": str(path),
        "rank_inventory": inventory,
        "roi": {"kind": args.region},
        "sampling_rule": {"kind": args.sample},
        "selection_fingerprint": "summary-only",
        "summary_only": True,
    }


def _default_extractor() -> Path:
    return Path(__file__).resolve().parents[2] / "specfem3d_globe" / "bin" / "xulvz_model_extract"
