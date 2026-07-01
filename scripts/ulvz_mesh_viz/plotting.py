from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt

from ulvz_mesh_viz.data import category_counts, write_json


CATEGORY_COLORS = {"outside": "#7a7a7a", "taper": "#e59f00", "core": "#0072b2"}


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--points")
    parser.add_argument("--comparison-summary")
    parser.add_argument("--formats", default="png")
    return parser


def parse_formats(value: str) -> list[str]:
    formats = [item.strip().lower() for item in value.split(",") if item.strip()]
    allowed = {"png", "pdf"}
    bad = sorted(set(formats) - allowed)
    if bad:
        raise ValueError(f"unsupported output formats: {', '.join(bad)}")
    return formats or ["png"]


def output_paths(out_dir: str | Path, stem: str, formats: list[str]) -> list[Path]:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    return [base / f"{stem}.{fmt}" for fmt in formats]


def save_figure(fig, out_dir: str | Path, stem: str, formats: list[str]) -> list[str]:
    paths = output_paths(out_dir, stem, formats)
    for path in paths:
        fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return [str(path) for path in paths]


def add_disclaimer(fig, metadata: dict) -> None:
    disclaimer = metadata.get("fixture_disclaimer", "")
    fig.text(0.01, 0.01, disclaimer, fontsize=7, ha="left", va="bottom", color="#444444")


def category_scatter(ax, df, x_col: str, y_col: str, *, s: float = 12.0) -> None:
    for category, color in CATEGORY_COLORS.items():
        subset = df[df["category"] == category]
        if len(subset) == 0:
            continue
        ax.scatter(subset[x_col], subset[y_col], s=s, label=category, alpha=0.78, color=color)
    ax.legend(loc="best", frameon=False)


def write_plot_summary(
    out_dir: str | Path,
    stem: str,
    metadata: dict,
    points,
    output_files: list[str],
    options: dict | None = None,
    material_fields: list[str] | None = None,
) -> dict:
    payload = {
        "schema_version": metadata.get("schema_version"),
        "category_counts": category_counts(points),
        "material_fields": material_fields or [],
        "options": options or {},
        "output_files": output_files,
        "fixture_disclaimer": metadata.get("fixture_disclaimer", ""),
    }
    write_json(Path(out_dir) / f"{stem}_summary.json", payload)
    return payload
