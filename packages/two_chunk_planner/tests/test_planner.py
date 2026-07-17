from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from two_chunk_planner.cli import main
from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.errors import PlannerError
from two_chunk_planner.geometry import angular_distance_deg, latlon_to_unit, split_dateline, unit_to_latlon
from two_chunk_planner.io import Source, Station, parse_cmtsolution, parse_stations, parse_target_region, parse_weights
from two_chunk_planner.optimize import SearchSettings, search
from two_chunk_planner.paths import geometry_paths, taup_paths
from two_chunk_planner.transforms import EulerTransform


REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "packages/two_chunk_planner/examples"
DATA = EXAMPLES / "geometry_only/DATA"
PHASE_DATA = EXAMPLES / "phase_aware/DATA"


def fixture_domain() -> CanonicalTwoChunkDomain:
    return CanonicalTwoChunkDomain(EulerTransform(0.0, 0.0, 0.0))


def test_geographic_cartesian_round_trip():
    point = latlon_to_unit(-23.2, 179.9)
    latitude, longitude = unit_to_latlon(point)
    assert latitude == pytest.approx(-23.2)
    assert longitude == pytest.approx(179.9)


def test_package_geometry_example_chunks_and_endpoints():
    domain = fixture_domain()
    source = parse_cmtsolution(DATA / "CMTSOLUTION")
    stations = parse_stations(DATA / "STATIONS")
    assert domain.classify(source.latitude_deg, source.longitude_deg).chunk == "chunk_1_central"
    assert all(domain.classify(item.latitude_deg, item.longitude_deg).chunk == "chunk_2_left_attached" for item in stations)
    for name in ("C1", "C2"):
        endpoint = domain.global_endpoint(name)
        latitude, longitude = domain.transform.local_to_geographic(domain.c1_local if name == "C1" else domain.c2_local)
        assert angular_distance_deg(endpoint, latlon_to_unit(latitude, longitude)) < 1.0e-8
        assert domain.interface_distance(latitude, longitude) < 1.0e-8


def test_rotation_preserves_distance_and_detects_outside():
    first = CanonicalTwoChunkDomain(EulerTransform(0.0, 0.0, 0.0))
    second = CanonicalTwoChunkDomain(EulerTransform(20.0, -140.0, 137.0))
    local_a, local_b = first.c1_local, first.c2_local
    assert angular_distance_deg(local_a, local_b) == pytest.approx(angular_distance_deg(second.transform.local_to_global(local_a), second.transform.local_to_global(local_b)))
    assert first.classify(-80.0, 0.0).classification == "outside_two_chunk_domain"


def test_synthetic_phase_fixture_is_actually_ab_to_ac():
    domain = CanonicalTwoChunkDomain(EulerTransform(0.0, 0.0, 0.0))
    source, station = parse_cmtsolution(PHASE_DATA / "CMTSOLUTION"), parse_stations(PHASE_DATA / "STATIONS")[0]
    assert domain.classify(source.latitude_deg, source.longitude_deg).classification == "chunk_1_central"
    assert domain.classify(station.latitude_deg, station.longitude_deg).classification == "chunk_2_left_attached"


def test_target_yaml_is_optional_and_strict(tmp_path: Path):
    path = tmp_path / "target.yaml"
    path.write_text("name: target\ntype: circle\ncenter:\n  latitude_deg: 19.6\n  longitude_deg: -155.5\nradius_km: 512\n", encoding="utf-8")
    target = parse_target_region(path)
    assert target.kind == "circle"
    path.write_text("type: circle\ncenter: {latitude_deg: 0, longitude_deg: 0}\nradius_km: 1\nunknown: true\n", encoding="utf-8")
    with pytest.raises(PlannerError, match="unknown"):
        parse_target_region(path)
    weights = tmp_path / "weights.yaml"
    weights.write_text("coverage: 1\nexternal_margin: 2\nendpoint_margin: 3\ncost: 4\n", encoding="utf-8")
    assert parse_weights(weights)["cost"] == 4.0


def test_deterministic_fixed_search_and_canonical_inc(tmp_path: Path):
    source, stations = parse_cmtsolution(DATA / "CMTSOLUTION"), parse_stations(DATA / "STATIONS")
    paths = geometry_paths(source, stations, 3)
    settings = SearchSettings(latitude_min=0, latitude_max=0, longitude_min=0, longitude_max=0, gamma_min=0, gamma_max=0)
    first = search(source, stations, paths, None, False, 1.0, settings)
    second = search(source, stations, paths, None, False, 1.0, settings)
    assert first.feasible_count == second.feasible_count == 1
    assert [item.to_dict() for item in first.candidates] == [item.to_dict() for item in second.candidates]


def test_taup_strict_missing_pairs_are_aggregated():
    source, stations = parse_cmtsolution(PHASE_DATA / "CMTSOLUTION"), parse_stations(PHASE_DATA / "STATIONS")
    second = Station("PA", "PDA02", stations[0].latitude_deg, stations[0].longitude_deg)
    with pytest.raises(PlannerError) as raised:
        taup_paths(source, [stations[0], second], ["Pdiff", "NotARealPhase"], "prem", True, 1.0e-6)
    assert "NotARealPhase at PA.PDA01" in str(raised.value)
    assert "NotARealPhase at PA.PDA02" in str(raised.value)


def test_taup_geographic_pdiff_sdiff_metadata_and_length():
    pytest.importorskip("geographiclib")
    source, stations = parse_cmtsolution(PHASE_DATA / "CMTSOLUTION"), parse_stations(PHASE_DATA / "STATIONS")
    records, missing = taup_paths(source, stations, ["Pdiff", "Sdiff"], "prem", True, 1.0e-6)
    assert not missing
    assert {record.requested_phase for record in records} == {"Pdiff", "Sdiff"}
    for record in records:
        assert record.phase == record.requested_phase == record.returned_phase
        assert record.raypath_length_status == "taup_raypath_polyline_estimate"
        assert record.raypath_length_km is not None and math.isfinite(record.raypath_length_km) and record.raypath_length_km > 0.0
        assert record.maximum_sampled_depth_km is not None and record.maximum_sampled_depth_km > 0.0
        assert record.cmb_near_proxy["approximation"] is True
        assert record.cmb_near_proxy["sample_count"] > 0
        assert record.metadata["boundary_time_use"] == "forbidden"
        assert record.metadata["resample"] is True


def test_taup_partial_keeps_inventory_without_phase_substitution():
    source, stations = parse_cmtsolution(PHASE_DATA / "CMTSOLUTION"), parse_stations(PHASE_DATA / "STATIONS")
    records, missing = taup_paths(source, stations, ["Pdiff", "NotARealPhase"], "prem", False, 1.0e-6, allow_partial=True)
    assert [record.requested_phase for record in records] == ["Pdiff"]
    assert missing[0]["station_id"] == "PA.PDA01"
    assert missing[0]["requested_phase"] == "NotARealPhase"
    assert missing[0]["reason"].startswith("TauP request failed:")


def test_taup_dateline_path_is_split_without_false_map_chord():
    source = Source(0.0, -170.0, 50.0, "dateline_source")
    station = Station("PA", "DATE", 0.0, 65.0)
    records, missing = taup_paths(source, [station], ["Pdiff"], "prem", True, 1.0e-6)
    assert not missing
    assert len(split_dateline(records[0].points)) > 1
    assert records[0].raypath_length_km is not None and records[0].raypath_length_km > 0.0


def test_no_non90_geometry_is_exposed():
    source, stations = parse_cmtsolution(DATA / "CMTSOLUTION"), parse_stations(DATA / "STATIONS")
    result = search(source, stations, geometry_paths(source, stations, 3), None, False, 1.0, SearchSettings(latitude_min=0, latitude_max=0, longitude_min=0, longitude_max=0, gamma_min=0, gamma_max=0))
    assert result.candidates
    candidate = result.candidates[0].to_dict()
    assert candidate["center_latitude_deg"] == 0.0
    assert "ANGULAR_WIDTH_XI_IN_DEGREES" not in candidate


def test_cli_fixture_integration_writes_canonical_fragment(tmp_path: Path):
    output = tmp_path / "plan"
    code = main([
        "plan", "--cmtsolution", str(DATA / "CMTSOLUTION"), "--stations", str(DATA / "STATIONS"),
        "--analysis-window", "0", "300", "--output", str(output), "--latitude-range", "0,0",
        "--longitude-range", "0,0", "--gamma-range", "0,0", "--path-samples", "3", "--available-ranks", "8",
    ])
    assert code == 0
    payload = json.loads((output / "candidates.json").read_text())
    assert payload["returned_candidate_count"] == 1
    fragment = (output / "recommended_Par_file.inc").read_text()
    assert "NCHUNKS                         = 2" in fragment
    assert "ANGULAR_WIDTH_XI_IN_DEGREES     = 90.d0" in fragment
    assert "ANGULAR_WIDTH_ETA_IN_DEGREES    = 90.d0" in fragment


def test_cli_phase_partial_inventory_is_written(tmp_path: Path):
    output = tmp_path / "phase_partial"
    code = main([
        "plan", "--cmtsolution", str(PHASE_DATA / "CMTSOLUTION"), "--stations", str(PHASE_DATA / "STATIONS"),
        "--phases", "Pdiff,NotARealPhase", "--path-mode", "phase-aware", "--allow-partial-phase-coverage",
        "--analysis-window", "0", "1900", "--output", str(output), "--latitude-range", "0,0",
        "--longitude-range", "0,0", "--gamma-range", "0,0", "--available-ranks", "8",
    ])
    assert code == 0
    inventory = json.loads((output / "candidates.json").read_text())["phase_inventory"]
    assert inventory["mode"] == "partial"
    assert len(inventory["requested_pairs"]) == 2
    assert len(inventory["provided_pairs"]) == 1
    assert inventory["missing_pairs"][0]["requested_phase"] == "NotARealPhase"
    geometry = json.loads((output / "geometry_audit.json").read_text())
    assert geometry["phase_inventory"] == inventory
    assert "partial coverage" in (output / "report.md").read_text()
    boundary = json.loads((output / "boundary_time_audit.json").read_text())
    assert boundary["taup_path_use"] == "forbidden"
    assert boundary["hard_constraint_used"] is False
    assert boundary["boundary_time_production_safe"] is False
