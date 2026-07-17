<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Canonical two-chunk planner user guide

Version 0.2.0. `two_chunk_planner` is a completely standalone, read-only
canonical two-chunk planning tool. After installation it runs from any
directory and needs no ULVZ project, SPECFEM worktree, or patch manifest.

## 1. Scope and limits

It plans only `NCHUNKS=2`, canonical 90°×90° geometry: AB is the central first
chunk and AC is the supported-left second chunk. It does not support other
widths, attachment sides, independent orientations, arbitrary two-chunk or
multi-chunk topology. `general_two_chunk_mode_classification=B`.

The tool searches center latitude/longitude and `GAMMA_ROTATION_AZIMUTH`,
classifies sources/receivers, audits paths and emits a reviewable parameter
fragment. It never runs or replaces topology, mesher, database, Stacey, solver,
waveform, or production boundary-return acceptance.

## 2. Install and start

Install a supplied wheel from any directory:

```bash
python -m pip install two_chunk_planner-0.2.0-py3-none-any.whl
```

Install from a source distribution or source directory:

```bash
python -m pip install two_chunk_planner-0.2.0.tar.gz
python -m pip install .
python -m pip install -e '.[phase-aware]'
```

The optional `phase-aware` extra provides ObsPy. Confirm geographic TauP support
instead of assuming it:

```bash
python -c 'from obspy.geodetics.base import HAS_GEOGRAPHICLIB; print(HAS_GEOGRAPHICLIB)'
two-chunk-planner --help
python -m two_chunk_planner --help
```

For package development only, run without installing:

```bash
PYTHONPATH=src python -m two_chunk_planner --help
```

## 3. Quick standalone cases

The following fixtures are synthetic and not Kim/Song inputs. Set `P` to a copy
of the package examples; every output directory must not exist.

```bash
P=/path/to/two_chunk_planner/examples
two-chunk-planner plan --cmtsolution "$P/geometry_only/DATA/CMTSOLUTION" \
  --stations "$P/geometry_only/DATA/STATIONS" --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 --output geometry_plan
```

```bash
two-chunk-planner plan --cmtsolution "$P/phase_aware/DATA/CMTSOLUTION" \
  --stations "$P/phase_aware/DATA/STATIONS" --path-mode phase-aware \
  --phases Pdiff,Sdiff --taup-model prem --taup-resample --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 --output phase_plan
```

```bash
two-chunk-planner plan --cmtsolution "$P/geometry_only/DATA/CMTSOLUTION" \
  --stations "$P/geometry_only/DATA/STATIONS" --par-file "$P/external_par_file/Par_file" \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output external_par_plan
```

## 4. Inputs and profile

Provide exactly one of `--cmtsolution` or `--source LAT LON DEPTH_KM`, and one
of `--stations` or `--stations-csv`. Source, station and target YAML files may
be at any readable path. Circle/polygon/corridor targets are optional.

`--par-file` is the only optional external configuration context. It may be at
any path; it reads NEX/NPROC and relevant compatibility flags but is neither
located through SPECFEM nor edited. If absent, planning defaults come from
`src/two_chunk_planner/resources/canonical_profile_v1.json`: NEX=96 and the
canonical geometry/provenance reference. These are planning defaults, not the
user's production configuration. The profile never accesses a user SPECFEM
tree, patch manifest, or source hash.

The [English CLI reference](cli_reference_en.md) and
[Chinese CLI reference](cli_reference_zh.md) are the complete, authoritative
35-option list. Use them for TauP, target, search, scoring, NEX/MPI and output
details; this guide explains only common workflow choices.

## 5. Path modes and planning

`geometry-only` is the default and uses sampled surface great circles.
`phase-aware` requests each requested phase×station with TauP; Pdiff/Sdiff
geographic paths are validated. Strict coverage is default; partial coverage
requires `--allow-partial-phase-coverage` and never substitutes a phase.
TauP length is `taup_raypath_polyline_estimate`; CMB-near information is a
sampled proxy. TauP is forbidden for boundary-return timing.

Search is deterministic coarse/local/final center-gamma refinement. Candidate
geometry remains canonical; target coverage, external margins and endpoint
margins are hard/transparent checks. NEX=96 at total ranks 2/8/12 is labelled
`project_validated`; other compatible choices are not project-validated.

## 6. Outputs and verification boundary

Each successful run writes `candidates.json`, `candidates.csv`,
`geometry_audit.json`, `boundary_time_audit.json`, `report.md`, `map.png`,
`run_manifest.json`, and `recommended_Par_file.inc`.

All audits record `planner_mode=standalone`, `compatibility_profile_version`,
`specfem_source_verified=false`, `accepted_patch_verified=false`,
`production_configuration_verified=false`, `par_file_source`,
`configuration_status`, and `verification_warnings`. These false values are
not planning failures: independent planning deliberately does not inspect a
user's SPECFEM source, installed patch, mesh, or runtime validation.

`recommended_Par_file.inc` is a suggested parameter fragment, not a complete
or runnable Par_file. Review candidates, geometry audit, boundary-time audit,
report and fragment before copying anything manually.

## 7. Complete workflow

1. Install the package and prepare source/stations.
2. Choose geometry-only screening or phase-aware review.
3. Optionally prepare a strict target YAML and/or external Par_file.
4. Run `plan` to a new output directory.
5. Review candidate ranking, classifications, margins, warnings and resource labels.
6. In a separate SPECFEM workflow, apply/verify the accepted patch, then validate
   mesh/topology, Stacey, solver, waveform and external returns.

## 8. Boundary time, license and scientific status

Boundary seconds are always advisory `heuristic_not_conservative` surface-arc
proxies; `boundary_time_production_safe=false`. Sampling stability is
`indeterminate` (Pdiff 0.130094%, Sdiff 0.076131% resample-length differences).
Kim/Song exact reconstruction remains unavailable without author inputs.

This package is [GPL-3.0-or-later](../LICENSE); see
[third-party notices](../THIRD_PARTY_NOTICES.md) and
[validation status](validation_status.md).
