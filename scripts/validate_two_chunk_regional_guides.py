#!/usr/bin/env python3
"""Static consistency checks for the bilingual canonical two-chunk guides."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_PARAMETERS = {
    "NCHUNKS", "ANGULAR_WIDTH_XI_IN_DEGREES", "ANGULAR_WIDTH_ETA_IN_DEGREES",
    "CENTER_LATITUDE_IN_DEGREES", "CENTER_LONGITUDE_IN_DEGREES",
    "GAMMA_ROTATION_AZIMUTH", "NEX_XI", "NEX_ETA", "NPROC_XI", "NPROC_ETA",
    "MODEL", "OCEANS", "ELLIPTICITY", "TOPOGRAPHY", "GRAVITY", "ROTATION",
    "ATTENUATION", "RECORD_LENGTH_IN_MINUTES", "NTSTEP_BETWEEN_OUTPUT_SEISMOS",
    "NTSTEP_BETWEEN_OUTPUT_SAMPLE", "ABSORBING_CONDITIONS",
    "ABSORB_USING_GLOBAL_SPONGE", "REGIONAL_MESH_CUTOFF",
    "REGIONAL_MESH_CUTOFF_DEPTH", "REGIONAL_MESH_ADD_2ND_DOUBLING",
    "LOCAL_PATH", "LOCAL_TMP_PATH", "SAVE_MESH_FILES",
}


def read(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def markers(text: str) -> list[str]:
    return re.findall(r"<!-- guide-section:(\d+) -->", text)


def local_markdown_targets(text: str) -> list[str]:
    return [target for target in re.findall(r"!?(?:\[[^\]]+\])\(([^)]+)\)", text)
            if not target.startswith(("http://", "https://", "#"))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.project_root.resolve()
    en_path = root / "docs/two_chunk_regional_simulations_guide_en.md"
    zh_path = root / "docs/two_chunk_regional_simulations_guide_zh.md"
    index_path = root / "docs/two_chunk_regional_simulations_guide.md"
    manifest_path = root / "patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints_manifest.json"
    parameter_source = root / "specfem3d_globe/src/shared/read_compute_parameters.f90"
    absorb_source = root / "specfem3d_globe/src/meshfem3D/get_absorb.f90"
    errors: list[str] = []
    try:
        en, zh, index = read(en_path), read(zh_path), read(index_path)
        manifest = json.loads(read(manifest_path))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"guide validation: {exc}", file=sys.stderr)
        return 2

    expected_sections = [str(number) for number in range(1, 13)]
    if markers(en) != expected_sections or markers(zh) != expected_sections:
        errors.append("English and Chinese guides must each contain ordered section markers 1..12")
    en_commands = re.findall(r"~~~bash\n(.*?)~~~", en, flags=re.DOTALL)
    zh_commands = re.findall(r"~~~bash\n(.*?)~~~", zh, flags=re.DOTALL)
    if en_commands != zh_commands:
        errors.append("English and Chinese command blocks differ")
    for parameter in REQUIRED_PARAMETERS:
        if parameter not in en or parameter not in zh:
            errors.append(f"parameter missing from one guide: {parameter}")
    for field in ("patch_sha256",):
        if manifest[field] not in en or manifest[field] not in zh:
            errors.append(f"manifest {field} missing or mismatched in a guide")
    for field in ("baseline_target_sha256", "formal_candidate_sha256"):
        value = manifest["source_provenance"][field]
        if value not in en or value not in zh:
            errors.append(f"manifest source_provenance.{field} missing or mismatched in a guide")
    for token in ("canonical_90deg_fixture_ready=true", "general_two_chunk_mode_classification=B"):
        if token not in en or token not in zh or token not in index:
            errors.append(f"scope token missing: {token}")
    implementation_pairs = (
        ("counter-clockwise", "逆时针"),
        ("ABSORBING_CONDITIONS=.true.", "ABSORBING_CONDITIONS=.true."),
        ("ABSORB_USING_GLOBAL_SPONGE=.false.", "ABSORB_USING_GLOBAL_SPONGE=.false."),
        ("never sponge, Stacey", "永远不是 sponge、Stacey"),
        ("two_chunk_canonical_geometry.svg", "two_chunk_canonical_geometry.svg"),
        ("two_chunk_user_workflow.svg", "two_chunk_user_workflow.svg"),
        ("There is no AC latitude, longitude, or gamma parameter", "AC 没有独立的 latitude、longitude 或 gamma 参数"),
        ("fixed-geometry planner check", "固定几何的 planner 检查"),
        ("fixed teaching `DATA/` only", "仅 fixed teaching `DATA/`"),
    )
    for english, chinese in implementation_pairs:
        if english not in en or chinese not in zh:
            errors.append(f"missing bilingual implementation statement: {english}")
    for asset in (
        root / "docs/assets/two_chunk_canonical_geometry.svg",
        root / "docs/assets/two_chunk_user_workflow.svg",
        root / "docs/two_chunk_absorbing_boundary_audit.md",
    ):
        if not asset.is_file():
            errors.append(f"missing required guide asset: {asset.relative_to(root)}")
    try:
        parameter_text = read(parameter_source)
        absorb_text = read(absorb_source)
    except ValueError as exc:
        errors.append(f"cannot audit current absorbing-boundary source: {exc}")
    else:
        source_requirements = (
            (parameter_text, "ABSORB_USING_GLOBAL_SPONGE .and. NCHUNKS /= 6"),
            (parameter_text, "Please set NCHUNKS to 6 in Par_file to use ABSORB_USING_GLOBAL_SPONGE"),
            (absorb_text, "ichunk == CHUNK_AC"),
            (absorb_text, "ichunk == CHUNK_AB"),
        )
        for source_text, token in source_requirements:
            if token not in source_text:
                errors.append(f"current-source absorbing-boundary invariant missing: {token}")
    safety_pairs = (
        ("Stop on a hash or context mismatch", "hash 或 context 不匹配时必须停止"),
        ("Do not prescribe a fixed angular safety distance", "不能规定固定 angular safety distance"),
        ("not a universal window", "不是 universal window"),
    )
    for english, chinese in safety_pairs:
        if english not in en or chinese not in zh:
            errors.append(f"missing bilingual safety warning: {english}")
    for path, text in ((en_path, en), (zh_path, zh), (index_path, index)):
        for target in local_markdown_targets(text):
            if not (path.parent / target).resolve().is_file():
                errors.append(f"broken local markdown link in {path.relative_to(root)}: {target}")
    report = {
        "schema": "ulvz_two_chunk_bilingual_guide_check.v1",
        "english_sections": markers(en), "chinese_sections": markers(zh),
        "required_parameter_count": len(REQUIRED_PARAMETERS),
        "errors": errors, "status": "pass" if not errors else "fail",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
