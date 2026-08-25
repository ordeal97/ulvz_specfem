"""PREM/TauP theoretical-arrival annotation for SPECFEM synthetic outputs."""

API_VERSION = "0.2.0"

from .core import (
    CSV_FIELDS,
    SCHEMA_VERSION,
    V1_SCHEMA_VERSION,
    DEFAULT_PHASES,
    TraceAxis,
    annotate_run,
    arrival_identity,
    derive_convolved_rows,
    parse_cmtsolution,
    parse_stations,
)
from .sac import SAC_PRIMARY_PICK_SLOTS, retime_sac_primary_picks
from .storage import read_annotation, read_csv, read_sidecar, write_outputs

__all__ = [
    "API_VERSION", "CSV_FIELDS", "SCHEMA_VERSION", "V1_SCHEMA_VERSION", "DEFAULT_PHASES", "TraceAxis",
    "SAC_PRIMARY_PICK_SLOTS", "annotate_run", "arrival_identity", "derive_convolved_rows",
    "parse_cmtsolution", "parse_stations", "read_annotation", "read_csv", "read_sidecar",
    "retime_sac_primary_picks", "write_outputs",
]
