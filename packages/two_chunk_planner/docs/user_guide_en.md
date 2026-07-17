# Canonical two-chunk planner user guide

## 1. Purpose and supported scope

`two_chunk_planner` is a pre-run, read-only planning and audit tool for this
ULVZ project's accepted canonical regional geometry. It searches central
latitude/longitude and `GAMMA_ROTATION_AZIMUTH`, classifies sources and
receivers, audits path/target coverage, and emits a reviewable Par_file
fragment. It neither runs nor replaces SPECFEM mesher, database, solver,
Stacey, decomposition, waveform, or production boundary-return validation.

It supports only `NCHUNKS=2`, 90°×90° chunks, AB as the central first chunk,
and AC as the supported-left second chunk. Both chunks share one system-wide
orientation. It does not support non-90° or rectangular chunks, another
attachment side, nonadjacent chunks, independently oriented chunks, arbitrary
two-chunk topology, or three-/multi-chunk models. See the
[geometry schematic](figures/canonical_two_chunk_geometry.svg).

## 2. Environment and installation

The package requires Python >=3.11, NumPy, Matplotlib and PyYAML. Phase-aware
mode additionally needs ObsPy; geographic TauP paths need geographiclib to be
available through ObsPy. In this project use:

```bash
PY=${ULVZ_PYTHON:-python3}
PYTHONPATH=packages/two_chunk_planner/src "$PY" -m two_chunk_planner --help
PYTHONPATH=packages/two_chunk_planner/src "$PY" - <<'PY'
from obspy.geodetics.base import HAS_GEOGRAPHICLIB
print(HAS_GEOGRAPHICLIB)
PY
```

An editable installation is optional:

```bash
"$PY" -m pip install -e packages/two_chunk_planner
"$PY" -m pip install -e 'packages/two_chunk_planner[phase]'
```

The second command declares the ObsPy phase extra. Confirm `HAS_GEOGRAPHICLIB`
instead of assuming geographiclib is present. Do not treat installation as
patch application. If the package is installed outside this project checkout,
pass both `--project-root` and `--specfem-root`, because hash verification
needs the project patch manifest and the target SPECFEM source. Missing ObsPy
raises `phase-aware mode requires optional dependency obspy`; missing
geographic positions become missing phase-path requests rather than substitute
paths.

## 3. Quick start

Run from the repository root. Every `--output` path must not already exist.

```bash
P=packages/two_chunk_planner
PY=${ULVZ_PYTHON:-python3}
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan \
  --cmtsolution $P/examples/geometry_only/DATA/CMTSOLUTION \
  --stations $P/examples/geometry_only/DATA/STATIONS \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output $P/validation/manual_geometry_<UTC>
```

For TauP Pdiff/Sdiff run:

```bash
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan \
  --cmtsolution $P/examples/phase_aware/DATA/CMTSOLUTION --stations $P/examples/phase_aware/DATA/STATIONS \
  --path-mode phase-aware --phases Pdiff,Sdiff --taup-model prem --taup-resample \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output $P/validation/manual_phase_<UTC>
```

For CSV stations run:

```bash
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan --source 0 0 50 \
  --stations-csv $P/examples/station_csv/stations.csv --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output $P/validation/manual_csv_<UTC>
```

The fixed `0,0` center/gamma ranges are only quick deterministic example
constraints, not a general recommendation.

## 4. Inputs and validation

Provide exactly one of `--cmtsolution` and `--source LAT LON DEPTH_KM`, and
exactly one of `--stations` and `--stations-csv`. CMTSOLUTION needs a PDE
header and 12 labelled records; nonzero moment tensor, finite latitude,
longitude and nonnegative depth are enforced. STATIONS has six whitespace
fields: station, network, latitude, longitude, elevation, burial. CSV requires
`network,station,latitude_deg,longitude_deg`; `elevation_m` and `burial_m` are
optional. Duplicate network/station identifiers and invalid numeric positions
are rejected.

The planner reads `--par-file` or `DATA/Par_file` below `--specfem-root`; it uses
`ELLIPTICITY`, `SUPPRESS_CRUSTAL_MESH`, and `ADD_4TH_DOUBLING` for geometry or
NEX compatibility. It does not edit that file. A run needs requested phases,
an analysis window, or `--target-energy-end-s`.

`--target-region` is strict YAML. The package examples show:

- circle: `name`, `type: circle`, `center.latitude_deg`,
  `center.longitude_deg`, `radius_km`;
- polygon: `name`, `type: polygon`, and at least three named vertices with
  latitude/longitude;
- corridor: `name`, `type: corridor`, two or more named centerline points,
  and positive `half_width_km`.

Unknown or missing YAML fields are errors. `--weights` is a separate strict
mapping whose only keys are `coverage`, `external_margin`, `endpoint_margin`,
and `cost`; it has no YAML/CLI precedence conflict. Source and station input
forms are mutually exclusive, rather than merged.

## 5. Path modes and phase coverage

`geometry-only` (default) samples surface source-station great circles. Its
`--phases` text is not used to create phase paths. `phase-aware` requests each
phase×station separately through `TauPyModel.get_ray_paths_geo()`. Each record
contains requested/returned phase, arrival time, TauP model, `resample`,
ray-parameter tolerance, geographic sample count, maximum sampled depth, and
a Cartesian chord-sum `raypath_length_km` with status
`taup_raypath_polyline_estimate`.

The CMB-near field is a maximum-sampled-depth proxy with configurable
`--cmb-near-depth-tolerance-km` (default 25 km); it is not a physical CMB
intersection. All TauP records carry `boundary_time_use=forbidden`.

Strict mode is the default: any missing requested phase×station pair aborts
the entire request after listing all missing pairs. With
`--allow-partial-phase-coverage`, available requested paths remain and
`phase_inventory` records requested, provided, missing and a no-substitution
warning in `candidates.json`, `geometry_audit.json`, and `report.md`.

## 6. Center/gamma search and canonical geometry

The planner evaluates a deterministic coarse grid, local refinement, then
final refinement. Defaults are latitude/longitude/gamma coarse steps 10°/10°/
15°, local 2°/2°/3°, final 0.5°/0.5°/0.5°. Defaults search latitude −90..90,
longitude −180..180 and gamma 0..360. Pole representations are canonicalized
to avoid duplicate physical orientations. Results are ordered by descending
score then center latitude, longitude and gamma; at most five unique feasible
candidates are returned.

AB and AC meet on the xi-constant shared interface. C1 and C2 are its physical
endpoints; external faces are distinct absorbing-boundary candidates. Internal
interface proximity is a warning, while exact external-boundary/endpoint source
or receiver placement is rejected. Points are classified as central chunk,
supported-left chunk, shared interface, endpoint/external boundary, or outside.
If no candidate is feasible, all output files are still written with a
rejection summary and a Par_file fragment that says no feasible candidate.

## 7. Boundary time and NEX/MPI advice

For a feasible candidate, an optional `--boundary-speed-upper-km-s` yields a
sampled surface-arc source→boundary→station proxy. It is always
`heuristic_not_conservative`, `hard_constraint_used=false`, and advisory.
`analysis_end_s` uses `--target-energy-end-s` when present, otherwise the end
of `--analysis-window`; its reported margin is not a hard pass/fail. Without a
feasible candidate, boundary status is `unavailable`; without speed, seconds
are null. TauP does not enter this calculation.

Default NEX is 96×96. The rank relationship is
`total_ranks = 2*NPROC_XI*NPROC_ETA`. Compatibility also depends on current
Par_file physics flags. NEX=96 with total ranks 2, 8, or 12 is labelled
`project_validated`; other mathematically compatible choices are only
`mathematically_compatible_not_project_validated`. Lateral work is a simple
per-rank proxy, not a runtime prediction.

## 8. Outputs and workflow

Every successful run writes: `candidates.json`, `candidates.csv`,
`recommended_Par_file.inc`, `geometry_audit.json`, `boundary_time_audit.json`,
`report.md`, `map.png`, and `run_manifest.json`. Check patch provenance,
candidate source/station classes and margins, `path_audits`, `phase_inventory`,
TauP metadata, boundary status, NEX/MPI labels, warnings and rejection reasons
before copying the Par_file fragment manually.

Recommended workflow: prepare inputs; perform geometry-only screening; perform
phase-aware review where available; choose and manually review a candidate;
copy the fragment into a separately managed SPECFEM Par_file; then independently
run mesher/database, inspect C1/C2 and Stacey roles, run solver, and validate
waveforms and external returns.

## 9. FAQ and limits

- **Output already exists:** choose a new path; overwrite is deliberately
  refused.
- **Patch hash mismatch:** stop and verify the project manifest, SPECFEM root,
  and applied accepted patch; do not bypass the check.
- **Missing dependency or TauP phase:** install nothing automatically; strict
  mode fails, partial mode reports only available requested paths.
- **All candidates rejected:** read `rejection_summary`; outputs remain useful.
- **Date line:** map paths are split at ±180°; Cartesian length is unaffected.
- **Target YAML error:** use only the strict keys/types above.
- **Phase-aware is slower or differs from geometry-only:** it samples TauP
  ray paths rather than a surface great circle; deterministic ranking is not
  random.
- **Boundary time unavailable or too early:** it is not production-safe;
  perform a separate waveform/boundary-return assessment.
- **MPI option not project-validated:** it is only mathematically compatible.

## 10. Current validation

Synthetic AB→AC Pdiff/Sdiff and a rotated date-line case passed; the fixture is
not Kim/Song input. The complete package suite has 13 passing tests. Resample
length differences are Pdiff 14.7813 km (0.130094%) and Sdiff 8.6426 km
(0.076131%), so sampling stability is `indeterminate`. The current status is
`boundary_time_production_safe=false` and
`canonical_geometry_planning_validated__waveform_and_boundary_production_validation_required`.
