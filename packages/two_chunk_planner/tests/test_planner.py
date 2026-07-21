# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from two_chunk_planner.cli import main
from two_chunk_planner.domain import CanonicalTwoChunkDomain
from two_chunk_planner.errors import PlannerError
from two_chunk_planner.geometry import angular_distance_deg, great_circle_samples, latlon_to_unit, split_dateline, unit_to_latlon
from two_chunk_planner.io import Source, Station, parse_cmtsolution, parse_stations, parse_target_region, parse_weights
from two_chunk_planner.objective import evaluate_geometry, evaluate_geometry_scalar_summary, evaluate_geometry_summaries, prepare_geometry_inputs
from two_chunk_planner.optimize import SearchSettings, SearchTrace, _around, _grid, search
from two_chunk_planner.paths import geometry_paths, taup_paths
from two_chunk_planner.profile import canonical_profile
from two_chunk_planner.transforms import EulerTransform, geocentric_colatitude, geographic_latitude, geographic_to_global_vector


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


@pytest.mark.parametrize("latitude", (-89.9, -60.0, -23.2, 0.0, 23.2, 60.0, 89.9))
def test_ellipticity_latitude_round_trip_preserves_hemisphere(latitude: float):
    colatitude = geocentric_colatitude(latitude, True)
    assert geographic_latitude(colatitude, True) == pytest.approx(latitude, abs=1.0e-12)


def test_ellipticity_true_event1_outer_arcs_remain_geographic():
    domain = CanonicalTwoChunkDomain(EulerTransform(50.5, -77.0, 225.5, ellipticity=True))
    for arc in domain.external_boundaries:
        global_points = [
            domain.transform.local_to_global(point)
            for point in great_circle_samples(arc.start_local, arc.end_local, 181)
        ]
        geographic_points = domain.global_arc(arc, 181)
        assert all(-90.0 <= latitude <= 90.0 for latitude, _ in geographic_points)
        for vector, (latitude, longitude) in zip(global_points, geographic_points):
            assert geographic_to_global_vector(latitude, longitude, True) == pytest.approx(vector, abs=1.0e-12)


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


def _reference_search(source, stations, paths, target, ellipticity, coverage, settings, weights=None):
    """Pre-optimization full-audit implementation used only for equivalence tests."""
    all_count = evaluated = feasible = rejected = 0
    seen, summary, best = set(), {}, []
    trace = {"generated": {}, "evaluated": {}, "keepers": {}}
    rank = lambda item: (-item.total_score, item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg)

    def run(stage, parameters, keep):
        nonlocal all_count, evaluated, feasible, rejected
        all_count += len(parameters)
        trace["generated"][stage] = list(parameters)
        trace["evaluated"][stage] = []
        retained = []
        for latitude, longitude, gamma in parameters:
            key = (latitude, longitude, gamma)
            if key in seen:
                continue
            seen.add(key)
            item = evaluate_geometry(CanonicalTwoChunkDomain(EulerTransform(latitude, longitude, gamma, ellipticity)), latitude, longitude, gamma, source, stations, paths, target, coverage, weights)
            trace["evaluated"][stage].append(item)
            evaluated += 1
            if item.feasible:
                feasible += 1
                best.append(item)
                if len(best) > 10:
                    best[:] = sorted(best, key=rank)[:5]
            else:
                rejected += 1
                for reason in item.rejection_reasons:
                    summary[reason] = summary.get(reason, 0) + 1
            retained.append(item)
            if len(retained) > keep * 2:
                retained = sorted(retained, key=rank)[:keep]
        selected = sorted(retained, key=rank)[:keep]
        trace["keepers"][stage] = [(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg) for item in selected]
        return selected

    coarse = run("coarse", _grid(settings), 20)
    local = run("local", [value for item in coarse for value in _around(item, 10.0, 10.0, 15.0, settings.local_latitude_step, settings.local_longitude_step, settings.local_gamma_step, settings)], 20)
    run("final", [value for item in local[:5] for value in _around(item, 2.0, 2.0, 2.0, settings.final_latitude_step, settings.final_longitude_step, settings.final_gamma_step, settings)], 20)
    chosen = sorted({(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg): item for item in best}.values(), key=rank)[:5]
    return chosen, (all_count, len(seen), evaluated, feasible, rejected, dict(sorted(summary.items()))), trace


@pytest.mark.parametrize("settings", [
    SearchSettings(latitude_min=0, latitude_max=0, longitude_min=0, longitude_max=0, gamma_min=0, gamma_max=0),
    SearchSettings(latitude_min=-10, latitude_max=10, longitude_min=-20, longitude_max=20, gamma_min=0, gamma_max=30, coarse_latitude_step=10, coarse_longitude_step=10, coarse_gamma_step=15, local_latitude_step=2, local_longitude_step=2, local_gamma_step=3, final_latitude_step=0.5, final_longitude_step=0.5, final_gamma_step=0.5),
])
def test_compact_search_matches_full_audit_reference(settings):
    source, stations = parse_cmtsolution(DATA / "CMTSOLUTION"), parse_stations(DATA / "STATIONS")
    paths = geometry_paths(source, stations, 7)
    expected, counts, reference_trace = _reference_search(source, stations, paths, None, False, 1.0, settings)
    trace = SearchTrace.empty()
    actual = search(source, stations, paths, None, False, 1.0, settings, trace=trace)
    assert (actual.all_candidate_count, actual.deduplicated_candidate_count, actual.evaluated_count, actual.feasible_count, actual.rejected_count, actual.rejection_summary) == counts
    assert trace.generated == reference_trace["generated"]
    assert trace.keepers == reference_trace["keepers"]
    for stage, expected_items in reference_trace["evaluated"].items():
        observed = trace.evaluated[stage]
        assert [(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg) for item in observed] == [(item.center_latitude_deg, item.center_longitude_deg, item.gamma_rotation_azimuth_deg) for item in expected_items]
        for compact, full in zip(observed, expected_items):
            assert compact.evaluation.feasible == full.feasible
            assert compact.evaluation.rejection_reasons == tuple(full.rejection_reasons)
            assert compact.evaluation.warnings == tuple(full.warnings)
            assert compact.evaluation.coverage == full.score_components["coverage"]
            assert compact.evaluation.external_margin == pytest.approx(full.score_components["external_margin"], abs=1.0e-10)
            assert compact.evaluation.endpoint_margin == pytest.approx(full.score_components["endpoint_margin"], abs=1.0e-12)
            assert compact.evaluation.total_score == pytest.approx(full.total_score, abs=1.0e-12)
    assert [item.to_dict() for item in actual.candidates] == [item.to_dict() for item in expected]


def test_multi_orientation_path_batch_matches_scalar_reference():
    source, stations = parse_cmtsolution(DATA / "CMTSOLUTION"), parse_stations(DATA / "STATIONS")
    paths = geometry_paths(source, stations, 7)
    parameters = ((0.0, 0.0, 0.0), (10.0, -20.0, 15.0), (-10.0, 30.0, 45.0))
    domains = tuple(CanonicalTwoChunkDomain(EulerTransform(*item)) for item in parameters)
    prepared = prepare_geometry_inputs(source, stations, paths, None, False)
    observed, uncertain = evaluate_geometry_summaries(domains, source, stations, paths, None, prepared, 1.0)
    assert not uncertain.any()
    for parameter, domain, batch in zip(parameters, domains, observed):
        scalar = evaluate_geometry_scalar_summary(domain, *parameter, source, stations, paths, None, 1.0)
        assert batch.feasible == scalar.feasible
        assert batch.rejection_reasons == scalar.rejection_reasons
        assert batch.warnings == scalar.warnings
        assert batch.coverage == scalar.coverage
        assert batch.external_margin == pytest.approx(scalar.external_margin, abs=1.0e-10)
        assert batch.endpoint_margin == pytest.approx(scalar.endpoint_margin, abs=1.0e-12)
        assert batch.total_score == pytest.approx(scalar.total_score, abs=1.0e-12)


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


def test_bundled_profile_is_runtime_resource():
    profile = canonical_profile()
    assert profile["profile_version"] == "canonical_profile_v1"
    assert profile["canonical_geometry"]["NCHUNKS"] == 2
    assert profile["planning_defaults"]["NEX_XI"] == 96


def test_cli_runs_without_project_root_manifest_specfem_or_par_file(tmp_path: Path, monkeypatch):
    cmtsolution = tmp_path / "CMTSOLUTION"
    stations = tmp_path / "STATIONS"
    cmtsolution.write_text((DATA / "CMTSOLUTION").read_text(encoding="utf-8"), encoding="utf-8")
    stations.write_text((DATA / "STATIONS").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "standalone"
    assert main([
        "plan", "--cmtsolution", str(cmtsolution), "--stations", str(stations),
        "--analysis-window", "0", "300", "--output", str(output),
        "--latitude-range", "0,0", "--longitude-range", "0,0", "--gamma-range", "0,0",
    ]) == 0
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["planner_mode"] == "standalone"
    assert manifest["specfem_source_verified"] is False
    assert manifest["accepted_patch_verified"] is False
    assert manifest["par_file_source"] == "builtin_profile"
    assert manifest["configuration_status"] == "planning_defaults_only"
    assert "not a complete Par_file" in (output / "recommended_Par_file.inc").read_text(encoding="utf-8")


def test_cli_external_par_file_is_arbitrary_path(tmp_path: Path):
    external = tmp_path / "unrelated" / "settings.par"
    external.parent.mkdir()
    external.write_text("NEX_XI = 96\nNEX_ETA = 96\nNPROC_XI = 2\nNPROC_ETA = 2\nELLIPTICITY = .false.\n", encoding="utf-8")
    output = tmp_path / "external"
    assert main([
        "plan", "--cmtsolution", str(DATA / "CMTSOLUTION"), "--stations", str(DATA / "STATIONS"),
        "--analysis-window", "0", "300", "--par-file", str(external), "--output", str(output),
        "--latitude-range", "0,0", "--longitude-range", "0,0", "--gamma-range", "0,0",
    ]) == 0
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["par_file_source"] == "external_file"
    assert manifest["configuration_status"] == "external_par_file_read"


def test_removed_project_and_specfem_options_are_not_parser_options():
    with pytest.raises(SystemExit):
        main(["plan", "--project-root", "unused"])
    with pytest.raises(SystemExit):
        main(["plan", "--specfem-root", "unused"])
