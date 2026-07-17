# SPDX-License-Identifier: GPL-3.0-or-later
"""Strict input parsing and report serialization for the read-only planner."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from two_chunk_planner.errors import PlannerError


@dataclass(frozen=True)
class Source:
    latitude_deg: float
    longitude_deg: float
    depth_km: float
    identifier: str = "source"


@dataclass(frozen=True)
class Station:
    network: str
    station: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float = 0.0
    burial_m: float = 0.0

    @property
    def identifier(self) -> str:
        return f"{self.network}.{self.station}"


@dataclass(frozen=True)
class TargetRegion:
    name: str
    kind: str
    payload: dict[str, Any]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(text: str | float | int) -> float:
    return float(str(text).strip().replace("D", "e").replace("d", "e"))


def _finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise PlannerError(f"{label} must be finite")
    return value


def _latlon(latitude: float, longitude: float, label: str) -> tuple[float, float]:
    _finite(latitude, f"{label} latitude")
    _finite(longitude, f"{label} longitude")
    if abs(latitude) > 90.0 or abs(longitude) > 360.0:
        raise PlannerError(f"{label} latitude/longitude is outside valid numeric range")
    return latitude, longitude


def parse_cmtsolution(path: Path) -> Source:
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) != 13 or not lines[0].lstrip().startswith("PDE"):
        raise PlannerError("CMTSOLUTION must contain a PDE header and 12 labelled records")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            raise PlannerError(f"CMTSOLUTION record lacks ':': {line}")
        key, value = (part.strip() for part in line.split(":", 1))
        fields[key.lower()] = value
    for key in ("event name", "latitude", "longitude", "depth", "mrr", "mtt", "mpp", "mrt", "mrp", "mtp"):
        if key not in fields:
            raise PlannerError(f"CMTSOLUTION missing {key}")
    values = [number(fields[key]) for key in ("mrr", "mtt", "mpp", "mrt", "mrp", "mtp")]
    if not any(abs(value) > 0.0 for value in values):
        raise PlannerError("CMTSOLUTION moment tensor must not be identically zero")
    latitude, longitude = _latlon(number(fields["latitude"]), number(fields["longitude"]), "CMTSOLUTION")
    depth = _finite(number(fields["depth"]), "CMTSOLUTION depth")
    if depth < 0.0:
        raise PlannerError("CMTSOLUTION depth must be non-negative")
    return Source(latitude, longitude, depth, fields["event name"])


def parse_stations(path: Path) -> list[Station]:
    records: list[Station] = []
    seen: set[tuple[str, str]] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 6:
            raise PlannerError(f"STATIONS line {line_number} must contain six fields")
        station, network = fields[:2]
        key = (network, station)
        if key in seen:
            raise PlannerError(f"duplicate STATIONS record: {network}.{station}")
        seen.add(key)
        latitude, longitude = _latlon(number(fields[2]), number(fields[3]), f"STATIONS line {line_number}")
        elevation, burial = _finite(number(fields[4]), "station elevation"), _finite(number(fields[5]), "station burial")
        records.append(Station(network, station, latitude, longitude, elevation, burial))
    if not records:
        raise PlannerError("STATIONS contains no receivers")
    return records


def parse_station_csv(path: Path) -> list[Station]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"network", "station", "latitude_deg", "longitude_deg"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise PlannerError("station CSV requires network, station, latitude_deg, longitude_deg columns")
        rows = []
        for row in reader:
            latitude, longitude = _latlon(number(row["latitude_deg"]), number(row["longitude_deg"]), "station CSV")
            rows.append(Station(row["network"], row["station"], latitude, longitude, number(row.get("elevation_m") or 0.0), number(row.get("burial_m") or 0.0)))
    if not rows:
        raise PlannerError("station CSV contains no receivers")
    if len({(row.network, row.station) for row in rows}) != len(rows):
        raise PlannerError("station CSV has duplicate network/station records")
    return rows


def parse_par_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and "=" in line:
            key, value = (item.strip() for item in line.split("=", 1))
            if key in values:
                raise PlannerError(f"duplicate Par_file parameter: {key}")
            values[key] = value
    return values


def logical(value: str) -> bool:
    if value.strip().lower() in {".true.", "true"}:
        return True
    if value.strip().lower() in {".false.", "false"}:
        return False
    raise PlannerError(f"invalid logical value: {value}")


def compatible_nex(nex_xi: int, nex_eta: int, nproc_xi: int, nproc_eta: int, par: dict[str, str]) -> tuple[bool, str]:
    suppress = logical(par.get("SUPPRESS_CRUSTAL_MESH", ".false."))
    add_fourth = logical(par.get("ADD_4TH_DOUBLING", ".false."))
    if suppress and not add_fourth:
        base, per_proc = 8, 4
    elif suppress or not add_fourth:
        base, per_proc = 16, 8
    else:
        base, per_proc = 32, 16
    if nex_xi % base or nex_eta % base:
        return False, f"NEX must be a multiple of {base} for current Par_file physics branch"
    if nex_xi % (per_proc * nproc_xi) or nex_eta % (per_proc * nproc_eta):
        return False, f"NEX must be a multiple of {per_proc}*NPROC in each direction"
    return True, "compatible"


def _require_keys(data: dict[str, Any], allowed: set[str], required: set[str], label: str) -> None:
    unknown = set(data) - allowed
    missing = required - set(data)
    if unknown:
        raise PlannerError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise PlannerError(f"{label} missing fields: {', '.join(sorted(missing))}")


def parse_target_region(path: Path) -> TargetRegion:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PlannerError("target_region YAML must be a mapping")
    _require_keys(loaded, {"name", "type", "center", "radius_km", "vertices", "centerline", "half_width_km"}, {"type"}, "target_region")
    kind = loaded["type"]
    name = str(loaded.get("name", "target_region"))
    if kind == "circle":
        _require_keys(loaded, {"name", "type", "center", "radius_km"}, {"type", "center", "radius_km"}, "circle target")
        center = loaded["center"]
        if not isinstance(center, dict):
            raise PlannerError("circle center must be a mapping")
        _require_keys(center, {"latitude_deg", "longitude_deg"}, {"latitude_deg", "longitude_deg"}, "circle center")
        _latlon(number(center["latitude_deg"]), number(center["longitude_deg"]), "circle center")
        if number(loaded["radius_km"]) <= 0.0:
            raise PlannerError("circle radius_km must be positive")
    elif kind == "polygon":
        _require_keys(loaded, {"name", "type", "vertices"}, {"type", "vertices"}, "polygon target")
        vertices = loaded["vertices"]
        if not isinstance(vertices, list) or len(vertices) < 3:
            raise PlannerError("polygon requires at least three vertices")
        values = []
        for item in vertices:
            if not isinstance(item, dict):
                raise PlannerError("polygon vertex must be a mapping")
            _require_keys(item, {"name", "latitude_deg", "longitude_deg"}, {"name", "latitude_deg", "longitude_deg"}, "polygon vertex")
            values.append(_latlon(number(item["latitude_deg"]), number(item["longitude_deg"]), "polygon vertex"))
        if len(set(values)) < 3:
            raise PlannerError("polygon requires three distinct vertices")
    elif kind == "corridor":
        _require_keys(loaded, {"name", "type", "centerline", "half_width_km"}, {"type", "centerline", "half_width_km"}, "corridor target")
        if not isinstance(loaded["centerline"], list) or len(loaded["centerline"]) < 2 or number(loaded["half_width_km"]) <= 0.0:
            raise PlannerError("corridor requires at least two centerline points and positive half_width_km")
        for item in loaded["centerline"]:
            if not isinstance(item, dict):
                raise PlannerError("corridor centerline point must be a mapping")
            _require_keys(item, {"name", "latitude_deg", "longitude_deg"}, {"name", "latitude_deg", "longitude_deg"}, "corridor centerline point")
            _latlon(number(item["latitude_deg"]), number(item["longitude_deg"]), "corridor centerline point")
    else:
        raise PlannerError("target_region type must be circle, polygon, or corridor")
    return TargetRegion(name, kind, loaded)


def parse_weights(path: Path) -> dict[str, float]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PlannerError("weights YAML must be a mapping")
    _require_keys(loaded, {"coverage", "external_margin", "endpoint_margin", "cost"}, set(), "weights")
    values = {key: number(value) for key, value in loaded.items()}
    if any(value < 0.0 for value in values.values()) or not any(value > 0.0 for value in values.values()):
        raise PlannerError("weights must be non-negative and contain at least one positive value")
    return values


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=lambda item: asdict(item) if hasattr(item, "__dataclass_fields__") else str(item)) + "\n", encoding="utf-8")
