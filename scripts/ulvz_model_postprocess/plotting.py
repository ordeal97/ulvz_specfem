from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from scripts.ulvz_model_postprocess.errors import ModelPostprocessError
from scripts.ulvz_model_postprocess.schema import read_json


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True)
    parser.add_argument("--field", required=True)
    parser.add_argument("--kind", choices=["histogram", "radial-summary"], default="histogram")
    parser.add_argument("--out-dir", required=True)


def run(args: argparse.Namespace) -> dict:
    import matplotlib.pyplot as plt

    manifest_path = Path(args.input)
    manifest = read_json(manifest_path)
    values = _load_field_values(manifest_path.parent, manifest, args.field)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
    ax.hist(values, bins=20)
    ax.set_xlabel(f"{args.field} ({manifest.get('field_units', {}).get(args.field, 'unknown')})")
    ax.set_ylabel("count")
    ax.set_title(f"{args.kind}: {args.field}")
    output = out_dir / f"{args.kind}_{args.field}.png"
    fig.savefig(output, dpi=120)
    plt.close(fig)
    return {"output": str(output), "field": args.field, "kind": args.kind}


def _load_field_values(root: Path, manifest: dict, field: str) -> np.ndarray:
    if field not in manifest.get("field_units", {}):
        raise ModelPostprocessError(f"field {field!r} is not available")
    chunks = []
    for rank in manifest["rank_store"]["ranks"]:
        path = root / rank["path"] / "fields" / f"{field}.npy"
        chunks.append(np.asarray(np.load(path, mmap_mode="r")).ravel())
    return np.concatenate(chunks)
