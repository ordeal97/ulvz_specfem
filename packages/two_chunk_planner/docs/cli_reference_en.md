<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# `two-chunk-planner plan` CLI reference

Version 0.2.0 — GPL-3.0-or-later. This reference describes the standalone
canonical 90°×90° AB-central/AC-supported-left planner. It has no project-root,
manifest, SPECFEM source, or patch-verification mode. The parser inventory is
generated in [`generated/cli_options.json`](generated/cli_options.json) and is
checked against this page.

## Running modes

**Standalone:** supply source, stations, and phases or a time endpoint. The
bundled profile supplies planning defaults only. **Standalone plus Par_file:**
add `--par-file /any/path/Par_file`; only resource-relevant values are read.
Neither mode verifies a user's SPECFEM source or accepted patch. Use the
separate patch package before production simulations.

~~~bash
two-chunk-planner plan --source 0 0 50 --stations-csv stations.csv \
  --analysis-window 0 1900 --output plan_out
~~~

Every option has no short form. `--output` is required; all other defaults
below are parser defaults. Exactly one source form and exactly one station form
are required. At least one of phases, analysis window, or target-energy end is
required. An existing output directory is always refused.

## 1. Source and station input

### `--cmtsolution`
Short form: none. Type: path. Optional but mutually exclusive with `--source`;
one is required. Reads SPECFEM CMTSOLUTION (PDE header plus labelled records).
Example: `--cmtsolution DATA/CMTSOLUTION`. Invalid/missing fields or a zero
moment tensor stop planning. It supplies source coordinates and provenance.

### `--source`
Short form: none. Type: three floats `LAT LON DEPTH_KM`; no default. Mutually
exclusive with `--cmtsolution`; one is required. Example: `--source 0 -125 50`.
Latitude/depth must be finite and depth non-negative. It bypasses CMTSOLUTION
parsing only; it does not create an input file.

### `--stations`
Short form: none. Type: path; mutually exclusive with `--stations-csv`; one is
required. Example: `--stations DATA/STATIONS`. Reads six whitespace fields per
receiver. Duplicate network/station IDs or malformed numeric coordinates fail.

### `--stations-csv`
Short form: none. Type: path; mutually exclusive with `--stations`; one is
required. Example: `--stations-csv stations.csv`. Required columns are
`network,station,latitude_deg,longitude_deg`; elevation/burial are optional.

## 2. Phase, analysis window, and target end

### `--phases`
Short form: none. Type: comma-separated names; default none. Used only by
`phase-aware`; example `--phases Pdiff,Sdiff`. It requests exactly these TauP
phases—no substitute phase is used. It may be omitted only when a window/end is
provided.

### `--analysis-window`
Short form: none. Type: two floats `START_S END_S`; default none. Example:
`--analysis-window 0 1900`. Its end becomes the advisory boundary-time
comparison endpoint unless `--target-energy-end-s` is supplied.

### `--target-energy-end-s`
Short form: none. Type: float seconds; default none. Example:
`--target-energy-end-s 1900`. Overrides the window end for advisory boundary
margin reporting; it is not a production boundary-safety constraint.

## 3. Path mode

### `--path-mode`
Short form: none. Choices: `geometry-only`, `phase-aware`; default
`geometry-only`. Geometry-only samples a surface great circle; phase-aware
requests TauP geographic ray paths. Example: `--path-mode phase-aware`.

### `--path-samples`
Short form: none. Type: integer; default `121`. Applies to geometry-only
great-circle sampling. Example: `--path-samples 241`. It does not resample
TauP paths and does not establish waveform accuracy.

## 4. TauP and partial coverage

### `--taup-model`
Short form: none. Type: TauP model name; default `prem`; applies to
phase-aware only. Example: `--taup-model prem`. An unavailable model/phase is
an error in strict coverage.

### `--taup-resample`
Short form: none. Boolean flag; default false; phase-aware only. Example:
`--taup-resample`. Records the choice in each path record; length remains the
`taup_raypath_polyline_estimate`.

### `--ray-param-tol`
Short form: none. Type: float; default `1e-06`; phase-aware only. Example:
`--ray-param-tol 1e-6`. It is passed to the TauP path request and recorded in
metadata.

### `--cmb-near-depth-tolerance-km`
Short form: none. Type: float km; default `25.0`; phase-aware only. Example:
`--cmb-near-depth-tolerance-km 20`. Controls the sampled CMB-near proxy, not a
physical interface intersection.

### `--allow-partial-phase-coverage`
Short form: none. Boolean flag; default false (strict). Example:
`--allow-partial-phase-coverage`. Strict mode fails after listing every missing
phase×station pair; partial mode retains only returned requested phases and
adds a no-substitution warning/inventory.

## 5. Target regions

### `--target-region`
Short form: none. Type: strict YAML path; default none. Example:
`--target-region target_circle.yaml`. Supports only circle, polygon, or
corridor schemas. Unknown/missing fields fail; it changes coverage constraints.

## 6. Boundary time

### `--boundary-speed-upper-km-s`
Short form: none. Type: positive float km/s; default none. Example:
`--boundary-speed-upper-km-s 14`. Produces a surface-arc proxy marked
`heuristic_not_conservative`; it is advisory and TauP is forbidden here.

## 7. Center/gamma search and refinement

### `--latitude-range`
Short form: none. Format `MIN,MAX`; default `-90,90`. Example:
`--latitude-range -20,20`. Defines the center-latitude search interval.

### `--longitude-range`
Short form: none. Format `MIN,MAX`; default `-180,180`. Example:
`--longitude-range 120,180`. Defines the center-longitude interval; polar
equivalents are deduplicated deterministically.

### `--gamma-range`
Short form: none. Format `MIN,MAX`; default `0,360`. Example:
`--gamma-range 0,90`. Defines the whole-system gamma search interval.

### `--coarse-latitude-step`
Short form: none. Type: float degrees; default `10.0`. Example:
`--coarse-latitude-step 5`. First-pass latitude grid spacing.

### `--coarse-longitude-step`
Short form: none. Type: float degrees; default `10.0`. Example:
`--coarse-longitude-step 5`. First-pass longitude grid spacing.

### `--coarse-gamma-step`
Short form: none. Type: float degrees; default `15.0`. Example:
`--coarse-gamma-step 10`. First-pass gamma grid spacing.

### `--local-latitude-step`
Short form: none. Type: float degrees; default `2.0`. Example:
`--local-latitude-step 1`. Local refinement latitude spacing.

### `--local-longitude-step`
Short form: none. Type: float degrees; default `2.0`. Example:
`--local-longitude-step 1`. Local refinement longitude spacing.

### `--local-gamma-step`
Short form: none. Type: float degrees; default `3.0`. Example:
`--local-gamma-step 1`. Local refinement gamma spacing.

### `--final-latitude-step`
Short form: none. Type: float degrees; default `0.5`. Example:
`--final-latitude-step 0.25`. Final latitude spacing around top candidates.

### `--final-longitude-step`
Short form: none. Type: float degrees; default `0.5`. Example:
`--final-longitude-step 0.25`. Final longitude spacing around top candidates.

### `--final-gamma-step`
Short form: none. Type: float degrees; default `0.5`. Example:
`--final-gamma-step 0.25`. Final gamma spacing around top candidates.

## 8. Scoring and coverage

### `--weights`
Short form: none. Type: strict YAML path; default none. Example:
`--weights weights.yaml`. Allowed keys are `coverage`, `external_margin`,
`endpoint_margin`, `cost`; all must be non-negative and one positive. It
replaces score weights, not hard constraints.

### `--minimum-path-coverage`
Short form: none. Type: float in `(0,1]`; default `1.0`. Example:
`--minimum-path-coverage 0.9`. Lower values allow partial target/path coverage;
values outside the interval fail.

## 9. NEX, MPI, and cost

### `--available-ranks`
Short form: none. Format: comma-separated total ranks; default uses external
Par_file NPROC if present, otherwise profile `2,8,12`. Example:
`--available-ranks 8,12`. Suggestions label only canonical NEX=96 at 2/8/12
as `project_validated`.

### `--nex`
Short form: none. Format `XIxETA`; repeatable; default uses external Par_file
NEX if present, otherwise profile `96x96`. Example: `--nex 96x96 --nex 192x96`.
Each value is checked against the selected planning physics branch.

### `--max-compute-cost`
Short form: none. Type: float; default none. Example: `--max-compute-cost 2304`.
Filters suggestions by the planner's lateral-work-per-rank proxy; it is not a
runtime forecast.

## 10. Optional Par_file

### `--par-file`
Short form: none. Type: any readable Par_file path; default none. Example:
`--par-file /work/case/DATA/Par_file`. Reads NEX/NPROC and compatibility flags;
it never locates SPECFEM or verifies source/patch status. Omit it to use
profile planning defaults marked `builtin_profile`.

## 11. Output and safety

There is no `--log` option. User-facing errors go to standard error; ordinary
planning is quiet except for generated files. Capture shell stdout/stderr when
an external workflow needs a persistent log.

### `--output`
Short form: none. Type: directory path; required. Example: `--output plan_out`.
Must not exist. On success it receives JSON/CSV audits, Par_file fragment,
report, map, and manifest. Reusing a directory is a deliberate error.

## License and limits

This package is GPL-3.0-or-later; see [LICENSE](../LICENSE) and
[third-party notices](../THIRD_PARTY_NOTICES.md). It supports only canonical
90°×90° geometry, general classification B. Phase-aware Pdiff/Sdiff is
validated, sampling stability is `indeterminate`, and
`boundary_time_production_safe=false`. It neither verifies the user patch nor
replaces mesher/database/solver, Stacey, topology, or waveform acceptance.
