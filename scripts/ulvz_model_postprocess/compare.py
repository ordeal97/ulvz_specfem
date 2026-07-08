from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from scripts.ulvz_model_postprocess.errors import ModelPostprocessError
from scripts.ulvz_model_postprocess.input_contracts import parse_labeled_path
from scripts.ulvz_model_postprocess.schema import ensure_schema, read_json, stable_fingerprint, write_json


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--reference", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--comparison-name", required=True)
    parser.add_argument("--out-dir", required=True)


def run(args: argparse.Namespace) -> dict:
    ref_label, ref_path = parse_labeled_path(args.reference)
    target_label, target_path = parse_labeled_path(args.target)
    ref = read_json(ref_path)
    target = read_json(target_path)
    ensure_schema(ref)
    ensure_schema(target)
    _check_compatible(ref, target)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    common_fields = sorted(set(ref["field_units"]) & set(target["field_units"]))
    rank_outputs = []
    for ref_rank, target_rank in zip(ref["rank_store"]["ranks"], target["rank_store"]["ranks"]):
        rank_outputs.append(
            _write_rank_comparison(
                ref_path.parent,
                target_path.parent,
                out_dir,
                ref_rank,
                target_rank,
                common_fields,
            )
        )
    manifest = {
        "schema_version": "ulvz_model_postprocess.v1",
        "comparison_name": args.comparison_name,
        "reference": {"label": ref_label, "manifest": str(ref_path)},
        "target": {"label": target_label, "manifest": str(target_path)},
        "orientation": {"ratio": "target / reference", "difference": "target - reference"},
        "field_units": {f"{name}_ratio": "dimensionless" for name in common_fields}
        | {f"{name}_difference": ref["field_units"][name] for name in common_fields},
        "rank_store": {"layout": "rank-local-directory-npy-v1", "ranks": rank_outputs},
        "compatibility_fingerprint": stable_fingerprint(
            {
                "reference": ref["compatibility_fingerprint"],
                "target": target["compatibility_fingerprint"],
                "fields": common_fields,
            }
        ),
    }
    manifest_path = out_dir / f"{args.comparison_name}_manifest.json"
    write_json(manifest_path, manifest)
    return manifest


def _check_compatible(ref: dict, target: dict) -> None:
    checks = [
        ("extraction_mode", "extraction mode"),
        ("selection_fingerprint", "selection fingerprint"),
        ("field_units", "field units"),
        ("coordinate_units", "coordinate units"),
        ("model_field_scaling_convention", "model field scaling convention"),
    ]
    for key, label in checks:
        if ref.get(key) != target.get(key):
            raise ModelPostprocessError(f"comparison requires matching {label}")
    ref_contents = ref.get("compatibility_fingerprint_contents", {})
    target_contents = target.get("compatibility_fingerprint_contents", {})
    for key, label in [
        ("roi", "ROI definition"),
        ("sampling_rule", "sampling rule"),
        ("rank_inventory", "rank inventory"),
        ("topology_fingerprint", "topology fingerprint"),
        ("geometry_fingerprint", "geometry fingerprint"),
    ]:
        if ref_contents.get(key) != target_contents.get(key):
            raise ModelPostprocessError(f"comparison requires matching {label}")


def _write_rank_comparison(
    ref_root: Path,
    target_root: Path,
    out_root: Path,
    ref_rank: dict,
    target_rank: dict,
    fields: list[str],
) -> dict:
    rank_path = ref_rank["path"]
    out_rank = out_root / "ranks" / rank_path.split("/")[-1]
    fields_dir = out_rank / "fields"
    fields_dir.mkdir(parents=True, exist_ok=True)
    for name in fields:
        ref_values = np.load(ref_root / rank_path / "fields" / f"{name}.npy", mmap_mode="r")
        target_values = np.load(target_root / target_rank["path"] / "fields" / f"{name}.npy", mmap_mode="r")
        if ref_values.shape != target_values.shape:
            raise ModelPostprocessError(f"field shape mismatch for {name}")
        np.save(fields_dir / f"{name}_ratio.npy", target_values / ref_values)
        np.save(fields_dir / f"{name}_difference.npy", target_values - ref_values)
    metadata = {
        "schema_version": "ulvz_model_postprocess.v1",
        "rank": ref_rank["rank"],
        "region": ref_rank["region"],
        "fields": [f"{name}_ratio" for name in fields] + [f"{name}_difference" for name in fields],
    }
    write_json(out_rank / "metadata.json", metadata)
    return {"rank": ref_rank["rank"], "region": ref_rank["region"], "path": f"ranks/{out_rank.name}"}
