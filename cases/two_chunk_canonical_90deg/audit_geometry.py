#!/usr/bin/env python3
"""Read-only geometry and input audit for the canonical two-chunk teaching case.

The mapping follows euler_angles.f90 and chunk_map() in write_profile.f90.
It is a pre-meshing audit only: it neither reads DATABASES_MPI nor modifies
DATA inputs.  Reports are refused when their output directory already exists.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEG = math.pi / 180.0
HALF_WIDTH = math.pi / 4.0
EPS = 1.0e-9
REQUIRED_CMT = (
    "event name", "time shift", "half duration", "latitude", "longitude",
    "depth", "Mrr", "Mtt", "Mpp", "Mrt", "Mrp", "Mtp",
)
CANONICAL = {
    "NCHUNKS": 2, "ANGULAR_WIDTH_XI_IN_DEGREES": 90.0,
    "ANGULAR_WIDTH_ETA_IN_DEGREES": 90.0, "CENTER_LATITUDE_IN_DEGREES": 90.0,
    "CENTER_LONGITUDE_IN_DEGREES": 90.0, "GAMMA_ROTATION_AZIMUTH": 0.0,
    "NEX_XI": 96, "NEX_ETA": 96, "NPROC_XI": 2, "NPROC_ETA": 2,
    "ELLIPTICITY": False,
}


class AuditError(ValueError):
    """Input or source-context condition that requires the user to stop."""


@dataclass
class PointAudit:
    role: str
    identifier: str
    latitude_degrees: float
    longitude_degrees: float
    elevation_or_depth: float
    chunk: str
    xi_degrees: float | None
    eta_degrees: float | None
    shared_interface_margin_degrees: float | None
    c1_margin_degrees: float
    c2_margin_degrees: float
    external_boundary_margin_degrees: float | None
    on_shared_interface: bool
    on_c1_or_c2: bool
    notes: list[str]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(text: str) -> float:
    return float(text.strip().replace("D", "e").replace("d", "e"))


def bool_value(text: str) -> bool:
    value = text.strip().lower()
    if value in {".true.", "true"}:
        return True
    if value in {".false.", "false"}:
        return False
    raise AuditError(f"invalid logical value: {text}")


def parse_par_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if not key.replace("_", "").isalnum():
            continue
        if key in values:
            raise AuditError(f"duplicate Par_file parameter: {key}")
        values[key] = value
    return values


def template_values(path: Path) -> dict[str, str]:
    return parse_par_file(path)


def parse_cmt(path: Path) -> dict[str, float | str]:
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) != 13:
        raise AuditError(f"CMTSOLUTION must have 13 non-comment lines, found {len(lines)}")
    result: dict[str, float | str] = {"pde": lines[0]}
    for line, expected in zip(lines[1:], REQUIRED_CMT):
        if ":" not in line:
            raise AuditError(f"CMTSOLUTION line lacks ':': {line}")
        key, value = (part.strip() for part in line.split(":", 1))
        if key.lower() != expected.lower():
            raise AuditError(f"CMTSOLUTION expected '{expected}:', found '{key}:'")
        result[expected] = value if expected == "event name" else number(value)
    for key in ("latitude", "longitude", "depth", "time shift", "half duration",
                "Mrr", "Mtt", "Mpp", "Mrt", "Mrp", "Mtp"):
        if not math.isfinite(float(result[key])):
            raise AuditError(f"CMTSOLUTION {key} is not finite")
    if abs(float(result["latitude"])) > 90.0 or abs(float(result["longitude"])) > 360.0:
        raise AuditError("CMTSOLUTION latitude/longitude is outside accepted numeric range")
    if float(result["depth"]) < 0.0:
        raise AuditError("CMTSOLUTION depth must be non-negative")
    return result


def parse_stations(path: Path) -> list[dict[str, Any]]:
    stations: list[dict[str, Any]] = []
    names: set[tuple[str, str]] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 6:
            raise AuditError(f"STATIONS line {line_number} must have 6 fields")
        station, network = fields[:2]
        key = (station, network)
        if key in names:
            raise AuditError(f"duplicate STATIONS network/station pair: {network}.{station}")
        names.add(key)
        lat, lon, elevation, burial = (number(value) for value in fields[2:])
        if not all(math.isfinite(value) for value in (lat, lon, elevation, burial)):
            raise AuditError(f"STATIONS line {line_number} has non-finite numeric data")
        if abs(lat) > 90.0 or abs(lon) > 360.0:
            raise AuditError(f"STATIONS line {line_number} has invalid latitude/longitude")
        stations.append({"station": station, "network": network, "lat": lat, "lon": lon,
                         "elevation": elevation, "burial": burial})
    if not stations:
        raise AuditError("STATIONS has no receiver records")
    return stations


def euler_matrix(center_lat: float, center_lon: float, gamma: float) -> list[list[float]]:
    """Current case has ELLIPTICITY=false, so geographic=geocentric here."""
    alpha = center_lon * DEG
    beta = (90.0 - center_lat) * DEG
    g = gamma * DEG
    sa, ca, sb, cb, sg, cg = (math.sin(alpha), math.cos(alpha), math.sin(beta),
                                math.cos(beta), math.sin(g), math.cos(g))
    return [
        [cg * cb * ca - sg * sa, -sg * cb * ca - cg * sa, sb * ca],
        [cg * cb * sa + sg * ca, -sg * cb * sa + cg * ca, sb * sa],
        [-cg * sb, sg * sb, cb],
    ]


def transpose_apply(matrix: list[list[float]], vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(sum(matrix[row][col] * vector[row] for row in range(3)) for col in range(3))  # type: ignore[return-value]


def unit_latlon(lat: float, lon: float) -> tuple[float, float, float]:
    lat_r, lon_r = lat * DEG, lon * DEG
    return (math.cos(lat_r) * math.cos(lon_r), math.cos(lat_r) * math.sin(lon_r), math.sin(lat_r))


def norm(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(value * value for value in vector))
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def angular_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    return math.degrees(math.acos(dot))


def plane_distance(vector: tuple[float, float, float], normal: tuple[float, float, float]) -> float:
    return math.degrees(math.asin(min(1.0, abs(sum(x * y for x, y in zip(vector, norm(normal)))))))


def map_point(lat: float, lon: float, matrix: list[list[float]]) -> PointAudit:
    local = transpose_apply(matrix, unit_latlon(lat, lon))
    x, y, z = local
    candidates: list[tuple[str, float, float]] = []
    if z > 0.0:
        candidates.append(("chunk_1_central", math.atan2(y, z), math.atan2(-x, z)))
    if y < 0.0:
        # chunk_map() uses Fortran ATAN of the quotient (not a quadrant-aware
        # ATAN2) and separately rejects y>0 for CHUNK_AC.
        candidates.append(("chunk_2_left_attached", math.atan((-z) / y), math.atan(x / y)))
    valid = [(name, xi, eta) for name, xi, eta in candidates
             if abs(xi) <= HALF_WIDTH + EPS and abs(eta) <= HALF_WIDTH + EPS]
    if len(valid) == 2:
        chunk, xi, eta = valid[0]  # shared interface: preserve central chunk as the primary label.
        notes = ["point lies on the AB--AC shared interface"]
    elif len(valid) == 1:
        chunk, xi, eta = valid[0]
        notes = []
    else:
        chunk, xi, eta = "outside_two_chunk_domain", None, None
        notes = ["outside the validated two-chunk physical domain"]

    c1 = norm((1.0, -1.0, 1.0))
    c2 = norm((-1.0, -1.0, 1.0))
    c1_margin = angular_distance(local, c1)
    c2_margin = angular_distance(local, c2)
    if xi is None or eta is None:
        return PointAudit("", "", lat, lon, 0.0, chunk, None, None, None, c1_margin,
                          c2_margin, None, False, False, notes)

    shared = plane_distance(local, (0.0, 1.0, 1.0))
    # External faces for the selected physical chunk.  Distances are to the
    # supporting great circles; endpoint distances above resolve corner proximity.
    if chunk == "chunk_1_central":
        external_planes = ((0.0, 1.0, -1.0), (1.0, 0.0, -1.0), (1.0, 0.0, 1.0))
    else:
        external_planes = ((0.0, 1.0, -1.0), (1.0, 1.0, 0.0), (1.0, -1.0, 0.0))
    external = min(plane_distance(local, plane) for plane in external_planes)
    return PointAudit("", "", lat, lon, 0.0, chunk, math.degrees(xi), math.degrees(eta),
                      shared, c1_margin, c2_margin, external, shared <= 1.0e-7,
                      min(c1_margin, c2_margin) <= 1.0e-7, notes)


def validate(par: dict[str, str], template: dict[str, str], cmt: dict[str, float | str],
             stations: list[dict[str, Any]], manifest: dict[str, Any], specfem_root: Path | None) -> list[str]:
    errors: list[str] = []
    unknown = sorted(set(par) - set(template))
    if unknown:
        errors.append("Par_file parameters absent from current template: " + ", ".join(unknown))
    missing = sorted(set(template) - set(par))
    if missing:
        errors.append("Par_file parameters missing from current template: " + ", ".join(missing))
    for key, reference in template.items():
        if key not in par:
            continue
        try:
            if reference.strip().lower() in {".true.", ".false.", "true", "false"}:
                bool_value(par[key])
            else:
                try:
                    number(reference)
                except ValueError:
                    if not par[key].strip():
                        raise AuditError("empty string value")
                else:
                    number(par[key])
        except (AuditError, ValueError) as exc:
            errors.append(f"{key} is not valid in the current template value class: {exc}")
    for key, expected in CANONICAL.items():
        if key not in par:
            errors.append(f"missing Par_file parameter: {key}")
            continue
        try:
            actual: object = bool_value(par[key]) if isinstance(expected, bool) else number(par[key])
        except (AuditError, ValueError) as exc:
            errors.append(f"{key}: {exc}")
            continue
        if actual != expected:
            errors.append(f"{key}={actual!r}; canonical teaching case requires {expected!r}")
    if int(number(par.get("NEX_XI", "0"))) % 16 or int(number(par.get("NEX_ETA", "0"))) % 16:
        errors.append("NEX_XI and NEX_ETA must meet the current template's multiple-of-16 comment")
    if int(number(par.get("NEX_XI", "0"))) % (8 * int(number(par.get("NPROC_XI", "1")))):
        errors.append("NEX_XI is incompatible with 8*NPROC_XI")
    if int(number(par.get("NEX_ETA", "0"))) % (8 * int(number(par.get("NPROC_ETA", "1")))):
        errors.append("NEX_ETA is incompatible with 8*NPROC_ETA")
    if not cmt["pde"] or not stations:
        errors.append("source or station records are empty")
    if not str(cmt["pde"]).lstrip().startswith("PDE"):
        errors.append("CMTSOLUTION teaching record must begin with a PDE header")
    moment_keys = ("Mrr", "Mtt", "Mpp", "Mrt", "Mrp", "Mtp")
    if not any(abs(float(cmt[key])) > 0.0 for key in moment_keys):
        errors.append("CMTSOLUTION moment tensor must not be identically zero")
    source = manifest["source_provenance"]
    if not source.get("formal_candidate_sha256") or not source.get("baseline_target_sha256"):
        errors.append("patch manifest lacks authoritative source hashes")
    if specfem_root is not None:
        target = specfem_root / "src/meshfem3D/create_chunk_buffers.f90"
        if not target.is_file():
            errors.append(f"missing target source file: {target}")
        elif sha256(target) != source["formal_candidate_sha256"]:
            errors.append("accepted patch source hash does not match the manifest formal candidate")
    return errors


def write_reports(output: Path, report: dict[str, Any], rows: list[PointAudit]) -> None:
    output.mkdir(parents=True)
    (output / "geometry_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (output / "geometry_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0])))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    lines = ["# Canonical two-chunk geometry audit", "", f"Status: **{report['status']}**", "",
             "Margins are angular geometry quantities (degrees), not universal safety thresholds.", "",
             "| role | id | classification | xi | eta | shared | C1 | C2 | external |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        value = lambda number: "n/a" if number is None else f"{number:.6f}"
        lines.append(f"| {row.role} | {row.identifier} | {row.chunk} | {value(row.xi_degrees)} | "
                     f"{value(row.eta_degrees)} | {value(row.shared_interface_margin_degrees)} | "
                     f"{row.c1_margin_degrees:.6f} | {row.c2_margin_degrees:.6f} | "
                     f"{value(row.external_boundary_margin_degrees)} |")
    if report["validation_errors"]:
        lines.extend(["", "## Validation errors", *[f"- {item}" for item in report["validation_errors"]]])
    (output / "geometry_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path(__file__).resolve().parent / "DATA")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "reports")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--specfem-root", type=Path, help="Check applied target source against manifest candidate hash.")
    parser.add_argument("--validate-only", action="store_true", help="Parse and validate only; write no reports.")
    parser.add_argument("--dry-run", action="store_true", help="Show intended report location; write nothing.")
    args = parser.parse_args()
    try:
        input_dir, project_root = args.input_dir.resolve(), args.project_root.resolve()
        par = parse_par_file(input_dir / "Par_file")
        cmt = parse_cmt(input_dir / "CMTSOLUTION")
        stations = parse_stations(input_dir / "STATIONS")
        template = template_values((args.specfem_root or project_root / "specfem3d_globe") / "DATA/Par_file")
        manifest = json.loads((project_root / "patches/specfem3d_globe/two_chunk_endpoints/"
                                            "specfem3d_globe_two_chunk_endpoints_manifest.json").read_text())
        errors = validate(par, template, cmt, stations, manifest, args.specfem_root.resolve() if args.specfem_root else None)
        matrix = euler_matrix(number(par["CENTER_LATITUDE_IN_DEGREES"]),
                              number(par["CENTER_LONGITUDE_IN_DEGREES"]),
                              number(par["GAMMA_ROTATION_AZIMUTH"]))
        source = map_point(float(cmt["latitude"]), float(cmt["longitude"]), matrix)
        source.role, source.identifier, source.elevation_or_depth = "source", str(cmt["event name"]), float(cmt["depth"])
        rows = [source]
        for station in stations:
            row = map_point(station["lat"], station["lon"], matrix)
            row.role, row.identifier, row.elevation_or_depth = "station", f"{station['network']}.{station['station']}", station["elevation"]
            rows.append(row)
        if any(row.chunk == "outside_two_chunk_domain" for row in rows):
            errors.append("at least one source/station is outside the canonical two-chunk domain")
        report = {
            "schema": "ulvz_two_chunk_geometry_audit.v1",
            "status": "pass" if not errors else "fail",
            "input_dir": str(input_dir), "manifest_patch_sha256": manifest["patch_sha256"],
            "baseline_target_sha256": manifest["source_provenance"]["baseline_target_sha256"],
            "formal_candidate_sha256": manifest["source_provenance"]["formal_candidate_sha256"],
            "total_mpi_ranks": int(number(par["NCHUNKS"])) * int(number(par["NPROC_XI"])) * int(number(par["NPROC_ETA"])),
            "mapping_provenance": [
                "specfem3d_globe/src/shared/euler_angles.f90",
                "specfem3d_globe/src/auxiliaries/write_profile.f90:get_latlon_chunk_location",
                "specfem3d_globe/src/auxiliaries/write_profile.f90:chunk_map",
            ],
            "validation_errors": errors, "points": [asdict(row) for row in rows],
        }
        if args.validate_only:
            print(json.dumps({"status": report["status"], "total_mpi_ranks": report["total_mpi_ranks"],
                              "validation_errors": errors}, indent=2))
        elif args.dry_run:
            print(f"would write geometry audit reports to {args.output_dir}")
        else:
            if args.output_dir.exists():
                raise AuditError(f"refusing to overwrite existing output directory: {args.output_dir}")
            write_reports(args.output_dir, report, rows)
            print(f"wrote {args.output_dir}")
        return 0 if not errors else 2
    except (AuditError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"audit_geometry.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
