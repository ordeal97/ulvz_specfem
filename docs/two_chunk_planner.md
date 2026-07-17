# Canonical two-chunk simulation planner

`packages/two_chunk_planner/` is a read-only planning package for the current
ULVZ project's accepted two-chunk configuration. It is separate from
`ulvz_model_postprocess`, because the latter is a `DATABASES_MPI`
post-processing package while the planner audits inputs before meshing.

## Supported scope

The planner can recommend only:

- `NCHUNKS=2`;
- `ANGULAR_WIDTH_XI_IN_DEGREES=90` and `ANGULAR_WIDTH_ETA_IN_DEGREES=90`;
- chunk 1 as central AB and chunk 2 as supported-left AC;
- one system-wide center and `GAMMA_ROTATION_AZIMUTH`;
- candidate MPI decompositions with total ranks
  `2*NPROC_XI*NPROC_ETA`.

It verifies that `create_chunk_buffers.f90` has the accepted candidate hash in
the project patch manifest before producing a runnable recommendation. It does
not apply that patch. Non-90° widths, rectangular chunks, other attachment
sides, independent orientations, arbitrary two-chunk topology, and multi-chunk
configuration are rejected or absent from the interface.

`canonical_90deg_fixture_ready=true`; `general_two_chunk_mode_classification=B`.

## Inputs and modes

Provide a current-format `CMTSOLUTION` or source latitude/longitude/depth, a
current-format `STATIONS` or CSV, and at least requested phases, an analysis
window, or a target energy end time. The default mode is `geometry-only`: it
uses source–station great-circle corridors. `phase-aware` is explicit and uses
`TauPyModel.get_ray_paths_geo()` when the optional ObsPy dependencies can
provide geographic ray samples.

Requested phase–station pairs are globally validated before search. Missing
TauP geographic paths stop strict mode; `--allow-partial-phase-coverage`
continues only with explicit requested/provided/missing inventory in
`candidates.json`, `geometry_audit.json`, and `report.md`; it never substitutes
another phase. Invalid TauP phase syntax is also recorded as a missing request.
In particular, phase-only input does not define a waveform analysis end time:
the boundary-time margin is `unavailable` until the user supplies an end time.

`target_region` is optional and adds an extra containment constraint. It never
defaults to a circle. Its strict YAML types are `circle`, `polygon`, and
`corridor`; all circle radii and corridor half widths are km. Polygon and
corridor points are named geographic coordinates and are handled across ±180°.

## Geometry, optimization, and resources

The implementation follows `euler_angles.f90`, `chunk_map` and the accepted
two-chunk endpoint mapping. It uses local cubed-sphere faces and spherical arcs
to classify points, construct AB–AC, C1/C2 and outer faces. It does not use a
latitude/longitude rectangle approximation. Geometry quantities, sampled path
coverage and sampled target containment retain their individual method/status
labels in the audit JSON.

The search is deterministic: a global coarse center/gamma grid, fixed local
refinement, stable polar/domain deduplication, then score ordering by score and
coordinates. The report records generated, deduplicated, evaluated, feasible
and rejected counts. At most five nonduplicate feasible candidates are emitted;
fewer are returned when necessary, and no-feasible-candidate cases still write
all audits and a rejection summary.

Hard constraints cover canonical geometry/patch provenance, in-domain
source/stations, no exact endpoint/external-boundary placement, required path
coverage, optional target containment, and current Par_file NEX/MPI rules.
The scoring audit exposes coverage, boundary margin, C1/C2 margin, lateral work
proxy, weights and total score. NEX=96 is the sole default recommendation.
Use `--weights packages/two_chunk_planner/examples/weights.yaml` to replace the
strict `coverage`, `external_margin`, `endpoint_margin`, and `cost` weights.
Ranks 2, 8 and 12 with NEX=96 are labeled `project_validated`; other compatible
choices are only `mathematically_compatible_not_project_validated`.

## TauP length and boundary risk

For each geographic TauP ray path, planner converts sampled latitude,
longitude and depth to 3-D Cartesian points and sums adjacent chord lengths.
This output is strictly labelled `taup_raypath_polyline_estimate` and records
requested/returned phase, arrival, TauP model, resampling, ray-parameter
tolerance, sample count, coordinate/depth validation, maximum sampled depth
and a configurable maximum-depth CMB-near proxy. The proxy records its depth
tolerance, samples, and approximation label; it is not a real CMB intersection
or boundary calculation. Every TauP record has `boundary_time_use=forbidden`.
It is useful for phase coverage and propagation-length reporting only.

TauP does not model arbitrary regional external boundary reflections. The v1
boundary-time report samples only the surface traces of external boundaries and
evaluates source→boundary→receiver distances divided by an optional user
velocity upper bound. Every such seconds value is
`heuristic_not_conservative`, is advisory only, and is never a hard reject.
It must not be interpreted as a full 3-D minimization over lateral absorbing
surfaces or as a waveform validation. If an analysis-window end or target
energy end is supplied, `boundary_time_audit.json` reports its signed advisory
margin; `hard_constraint_used=false` and
`boundary_time_production_safe=false` remain unchanged.

## Outputs and use

`plan` refuses to overwrite its output directory and writes:

- `candidates.json` and `candidates.csv`;
- `recommended_Par_file.inc`;
- `geometry_audit.json` and `boundary_time_audit.json`;
- `map.png`, `report.md`, and `run_manifest.json`.

The map draws external boundaries, AB–AC, C1/C2, source, stations, sampled
path corridors, an optional target boundary/centerline, and the source-nearest
sampled external-boundary point. It splits paths at the date line rather than
drawing a false map-wide longitude chord.

Review the proposed fragment, run the existing input audit, mesher/database
checks, C1/C2 and Stacey checks, and waveform/return-time validation separately.
The planner is not evidence that a candidate has production waveform accuracy.

## Phase-aware runtime acceptance

`results/two_chunk_planner_phase_aware_acceptance_20260717T085352Z/` is a
real, no-solver acceptance with Python 3.11.15, NumPy 2.4.6, ObsPy 1.5.0,
geographiclib 2.1 and `HAS_GEOGRAPHICLIB=True`. Its synthetic (not Kim/Song)
source 0°/0°/50 km and receiver 0°/−125° are actually classified AB central
and AC supported-left. Strict `prem` Pdiff/Sdiff runs return geographic paths;
resample=false/true lengths are retained without inventing a convergence
threshold. The sampling conclusion is therefore `indeterminate`, while the
date-line rotation preserves arrivals/Cartesian lengths and splits both path
plots. Geometry-only and phase-aware results use their documented path types
and repeat deterministically. This validates canonical geometry planning, not
waveform accuracy or production boundary-return safety:
`canonical_geometry_planning_validated__waveform_and_boundary_production_validation_required`.
