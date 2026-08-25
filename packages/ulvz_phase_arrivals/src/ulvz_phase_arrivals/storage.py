"""CSV and ASDF AuxiliaryData-compatible sidecar persistence."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterable

import h5py
import numpy as np

from .core import CSV_FIELDS, SCHEMA_VERSION, V1_CSV_FIELDS, V1_SCHEMA_VERSION, normalize_rows

SIDECAR_NAME = "synthetic.theoretical_arrivals.h5"
CSV_NAME = "theoretical_arrivals.csv"


def output_paths(output_dir: Path) -> tuple[Path, Path]:
    return output_dir / SIDECAR_NAME, output_dir / CSV_NAME


def _encode(value: str, width: int) -> bytes:
    return value.encode("utf-8")[:width]


def _validate_written_rows(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    for row in rows:
        missing = [field for field in CSV_FIELDS if field not in row]
        extra = [field for field in row if field not in CSV_FIELDS]
        if missing or extra or row.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("writer requires normalized v1.1 rows")


def _write_sidecar(path: Path, rows: list[dict[str, str]], provenance: dict[str, object]) -> None:
    _validate_written_rows(rows)
    by_station: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_station.setdefault((row["network"], row["station"]), []).append(row)
    with h5py.File(path, "w") as handle:
        handle.attrs["sidecar_kind"] = "ASDF AuxiliaryData-compatible HDF5 sidecar"
        handle.attrs["schema_version"] = SCHEMA_VERSION
        handle.attrs["provenance"] = json.dumps(provenance, sort_keys=True)
        root = handle.require_group("AuxiliaryData").require_group("TheoreticalArrivals")
        for (network, station), station_rows in sorted(by_station.items()):
            widths = {field: max(1, max(len(row[field].encode("utf-8")) for row in station_rows)) for field in CSV_FIELDS}
            dtype = np.dtype([(field, f"S{widths[field]}") for field in CSV_FIELDS])
            data = np.empty(len(station_rows), dtype=dtype)
            for index, row in enumerate(station_rows):
                data[index] = tuple(_encode(row[field], widths[field]) for field in CSV_FIELDS)
            dataset = root.require_group(f"{network}_{station}").create_dataset("data", data=data)
            dataset.attrs["parameters"] = json.dumps({"schema_version": SCHEMA_VERSION, "fields": list(CSV_FIELDS),
                                                        "row_layout": "trace x requested_phase x TauP_arrival"}, sort_keys=True)


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_sidecar_raw(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with h5py.File(path, "r") as handle:
        root_version = str(handle.attrs.get("schema_version", ""))
        if root_version not in {V1_SCHEMA_VERSION, SCHEMA_VERSION}:
            raise ValueError(f"{path}: unsupported theoretical-arrivals schema version")
        root = handle["AuxiliaryData/TheoreticalArrivals"]
        for station_group in root.values():
            data = station_group["data"]
            fields = tuple(data.dtype.names or ())
            expected = V1_CSV_FIELDS if root_version == V1_SCHEMA_VERSION else CSV_FIELDS
            if fields != expected:
                raise ValueError(f"{data.name}: incompatible arrival schema")
            parameters = json.loads(str(data.attrs.get("parameters", "{}")))
            if parameters.get("schema_version") != root_version or tuple(parameters.get("fields", ())) != expected:
                raise ValueError(f"{data.name}: incompatible arrival schema parameters")
            for record in data:
                rows.append({field: bytes(record[field]).decode("utf-8") for field in expected})
    return rows


def read_sidecar(path: Path) -> list[dict[str, str]]:
    """Read and normalize a formal HDF5 sidecar from schema v1.0 or v1.1."""
    return normalize_rows(_read_sidecar_raw(path))


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read and normalize a formal CSV annotation from schema v1.0 or v1.1."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: empty theoretical-arrivals CSV")
        fields = tuple(reader.fieldnames)
        if fields not in {V1_CSV_FIELDS, CSV_FIELDS}:
            raise ValueError(f"{path}: incompatible arrival schema")
        rows = list(reader)
    versions = {row.get("schema_version", "") for row in rows}
    expected_version = V1_SCHEMA_VERSION if fields == V1_CSV_FIELDS else SCHEMA_VERSION
    if versions and versions != {expected_version}:
        raise ValueError(f"{path}: schema version does not match CSV fields")
    return normalize_rows(rows)


def read_annotation(output_dir: Path) -> list[dict[str, str]] | None:
    """Read a CSV-only, HDF5-only, or verified matching annotation pair."""
    sidecar, csv_path = output_paths(output_dir)
    has_sidecar, has_csv = sidecar.is_file(), csv_path.is_file()
    if not has_sidecar and not has_csv:
        return None
    h5_rows = read_sidecar(sidecar) if has_sidecar else None
    csv_rows = read_csv(csv_path) if has_csv else None
    if h5_rows is not None and csv_rows is not None and h5_rows != csv_rows:
        raise ValueError(f"{output_dir}: CSV and HDF5 arrival annotations differ")
    return h5_rows if h5_rows is not None else csv_rows


def write_outputs(output_dir: Path, rows: list[dict[str, str]], provenance: dict[str, object], *, overwrite: bool = False) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    sidecar, csv_path = output_paths(output_dir)
    existing = [path for path in (sidecar, csv_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError("refusing to overwrite existing annotation output(s): " + ", ".join(str(path) for path in existing))
    temporary = Path(tempfile.mkdtemp(prefix=".theoretical-arrivals-", dir=output_dir))
    try:
        staged_sidecar, staged_csv = output_paths(temporary)
        _write_sidecar(staged_sidecar, rows, provenance)
        restored = read_sidecar(staged_sidecar)
        if restored != rows:
            raise RuntimeError("sidecar readback does not reproduce the arrival rows")
        _write_csv(staged_csv, restored)
        os.replace(staged_sidecar, sidecar)
        os.replace(staged_csv, csv_path)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return sidecar, csv_path
