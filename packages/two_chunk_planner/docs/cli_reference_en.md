<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# `two-chunk-planner plan` CLI reference

Version 0.2.1 — GPL-3.0-or-later. This is the complete parameter-selection
reference for the standalone canonical two-chunk planner. It documents the
current parser, not a separate SPECFEM workflow: the planner neither changes
nor verifies SPECFEM source, a patch, meshing, databases, Stacey boundaries or
waveforms. The parser inventory is generated in
[`generated/cli_options.json`](generated/cli_options.json) and checked against
both language editions.

Use `two-chunk-planner --help` for the top-level command and
`two-chunk-planner plan --help` for the parser synopsis. All documented options
have no short form. The installed command and the repository invocation below
use exactly the same parser.

~~~bash
PYTHONPATH=packages/two_chunk_planner/src /usr/bin/python3 -m two_chunk_planner plan --help
~~~

## Read this first

The planner has 35 `plan` options. `--output` is the only parser-required
option. Runtime validation also requires exactly one source form
(`--cmtsolution` or `--source`), exactly one station form (`--stations` or
`--stations-csv`), and at least one of `--phases`, `--analysis-window`, or
`--target-energy-end-s`.

There is **no** CLI option for chunk width, chunk topology, a plotting switch,
an internal diagnostic switch, or NumPy batch size. The topology is always two
90°×90° chunks (AB central plus AC supported-left); `map.png` and `globe.png`
are written automatically; and the internal NumPy batch implementation needs
no user option.

There is also no user-settable hard outer-boundary or C1/C2 safety-distance
threshold. Those margins are calculated for containment audits and score
components; `--weights` can change their ranking weight, not turn them into a
new hard constraint.

### Minimal runnable command

This inexpensive geometry-only example uses sampled surface great circles. It
is suitable for an input-format and output-directory check, not phase science.

~~~bash
D=/path/to/DATA
OUT=/path/to/new_geometry_plan

two-chunk-planner plan \
  --cmtsolution "$D/CMTSOLUTION" \
  --stations "$D/STATIONS" \
  --analysis-window 0 600 \
  --output "$OUT"
~~~

### Recommended phase-aware command

Use this when phase-path coverage is part of the scientific planning question.
There must be no space after a shell continuation backslash.

~~~bash
D=/path/to/DATA
OUT=/path/to/new_phase_plan

PYTHONPATH=packages/two_chunk_planner/src \
/usr/bin/python3 -m two_chunk_planner plan \
  --cmtsolution "$D/CMTSOLUTION" \
  --stations "$D/STATIONS" \
  --par-file "$D/Par_file" \
  --path-mode phase-aware \
  --phases S,Sdiff \
  --taup-model prem \
  --taup-resample \
  --analysis-window 0 1600 \
  --output "$OUT"
~~~

### Common combinations

- Add `--allow-partial-phase-coverage` only when it is scientifically
  acceptable to continue after explicitly recording missing station–phase
  pairs. It never substitutes S for missing Sdiff.
- Add `--target-region target.yaml` when the two chunks must also contain a
  specified circle, polygon, or corridor.
- Add `--par-file "$D/Par_file"` to read ELLIPTICITY and resource-compatibility
  context; add `--nex` or `--available-ranks` only to compare alternatives.
- Narrow the latitude, longitude, and gamma ranges before reducing search
  steps. Smaller steps and broader ranges can greatly increase runtime.

### Defaults usually left unchanged

Most users should retain the default `prem` TauP model, full path coverage
(`1.0`), default score weights, canonical geometry, and the coarse/local/final
steps. Change them only for a documented scientific or computational reason.
NEX/NPROC values do not change the number of orientation candidates.

## 1. Input files

Exactly one source option and exactly one station option are required.

### `--cmtsolution`

- **Purpose:** reads the event source from a SPECFEM CMTSOLUTION and supplies
  source position/depth to path construction and every candidate audit.
- **Required:** conditionally required; provide this or `--source`, not both.
- **Values:** readable CMTSOLUTION path with a PDE header and 12 labelled
  records; source latitude/longitude are degrees and depth is km.
- **Default:** none; planning fails if neither source form is supplied.
- **When to use:** use for an existing SPECFEM event. Do not use when testing a
  synthetic source that is more conveniently supplied with `--source`.
- **Relations:** mutually exclusive with `--source`; the source affects TauP
  paths in `phase-aware` mode and geometry paths in `geometry-only` mode.
- **Output effect:** writes parsed source provenance to `run_manifest.json` and
  changes feasibility, score, paths, figures, and all audits.
- **Example:** `--cmtsolution "$D/CMTSOLUTION"`.
- **Notes:** malformed fields, invalid coordinates, negative depth, or a zero
  moment tensor stop the run; this option does not verify the event file against
  a solver setup.

### `--source`

- **Purpose:** supplies a source directly without parsing CMTSOLUTION.
- **Required:** conditionally required; provide this or `--cmtsolution`, not
  both.
- **Values:** three finite numbers: `LAT LON DEPTH_KM`; latitude/longitude are
  geographic degrees and depth is non-negative km.
- **Default:** none; planning fails if neither source form is supplied.
- **When to use:** use for a small synthetic or sensitivity test. Do not use it
  when CMTSOLUTION provenance is required in the plan output.
- **Relations:** mutually exclusive with `--cmtsolution`; otherwise behaves as
  the same source input to paths and geometry.
- **Output effect:** changes source-dependent coverage, score, figures, and
  stores the supplied values in `run_manifest.json`.
- **Example:** `--source 0 -125 50`.
- **Notes:** it does not create a CMTSOLUTION file and does not infer a moment
  tensor or origin time.

### `--stations`

- **Purpose:** reads receivers from a SPECFEM whitespace-delimited STATIONS
  file.
- **Required:** conditionally required; provide this or `--stations-csv`, not
  both.
- **Values:** readable STATIONS path with six whitespace-separated fields per
  station; station coordinates are geographic degrees.
- **Default:** none; planning fails if neither station form is supplied.
- **When to use:** use the SPECFEM-ready station list for a simulation case.
  Do not combine it with `--stations-csv`.
- **Relations:** mutually exclusive with `--stations-csv`; station count
  multiplies phase requests and path evaluations.
- **Output effect:** changes station containment, paths, score, figures,
  candidate feasibility, and station provenance in `run_manifest.json`.
- **Example:** `--stations "$D/STATIONS"`.
- **Notes:** duplicate network/station IDs, invalid coordinates, malformed
  lines, or an empty file stop planning.

### `--stations-csv`

- **Purpose:** reads receivers from a portable CSV instead of SPECFEM STATIONS.
- **Required:** conditionally required; provide this or `--stations`, not both.
- **Values:** CSV with `network,station,latitude_deg,longitude_deg`; elevation
  and burial columns may be present.
- **Default:** none; planning fails if neither station form is supplied.
- **When to use:** use for pre-SPECFEM screening or externally managed station
  inventories. Do not use it together with `--stations`.
- **Relations:** mutually exclusive with `--stations`; it provides the same
  downstream station objects.
- **Output effect:** changes paths, containment, score, figures, and the
  station list stored in the manifest.
- **Example:** `--stations-csv stations.csv`.
- **Notes:** duplicate network/station pairs or missing required columns stop
  the run; CSV does not update a SPECFEM STATIONS file.

## 2. Paths and phases

`geometry-only` samples one surface great-circle path per station. `phase-aware`
queries TauP separately for every requested station–phase pair. Supplying
`--phases` alone does not switch the mode; use `--path-mode phase-aware`.

### `--path-mode`

- **Purpose:** selects the path construction used by coverage evaluation.
- **Required:** optional.
- **Values:** exactly `geometry-only` or `phase-aware`.
- **Default:** `geometry-only`.
- **When to use:** use `geometry-only` for fast geometric screening; use
  `phase-aware` when the requested TauP phase paths must be covered.
- **Relations:** `--path-samples` applies only to geometry-only; TauP options
  affect phase-aware requests. `--phases` does not implicitly change this mode.
- **Output effect:** both modes write the same nine output files, but
  phase-aware outputs include TauP path/phase inventory and geometry-only
  outputs contain sampled surface paths with null TauP settings.
- **Example:** `--path-mode phase-aware`.
- **Notes:** phase-aware requires the optional ObsPy/TauP dependency and may be
  much slower before orientation search because it requests each pair once.

### `--phases`

- **Purpose:** names the TauP phases to request in phase-aware mode.
- **Required:** optional in argparse, but at least one of this, `--analysis-window`,
  or `--target-energy-end-s` is required at runtime.
- **Values:** comma-separated phase names without spaces in the semantic list,
  for example `S,Sdiff` or `Pdiff,Sdiff`.
- **Default:** no requested phases.
- **When to use:** use with `--path-mode phase-aware`; omit for a purely
  geometry-only run driven by an analysis-window or target end.
- **Relations:** each name is requested for every station; strict/partial
  handling is controlled by `--allow-partial-phase-coverage`.
- **Output effect:** phase-aware runs write requested/provided/missing pairs and
  returned TauP paths to JSON; it changes coverage checks, score, and runtime.
- **Example:** `--phases S,Sdiff`.
- **Notes:** comma separation is required; `S, Sdiff` is accepted after trimming
  whitespace, but shell quoting is safer for unusual names. TauP never silently
  substitutes one requested phase for another.

### `--path-samples`

- **Purpose:** sets the number of points used for each geometry-only surface
  great-circle path.
- **Required:** optional; meaningful only in geometry-only mode.
- **Values:** integer sample count; default `121`.
- **Default:** 121 points per station path.
- **When to use:** increase it only when a geometry-only containment screen
  needs finer path sampling; leave it unchanged for phase-aware paths.
- **Relations:** ignored for TauP path generation; it is independent of
  `--taup-resample`.
- **Output effect:** changes geometry-only `phase_paths`, discrete coverage
  evaluation, `map.png`/`globe.png`, and per-candidate cost.
- **Example:** `--path-samples 241`.
- **Notes:** it does not improve physical waveform accuracy and does not alter
  TauP paths; more points increase geometry-only search work.

### `--taup-model`

- **Purpose:** selects the TauP velocity model passed to `TauPyModel`.
- **Required:** optional; meaningful only in phase-aware mode.
- **Values:** a TauP model name available in the installed ObsPy environment.
- **Default:** `prem`.
- **When to use:** retain `prem` for the documented workflow; use another model
  only when its phase predictions are the intended planning basis.
- **Relations:** combines with `--phases`, source/stations, `--taup-resample`,
  and `--ray-param-tol`; it is recorded only for phase-aware runs.
- **Output effect:** can change returned/missing phases, path geometry,
  coverage, score, phase inventory, figures, and runtime.
- **Example:** `--taup-model prem`.
- **Notes:** an unavailable model or missing requested arrival is a strict-mode
  error unless partial coverage is explicitly allowed.

### `--taup-resample`

- **Purpose:** asks TauP to return a resampled geographic ray-path polyline.
- **Required:** optional boolean flag; meaningful only in phase-aware mode.
- **Values:** present means true; absent means false.
- **Default:** false.
- **When to use:** use when the program-defined TauP resampling is desired for
  a denser or regularized returned path representation; otherwise retain TauP's
  unresampled output.
- **Relations:** passed with `--taup-model`, `--phases`, and `--ray-param-tol`;
  unrelated to geometry-only `--path-samples`.
- **Output effect:** records `resample` and path-point metadata, may change
  discrete path coverage and figures, and can change TauP/pre-search runtime.
- **Example:** `--taup-resample`.
- **Notes:** it does not select a different requested phase or replace the
  physical model; it changes the sampled representation used by the planner,
  not waveform accuracy certification.

### `--ray-param-tol`

- **Purpose:** forwards a ray-parameter tolerance to TauP geographic path
  requests.
- **Required:** optional; meaningful only in phase-aware mode.
- **Values:** floating-point tolerance; default `1e-06`.
- **Default:** `1e-06`.
- **When to use:** retain the default unless TauP behaviour must be studied for
  a documented numerical reason.
- **Relations:** used with `--taup-model`, `--phases`, and `--taup-resample`.
- **Output effect:** is recorded in path metadata; it can affect returned paths
  and therefore coverage only if TauP's result changes.
- **Example:** `--ray-param-tol 1e-6`.
- **Notes:** it is not a geometric boundary tolerance and should not be tuned
  to force a desired phase arrival.

### `--cmb-near-depth-tolerance-km`

- **Purpose:** sets the depth band around a TauP path's maximum sampled depth
  used for the CMB-near proxy stored in each path record.
- **Required:** optional; meaningful only in phase-aware mode.
- **Values:** non-negative floating-point km; default `25.0`.
- **Default:** 25 km below the maximum sampled-depth reference.
- **When to use:** change only when reviewing how broad the descriptive
  CMB-near sample segment should be.
- **Relations:** operates after TauP path retrieval and does not change the
  requested phase, TauP model, or boundary-time calculation.
- **Output effect:** changes `cmb_near_proxy` metadata in structured paths; it
  does not alter the path points, feasibility, score, or search range.
- **Example:** `--cmb-near-depth-tolerance-km 20`.
- **Notes:** this is a sampled maximum-depth proxy, not a physical CMB
  intersection or an ULVZ crossing calculation.

### `--allow-partial-phase-coverage`

- **Purpose:** permits phase-aware planning to continue after TauP cannot
  return some requested station–phase pairs.
- **Required:** optional boolean flag; meaningful only with phase-aware paths.
- **Values:** present means partial mode; absent means strict mode.
- **Default:** false (strict mode).
- **When to use:** use only when it is scientifically acceptable to plan from
  the subset of returned requested paths and separately inspect missing pairs.
- **Relations:** applies to failures from `--phases`/`--taup-model` requests;
  it does not lower `--minimum-path-coverage` and does not alter target checks.
- **Output effect:** partial mode writes missing-pair inventory and a warning,
  then evaluates only returned requested paths; strict mode stops before output.
- **Example:** `--allow-partial-phase-coverage`.
- **Notes:** a missing Sdiff remains missing; S is never substituted for it.
  Partial mode is not a claim that omitted paths are covered.

## 3. Time, target region, and coverage constraints

### `--analysis-window`

- **Purpose:** supplies the analysis start/end labels and its end for advisory
  boundary-time comparison.
- **Required:** optional, but can satisfy the runtime requirement for a time or
  phase input.
- **Values:** two floating-point seconds: `START_S END_S`.
- **Default:** none.
- **When to use:** provide the signal-analysis interval for ordinary planning
  runs, including phase-aware Event-style cases.
- **Relations:** `--target-energy-end-s` overrides its end for the advisory
  comparison; it is independent of `--phases` and path sampling.
- **Output effect:** writes `analysis_window` and `analysis_end_s` to
  `boundary_time_audit.json`; it does not change candidate generation or score.
- **Example:** `--analysis-window 0 1600`.
- **Notes:** units are seconds. It does **not** truncate TauP or geometry paths,
  filter arrivals, or prove that 1600 s is free of boundary returns.

### `--target-energy-end-s`

- **Purpose:** supplies a separate end time for advisory boundary-time output.
- **Required:** optional, but can satisfy the runtime requirement for a time or
  phase input.
- **Values:** one floating-point value in seconds.
- **Default:** none.
- **When to use:** use when the scientifically relevant signal-energy end is
  different from the end of `--analysis-window`.
- **Relations:** overrides the analysis-window end only in boundary-time output;
  it does not alter paths, coverage, score, or search.
- **Output effect:** changes `analysis_end_s` and advisory margins in
  `boundary_time_audit.json`.
- **Example:** `--target-energy-end-s 1850`.
- **Notes:** this value is not a hard boundary safety constraint and does not
  crop waveform or path data.

### `--target-region`

- **Purpose:** adds a geographic target that must be fully contained by the
  chosen two-chunk domain.
- **Required:** optional.
- **Values:** path to strict YAML defining one `circle`, `polygon`, or
  `corridor`; coordinates are degrees and widths/radii are km.
- **Default:** no target-region containment constraint.
- **When to use:** use when an ULVZ, study area, or required corridor must fit
  in the two chunks. Omit it when only source/stations/paths matter.
- **Relations:** combines with all candidate geometry checks; its samples must
  have coverage 1.0 independently of `--minimum-path-coverage`.
- **Output effect:** can reject candidates, change score/margins, add a target
  audit, and draw the target in both figures.
- **Example:** `--target-region target_circle.yaml`.
- **Notes:** unknown YAML fields, invalid geometry, or incomplete containment
  fail the run/candidate; target sampling is a documented heuristic audit and
  adds per-candidate work.

### `--weights`

- **Purpose:** replaces the default score weights for coverage, external margin,
  endpoint margin, and cost.
- **Required:** optional.
- **Values:** strict YAML mapping with only `coverage`, `external_margin`,
  `endpoint_margin`, and `cost`; values are non-negative and at least one must
  be positive.
- **Default:** built-in weights 0.35, 0.30, 0.20, and 0.15 respectively.
- **When to use:** use only for a transparent, documented change in ranking
  priorities after confirming that hard feasibility requirements remain suitable.
- **Relations:** replaces score weights, but does not replace source/station
  containment, target containment, or `--minimum-path-coverage`.
- **Output effect:** can reorder feasible candidates and changes score
  components in JSON/CSV; it does not change generated orientation points.
- **Example:** `--weights weights.yaml`.
- **Notes:** it is not a way to make an infeasible candidate feasible; record
  the scientific rationale for non-default weights.

### `--minimum-path-coverage`

- **Purpose:** sets the minimum contained fraction required for each evaluated
  path.
- **Required:** optional.
- **Values:** floating point strictly in `(0,1]`; default `1.0`.
- **Default:** every sampled point of every evaluated path must be inside.
- **When to use:** retain 1.0 for full path containment; lower only when a
  partial-path scientific criterion is explicitly justified.
- **Relations:** applies to geometry-only and returned phase-aware paths; it is
  distinct from `--allow-partial-phase-coverage`, which concerns missing paths.
- **Output effect:** changes candidate feasibility, rejection reasons, score,
  and path audits; it does not remove any path points.
- **Example:** `--minimum-path-coverage 0.9`.
- **Notes:** values outside the interval stop planning. A lower threshold does
  not relax target-region full containment or replace missing TauP arrivals.

### `--boundary-speed-upper-km-s`

- **Purpose:** supplies an upper speed for an advisory surface-arc boundary
  return-time proxy.
- **Required:** optional.
- **Values:** positive floating-point km/s.
- **Default:** none; no earliest-return seconds are calculated.
- **When to use:** use only for an explicitly labelled preliminary comparison
  with an analysis end time.
- **Relations:** uses `--analysis-window` or `--target-energy-end-s` as the
  comparison end; TauP paths are deliberately not used for this calculation.
- **Output effect:** fills heuristic return seconds/margins in
  `boundary_time_audit.json`; it does not affect search, score, paths, or plots.
- **Example:** `--boundary-speed-upper-km-s 14`.
- **Notes:** the result is `heuristic_not_conservative`, not a three-dimensional
  absorbing-boundary proof and not a production safety criterion.

## 4. Fixed geometry and orientation search

Chunk width and topology are fixed: two 90°×90° chunks, AB central plus AC
supported-left. The search controls only the geographic center and gamma
rotation. It runs deterministic coarse, local, and final stages with stable
deduplication and tie-breaking. Narrower ranges reduce candidates; smaller
steps increase them, especially in the coarse stage.

### `--latitude-range`

- **Purpose:** limits candidate center latitudes.
- **Required:** optional.
- **Values:** `MIN,MAX` comma-separated degrees; default `-90,90`.
- **Default:** searches the full latitude span.
- **When to use:** restrict it to a scientifically plausible geographic band to
  reduce search work.
- **Relations:** works with longitude/gamma ranges and all three stage steps;
  range endpoints must each produce exactly two values overall.
- **Output effect:** changes the candidate set, runtime, feasible ranking, and
  selected center; it does not change chunk size.
- **Example:** `--latitude-range -20,20`.
- **Notes:** polar coordinate equivalents are canonicalized deterministically;
  use physical constraints, not convenience, to exclude regions.

### `--longitude-range`

- **Purpose:** limits candidate center longitudes.
- **Required:** optional.
- **Values:** `MIN,MAX` comma-separated degrees; default `-180,180`.
- **Default:** searches the full longitude span.
- **When to use:** restrict it around the study region when justified.
- **Relations:** combines with latitude/gamma ranges and stage steps; longitudes
  are normalized during deterministic canonicalization.
- **Output effect:** changes candidate count, runtime, chosen orientation, and
  all geometry-dependent outputs.
- **Example:** `--longitude-range 120,180`.
- **Notes:** a range does not alter longitude conventions in input files or the
  fixed 90° chunk widths.

### `--gamma-range`

- **Purpose:** limits the whole-system gamma rotation of the fixed two-chunk
  arrangement.
- **Required:** optional.
- **Values:** `MIN,MAX` comma-separated degrees; default `0,360`.
- **Default:** searches all gamma orientations.
- **When to use:** restrict it only when a physical orientation prior exists.
- **Relations:** combines with center ranges; a full 360° interval is treated as
  rotationally periodic during canonicalization.
- **Output effect:** changes candidate count, layout orientation, path margins,
  candidate rank, and figures.
- **Example:** `--gamma-range 0,90`.
- **Notes:** gamma is not a second chunk position; AC has no independent
  translation or rotation.

### `--coarse-latitude-step`

- **Purpose:** sets first-stage latitude grid spacing.
- **Required:** optional.
- **Values:** floating-point degrees; default `10.0`.
- **Default:** 10° coarse latitude spacing.
- **When to use:** reduce only when the coarse global search needs more detail;
  increase only with care because it can miss a better region before refinement.
- **Relations:** combines multiplicatively with coarse longitude/gamma steps;
  local/final steps refine keepers rather than replace coarse coverage.
- **Output effect:** strongly affects generated orientation count, search time,
  and potentially the final selected candidate.
- **Example:** `--coarse-latitude-step 5`.
- **Notes:** use the same scientific search scope when comparing runs; this is a
  resolution control, not a graphics setting.

### `--coarse-longitude-step`

- **Purpose:** sets first-stage longitude grid spacing.
- **Required:** optional.
- **Values:** floating-point degrees; default `10.0`.
- **Default:** 10° coarse longitude spacing.
- **When to use:** change with the other coarse steps only when a denser or
  cheaper first-stage orientation grid is intended.
- **Relations:** multiplies with coarse latitude/gamma counts; later stages use
  retained coarse keepers.
- **Output effect:** changes coarse candidate count, runtime, and possibly the
  final orientation.
- **Example:** `--coarse-longitude-step 5`.
- **Notes:** a smaller value can cause a large runtime increase over broad
  longitude ranges.

### `--coarse-gamma-step`

- **Purpose:** sets first-stage gamma grid spacing.
- **Required:** optional.
- **Values:** floating-point degrees; default `15.0`.
- **Default:** 15° coarse gamma spacing.
- **When to use:** use a smaller value only when coarse orientation sampling
  must be denser across a scientifically justified gamma range.
- **Relations:** multiplies with both other coarse dimensions; gamma remains
  periodic/canonicalized.
- **Output effect:** changes coarse candidate count, runtime, and potentially
  which local regions receive refinement.
- **Example:** `--coarse-gamma-step 10`.
- **Notes:** it does not rotate a single chunk independently.

### `--local-latitude-step`

- **Purpose:** sets latitude spacing for local refinement around coarse keepers.
- **Required:** optional.
- **Values:** floating-point degrees; default `2.0`.
- **Default:** 2° local latitude spacing.
- **When to use:** change when a documented local-resolution trade-off is
  needed after retaining the intended coarse search.
- **Relations:** used with local longitude/gamma steps in a fixed neighborhood
  around retained coarse candidates.
- **Output effect:** changes local candidates, runtime, and possible final rank;
  it does not broaden the initial global range.
- **Example:** `--local-latitude-step 1`.
- **Notes:** decreasing it increases local evaluation cost and should be paired
  with enough coarse coverage to find the relevant basin.

### `--local-longitude-step`

- **Purpose:** sets longitude spacing for local refinement around coarse keepers.
- **Required:** optional.
- **Values:** floating-point degrees; default `2.0`.
- **Default:** 2° local longitude spacing.
- **When to use:** change only for an intended local-resolution study.
- **Relations:** used with local latitude/gamma steps and bounded by the three
  search ranges.
- **Output effect:** changes local candidate count, runtime, and potentially the
  candidate passed to final refinement.
- **Example:** `--local-longitude-step 1`.
- **Notes:** it is not a station or map longitude-resolution setting.

### `--local-gamma-step`

- **Purpose:** sets gamma spacing for local refinement around coarse keepers.
- **Required:** optional.
- **Values:** floating-point degrees; default `3.0`.
- **Default:** 3° local gamma spacing.
- **When to use:** alter only with a documented reason to resolve local layout
  orientation more finely.
- **Relations:** used with local latitude/longitude steps; limited by
  `--gamma-range` when that range is not a full circle.
- **Output effect:** changes local orientation evaluations, runtime, and
  possible final candidate.
- **Example:** `--local-gamma-step 1`.
- **Notes:** this controls search resolution, not the physical width or topology
  of the chunks.

### `--final-latitude-step`

- **Purpose:** sets the finest latitude spacing around top local keepers.
- **Required:** optional.
- **Values:** floating-point degrees; default `0.5`.
- **Default:** 0.5° final latitude spacing.
- **When to use:** use a smaller value only for a required final orientation
  precision after assessing the runtime cost.
- **Relations:** works with final longitude/gamma steps in a fixed small
  neighborhood around the top local candidates.
- **Output effect:** changes final candidate evaluations, ranking, and selected
  center, without changing the global search range.
- **Example:** `--final-latitude-step 0.25`.
- **Notes:** tighter final steps can still add substantial work when many paths
  are evaluated per orientation.

### `--final-longitude-step`

- **Purpose:** sets the finest longitude spacing around top local keepers.
- **Required:** optional.
- **Values:** floating-point degrees; default `0.5`.
- **Default:** 0.5° final longitude spacing.
- **When to use:** change only for a justified final center precision.
- **Relations:** used with final latitude/gamma steps and constrained by the
  requested search ranges.
- **Output effect:** changes final candidates, runtime, and potentially the
  selected longitude.
- **Example:** `--final-longitude-step 0.25`.
- **Notes:** it does not change map projection precision or station coordinates.

### `--final-gamma-step`

- **Purpose:** sets the finest gamma spacing around top local keepers.
- **Required:** optional.
- **Values:** floating-point degrees; default `0.5`.
- **Default:** 0.5° final gamma spacing.
- **When to use:** change only when final orientation resolution must be finer.
- **Relations:** used with final latitude/longitude steps; gamma remains a
  canonical periodic orientation.
- **Output effect:** changes final evaluations, runtime, and possibly selected
  gamma and figures.
- **Example:** `--final-gamma-step 0.25`.
- **Notes:** a smaller step is not an approximation mode; it expands the exact
  enumerated final candidate set.

## 5. SPECFEM resource suggestions

These options run after the orientation search. They change resource labels and
the generated Par_file fragment, not the orientation candidate set or phase
path count. `--par-file` may also set ELLIPTICITY for geometric conversion.

### `--par-file`

- **Purpose:** reads an arbitrary external Par_file as read-only planning
  context.
- **Required:** optional.
- **Values:** readable path to a `KEY = VALUE` text file; duplicate keys fail.
- **Default:** bundled planning defaults, labelled `builtin_profile`.
- **When to use:** use the case Par_file when resource suggestions should reflect
  its NEX/NPROC and compatibility branch; omit for a standalone screen.
- **Relations:** reads `ELLIPTICITY`, `NEX_XI`, `NEX_ETA`, `NPROC_XI`,
  `NPROC_ETA`, `SUPPRESS_CRUSTAL_MESH`, and `ADD_4TH_DOUBLING` when present;
  `--nex`/`--available-ranks` override their candidate sources.
- **Output effect:** records Par_file provenance, can change ellipticity-aware
  geometry conversion, and changes resource suggestions/fragment compatibility.
- **Example:** `--par-file "$D/Par_file"`.
- **Notes:** it does not locate a SPECFEM checkout, apply a patch, modify the
  file, verify mesh/solver readiness, or make NEX control orientation runtime.

### `--available-ranks`

- **Purpose:** supplies total MPI-rank counts to enumerate compatible two-chunk
  decompositions.
- **Required:** optional.
- **Values:** comma-separated positive integers, for example `8,12,128`.
- **Default:** uses `2*NPROC_XI*NPROC_ETA` from Par_file when available, else
  profile values `2,8,12`.
- **When to use:** use to compare the rank totals actually available on a
  target system; omit to inherit the documented context.
- **Relations:** combines with `--nex`, Par_file compatibility flags, and
  `--max-compute-cost`; it overrides the Par_file rank-total default.
- **Output effect:** changes `resource_suggestions` and
  `recommended_Par_file.inc`, never orientation candidates or paths.
- **Example:** `--available-ranks 64,128`.
- **Notes:** values are total ranks for both chunks, not ranks per chunk; a
  mathematical suggestion is not necessarily project-validated.

### `--nex`

- **Purpose:** adds one NEX_XIxNEX_ETA mesh-resolution candidate for resource
  compatibility suggestions.
- **Required:** optional and repeatable.
- **Values:** `XIxETA` integers with lowercase or uppercase `x`, for example
  `96x96`; repeat the option for multiple candidates.
- **Default:** Par_file `NEX_XI,NEX_ETA` when available, else profile `96x96`.
- **When to use:** use to compare legal mesh resolutions without changing the
  chosen orientation.
- **Relations:** overrides default NEX source when supplied; combines with
  `--available-ranks`, Par_file physics flags, and `--max-compute-cost`.
- **Output effect:** changes resource suggestions and possibly the recommended
  fragment, but not source/station/path geometry or orientation search time.
- **Example:** `--nex 96x96 --nex 192x96`.
- **Notes:** NEX does not increase orientation candidates or path points. Each
  value must satisfy the selected branch's multiple/divisibility checks.

### `--max-compute-cost`

- **Purpose:** filters resource suggestions using the planner's relative
  lateral-work-per-rank proxy.
- **Required:** optional.
- **Values:** floating-point threshold.
- **Default:** no post-search cost filtering.
- **When to use:** use to hide resource combinations above a documented planning
  proxy threshold; do not use it as a runtime prediction.
- **Relations:** applies after `--nex` and `--available-ranks` enumeration; it
  does not affect score weights or the orientation search.
- **Output effect:** removes resource suggestions and can alter the first
  suggestion copied to `recommended_Par_file.inc`; all geometry outputs remain.
- **Example:** `--max-compute-cost 2304`.
- **Notes:** an empty filtered suggestion list does not make a geometry
  candidate infeasible and does not estimate wall time or memory.

## 6. Output, plotting, and advanced behaviour

### `--output`

- **Purpose:** names the new directory receiving planner products.
- **Required:** required.
- **Values:** a directory path that does not already exist.
- **Default:** none.
- **When to use:** provide a unique run directory for every invocation.
- **Relations:** independent of all scientific controls; output is created only
  after inputs and path preparation succeed.
- **Output effect:** writes `candidates.json`, `candidates.csv`,
  `geometry_audit.json`, `boundary_time_audit.json`, `run_manifest.json`,
  `recommended_Par_file.inc`, `report.md`, `map.png`, and `globe.png`.
- **Example:** `--output plans/event1_phase_aware`.
- **Notes:** an existing directory is deliberately refused rather than
  overwritten. The planner has no `--plot`, `--no-plot`, `--log`, or public
  diagnostic option; capture stdout/stderr externally when a log is needed.

## Common errors and troubleshooting

- **“CMTSOLUTION or --source … is required” / station-form error:** provide one,
  and only one, source and station option.
- **“provide phases, analysis window, or target energy end time”:** add an
  analysis window for a geometry-only screen, or use phase-aware options.
- **TauP missing Sdiff:** first inspect source–station distance and model/phase
  applicability. Use partial coverage only if omitting that pair is acceptable;
  it will remain explicitly missing in output.
- **No feasible candidates:** inspect `candidates.json` rejection summary and
  `geometry_audit.json`; do not change chunk size because it is fixed. Revisit
  scientifically justified ranges, target constraints, station coverage, and
  phase availability.
- **Unexpectedly long run:** first inspect search ranges/coarse steps, station
  count, returned phase paths, path-point count, and target sampling. NEX/NPROC
  changes will not reduce orientation-search work.
- **Boundary-time result seems safe:** treat it only as the labelled
  `heuristic_not_conservative` surface-arc proxy; validate actual boundaries in
  the separate SPECFEM workflow.

## Limits

The planner supports only canonical 90°×90° two-chunk geometry and does not
replace production mesh, topology, boundary-return, solver, or waveform
validation. See the [English user guide](user_guide_en.md), [Chinese user
guide](user_guide_zh.md), and [validation status](validation_status.md).
