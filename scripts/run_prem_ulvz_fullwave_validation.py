#!/usr/bin/env python3
"""Stage and run an isolated NEX32 PREM-TISO ULVZ A/B waveform validation.

The script only reads the preserved Hawai'i one-chunk fixture.  It never
modifies that fixture, the SPECFEM DATA directory, or an existing result root.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from obspy.taup import TauPyModel

R_KM = 6371.0
SOURCE = (-5.0, 145.0, 208.6)
ULVZ_CENTER = (19.6, -155.5)
ULVZ = {
    "BACKGROUND_MODEL": "PREM", "CENTER_LATITUDE_DEGREES": "19.6",
    "CENTER_LONGITUDE_DEGREES": "-155.5", "THICKNESS_KM": "50.0",
    "LATERAL_RADIUS_KM": "512.0", "LATERAL_TAPER_KM": "100.0",
    "TOP_TAPER_KM": "10.0", "DVS": "-0.20", "DVP": "-0.15", "DRHO": "0.10",
}
ONE_CHUNK = {"width_deg": 135.0, "center_lat": 16.0, "center_lon": -166.0, "gamma": 154.0}
TEMPLATE_RELATIVE = Path("results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/05_mesh_smoke/fixtures/width_135/run/DATA")


@dataclass(frozen=True)
class Station:
    name: str
    network: str
    latitude_deg: float
    longitude_deg: float
    path_class: str
    path_distance_to_ulvz_km: float
    source_distance_deg: float
    p_diff_s: float
    s_diff_s: float
    boundary_margin_deg: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def set_value(text: str, key: str, value: str) -> str:
    pattern = rf"^({re.escape(key)}\s*=\s*).*?(\s*(?:#.*)?)$"
    text, count = re.subn(pattern, rf"\g<1>{value}\2", text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"expected exactly one {key} in template, found {count}")
    return text


def norm_lon(lon: float) -> float:
    return (lon + 180.0) % 360.0 - 180.0


def geo_to_vec(lat: float, lon: float) -> tuple[float, float, float]:
    lat, lon = math.radians(lat), math.radians(lon)
    return math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)


def angular_distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    a, b = geo_to_vec(*first), geo_to_vec(*second)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))


def euler_matrix(center_lat: float, center_lon: float, gamma: float) -> list[list[float]]:
    alpha, beta, gam = math.radians(center_lon), math.radians(90.0 - center_lat), math.radians(gamma)
    ca, sa, cb, sb, cg, sg = math.cos(alpha), math.sin(alpha), math.cos(beta), math.sin(beta), math.cos(gam), math.sin(gam)
    return [[ca * cb * cg - sa * sg, -ca * cb * sg - sa * cg, ca * sb],
            [sa * cb * cg + ca * sg, -sa * cb * sg + ca * cg, sa * sb],
            [-sb * cg, sb * sg, cb]]


def matvec(matrix: list[list[float]], vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(sum(row[index] * vector[index] for index in range(3)) for row in matrix)  # type: ignore[return-value]


def boundary_margin(point: tuple[float, float]) -> float:
    matrix = euler_matrix(ONE_CHUNK["center_lat"], ONE_CHUNK["center_lon"], ONE_CHUNK["gamma"])
    local = matvec([list(row) for row in zip(*matrix)], geo_to_vec(*point))
    xi, eta = math.degrees(math.atan2(local[1], local[2])), math.degrees(math.atan2(-local[0], local[2]))
    return ONE_CHUNK["width_deg"] / 2.0 - max(abs(xi), abs(eta))


def arc_distance_to_center_km(receiver: tuple[float, float]) -> float:
    """Minimum distance from ULVZ center to the source--receiver minor arc."""
    source, rec, center = geo_to_vec(*SOURCE[:2]), geo_to_vec(*receiver), geo_to_vec(*ULVZ_CENTER)
    total = math.radians(angular_distance(SOURCE[:2], receiver))
    if total == 0.0:
        return angular_distance(SOURCE[:2], ULVZ_CENTER) * math.pi / 180.0 * R_KM
    best = math.pi
    for index in range(1001):
        fraction = index / 1000.0
        left, right = math.sin((1.0 - fraction) * total), math.sin(fraction * total)
        point = tuple((left * source[i] + right * rec[i]) / math.sin(total) for i in range(3))
        norm = math.sqrt(sum(value * value for value in point))
        angle = math.acos(max(-1.0, min(1.0, sum(point[i] / norm * center[i] for i in range(3)))))
        best = min(best, angle)
    return best * R_KM


def choose_stations() -> list[Station]:
    """Select reproducible near/edge/far receivers without moving the fixture."""
    model = TauPyModel("prem")
    candidates: list[tuple[float, float, float, float, float]] = []
    for lat in range(-45, 66):
        for lon in range(-180, -69):
            point = (float(lat), float(lon))
            margin, distance = boundary_margin(point), angular_distance(SOURCE[:2], point)
            if margin < 20.0 or not 100.0 <= distance <= 165.0:
                continue
            arrivals = {item.name: item.time for item in model.get_travel_times(SOURCE[2], distance, ["Pdiff", "Sdiff"])}
            if {"Pdiff", "Sdiff"} <= set(arrivals):
                candidates.append((lat, lon, arc_distance_to_center_km(point), arrivals["Pdiff"], arrivals["Sdiff"]))
    categories = {
        "near_through": lambda value: value <= 512.0,
        "edge_taper": lambda value: 512.0 < value <= 612.0,
        "far": lambda value: value >= 1200.0,
    }
    chosen: list[Station] = []
    for number, (label, predicate) in enumerate(categories.items(), start=1):
        pool = [item for item in candidates if predicate(item[2])]
        if not pool:
            raise RuntimeError(f"could not select required {label} station with >=20 degree boundary margin and Pdiff/Sdiff")
        if label == "near_through":
            row = min(pool, key=lambda item: item[2])
        elif label == "edge_taper":
            row = min(pool, key=lambda item: abs(item[2] - 562.0))
        else:
            row = max(pool, key=lambda item: item[2])
        lat, lon, proxy_km, pdiff, sdiff = row
        chosen.append(Station(f"FW{number:02d}", "FV", lat, lon, label, proxy_km,
                              angular_distance(SOURCE[:2], (lat, lon)), pdiff, sdiff,
                              boundary_margin((lat, lon))))
    return chosen


def write_stations(path: Path, stations: list[Station]) -> None:
    path.write_text("".join(f"{item.name:<8} {item.network:<8} {item.latitude_deg:10.5f} {item.longitude_deg:11.5f}       0.0      0.0\n" for item in stations), encoding="utf-8")


def write_cmt(path: Path) -> None:
    path.write_text("""PDE 2012  4 17  0  0  0.00   -5.0000  145.0000 208.6 6.9 6.8 LOCALLY CONSTRUCTED
event name:     prem_ulvz_fullwave_validation
time shift:      0.0000
half duration:   10.0000
latitude:        -5.0000
longitude:       145.0000
depth:           208.6000
Mrr:       1.000000e+25
Mtt:      -1.000000e+25
Mpp:       0.000000e+00
Mrt:       0.000000e+00
Mrp:       0.000000e+00
Mtp:       0.000000e+00
""", encoding="utf-8")


def stage_case(case: Path, template: Path, enabled: bool, record_seconds: float, dt: float | None, stations: list[Station]) -> None:
    if case.exists():
        raise FileExistsError(f"refusing to overwrite existing case: {case}")
    data = case / "DATA"
    case.mkdir(parents=True)
    shutil.copytree(template, data)
    text = (data / "Par_file").read_text(encoding="utf-8")
    values = {
        "NCHUNKS": "1", "ANGULAR_WIDTH_XI_IN_DEGREES": "135.d0", "ANGULAR_WIDTH_ETA_IN_DEGREES": "135.d0",
        "CENTER_LATITUDE_IN_DEGREES": "16.d0", "CENTER_LONGITUDE_IN_DEGREES": "-166.d0", "GAMMA_ROTATION_AZIMUTH": "154.d0",
        "NEX_XI": "32", "NEX_ETA": "32", "NPROC_XI": "1", "NPROC_ETA": "1",
        "MODEL": "1D_transversely_isotropic_prem", "OCEANS": ".false.", "ELLIPTICITY": ".false.",
        "TOPOGRAPHY": ".false.", "GRAVITY": ".false.", "FULL_GRAVITY": ".false.", "ROTATION": ".false.",
        "ATTENUATION": ".false.", "REGIONAL_MESH_CUTOFF": ".false.", "ABSORBING_CONDITIONS": ".true.",
        "ABSORB_USING_GLOBAL_SPONGE": ".false.", "RECORD_LENGTH_IN_MINUTES": f"{record_seconds / 60.0:.10f}d0",
        "NTSTEP_BETWEEN_OUTPUT_INFO": "500", "NTSTEP_BETWEEN_OUTPUT_SEISMOS": "500", "NTSTEP_BETWEEN_OUTPUT_SAMPLE": "1",
        "OUTPUT_SEISMOS_ASCII_TEXT": ".true.", "OUTPUT_SEISMOS_SAC_ALPHANUM": ".false.",
        "OUTPUT_SEISMOS_SAC_BINARY": ".false.", "OUTPUT_SEISMOS_ASDF": ".false.", "RECEIVERS_CAN_BE_BURIED": ".true.",
        "MOVIE_SURFACE": ".false.", "MOVIE_VOLUME": ".false.", "SAVE_MESH_FILES": ".true.",
    }
    for key, value in values.items():
        text = set_value(text, key, value)
    if dt is not None:
        text += f"\n# Shared conservative DT from disabled pilot mesher.\nDT = {dt:.8f}d0\n"
    (data / "Par_file").write_text(text, encoding="utf-8")
    write_cmt(data / "CMTSOLUTION")
    write_stations(data / "STATIONS", stations)
    params = dict(ULVZ)
    params["ENABLED"] = ".true." if enabled else ".false."
    (data / "ulvz_s40rts.par").write_text("".join(f"{key} = {value}\n" for key, value in params.items()), encoding="utf-8")
    (case / "DATABASES_MPI").mkdir()
    (case / "OUTPUT_FILES").mkdir()


def run_logged(command: list[str], cwd: Path, log: Path, timeout_seconds: int) -> None:
    logging.info("running: %s (cwd=%s)", " ".join(command), cwd)
    with log.open("w", encoding="utf-8") as stream:
        try:
            result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"timeout after {timeout_seconds}s: {' '.join(command)}") from error
    if result.returncode:
        raise RuntimeError(f"non-zero exit ({result.returncode}): {' '.join(command)}; see {log}")


def output_text(case: Path, log: Path) -> str:
    paths = [log] + sorted((case / "OUTPUT_FILES").glob("*.txt"))
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths if path.exists())


def validate_run(case: Path, log: Path, solver: bool) -> None:
    text = output_text(case, log)
    if re.search(r"\b(?:nan|inf)\b", text, flags=re.IGNORECASE):
        raise RuntimeError(f"NaN/Inf detected in {case}")
    if re.search(r"(?:CFL.{0,80}(?:error|unstable|violation)|stability.{0,80}(?:error|unstable))", text, flags=re.IGNORECASE):
        raise RuntimeError(f"CFL/stability failure detected in {case}")
    if solver and "end of the simulation" not in text.lower():
        raise RuntimeError(f"solver completion marker missing in {case}")


def parse_pilot_dt(case: Path) -> float:
    text = output_text(case, case / "logs" / "xmeshfem3D.log")
    values = [float(value) for value in re.findall(r"Maximum suggested time step\s*=\s*([0-9.Ee+-]+)", text)]
    if not values:
        raise RuntimeError("pilot mesher did not report a maximum suggested time step")
    return min(values) * 0.90


def file_inventory(case: Path) -> dict[str, str]:
    return {str(path.relative_to(case / "DATA")): sha256(path) for path in sorted((case / "DATA").rglob("*")) if path.is_file()}


def parse_params(path: Path) -> dict[str, str]:
    return {key.strip(): value.strip() for key, value in (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.lstrip().startswith("#"))}


def audit_controls(root: Path, disabled: Path, enabled: Path) -> None:
    left, right = file_inventory(disabled), file_inventory(enabled)
    shared = sorted((set(left) | set(right)) - {"ulvz_s40rts.par"})
    mismatches = [name for name in shared if left.get(name) != right.get(name)]
    a, b = parse_params(disabled / "DATA/ulvz_s40rts.par"), parse_params(enabled / "DATA/ulvz_s40rts.par")
    differing = sorted(key for key in set(a) | set(b) if a.get(key) != b.get(key))
    report = {"shared_data_bitwise_identical": not mismatches, "shared_mismatches": mismatches,
              "ulvz_differing_keys": differing, "ulvz_only_enabled_differs": differing == ["ENABLED"],
              "disabled_data_sha256": left, "enabled_data_sha256": right}
    (root / "audit" / "input_control_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if mismatches or differing != ["ENABLED"]:
        raise RuntimeError("A/B input control audit failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--result-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-run", action="store_true", help="stage/audit only after the pilot setup")
    parser.add_argument("--solver-timeout-seconds", type=int, default=2700)
    args = parser.parse_args()
    project = args.project_root.resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (args.result_root or project / "results" / f"prem_ulvz_fullwave_validation_{timestamp}").resolve()
    template, specfem = project / TEMPLATE_RELATIVE, project / "specfem3d_globe"
    if root.exists():
        raise FileExistsError(f"result root already exists: {root}")
    if not template.is_dir() or not (specfem / "bin/xmeshfem3D").is_file() or not (specfem / "bin/xspecfem3D").is_file():
        raise RuntimeError("template or freshly-built SPECFEM executables are unavailable")
    root.mkdir(parents=True)
    logging.basicConfig(filename=root / "driver.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stations = choose_stations()
    latest_sdiff = max(item.s_diff_s for item in stations)
    requested_duration = math.ceil(latest_sdiff + 240.0)
    (root / "audit").mkdir()
    with (root / "station_geometry.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(stations[0])))
        writer.writeheader(); writer.writerows(asdict(item) for item in stations)
    with (root / "ulvz_model.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["key", "value", "units"])
        writer.writeheader()
        for key, value in ULVZ.items():
            unit = "dimensionless" if key in {"DVS", "DVP", "DRHO"} else ("km" if key.endswith("_KM") else "")
            writer.writerow({"key": key, "value": value, "units": unit})
    metadata = {"created_utc": timestamp, "source": {"latitude_deg": SOURCE[0], "longitude_deg": SOURCE[1], "depth_km": SOURCE[2]},
                "ulvz": ULVZ, "one_chunk": ONE_CHUNK, "template": str(template), "stations": [asdict(item) for item in stations],
                "postcursor_seconds": 240.0, "requested_duration_seconds": requested_duration,
                "mpi_command": ["mpirun", "-np", "1"], "binary_sha256": {name: sha256(specfem / "bin" / name) for name in ("xmeshfem3D", "xspecfem3D")}}
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pilot = root / "pilot_disabled"
    stage_case(pilot, template, False, requested_duration, None, stations)
    if args.dry_run:
        logging.info("dry run complete; no executable invoked")
        return
    (pilot / "logs").mkdir()
    run_logged([str(specfem / "bin/xmeshfem3D")], pilot, pilot / "logs/xmeshfem3D.log", args.solver_timeout_seconds)
    validate_run(pilot, pilot / "logs/xmeshfem3D.log", False)
    common_dt = parse_pilot_dt(pilot)
    nstep = math.ceil(requested_duration / common_dt)
    record_seconds = nstep * common_dt
    metadata.update({"pilot_conservative_dt_seconds": common_dt, "common_nstep": nstep, "common_record_seconds": record_seconds})
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    disabled, enabled = root / "A_disabled", root / "B_enabled"
    stage_case(disabled, template, False, record_seconds, common_dt, stations)
    stage_case(enabled, template, True, record_seconds, common_dt, stations)
    audit_controls(root, disabled, enabled)
    if args.skip_run:
        return
    for case in (disabled, enabled):
        (case / "logs").mkdir()
        run_logged([str(specfem / "bin/xmeshfem3D")], case, case / "logs/xmeshfem3D.log", args.solver_timeout_seconds)
        validate_run(case, case / "logs/xmeshfem3D.log", False)
        run_logged(["mpirun", "-np", "1", str(specfem / "bin/xspecfem3D")], case, case / "logs/xspecfem3D.log", args.solver_timeout_seconds)
        validate_run(case, case / "logs/xspecfem3D.log", True)
    comparison = project / "scripts/compare_prem_ulvz_fullwave.py"
    run_logged([sys.executable, str(comparison), "--result-root", str(root)], root, root / "compare.log", args.solver_timeout_seconds)


if __name__ == "__main__":
    main()
