# Two-chunk implementation attempt — 2026-07-15

This is an isolated implementation attempt based on the earlier two-chunk
classification **B**. It does not claim production support and it does not
modify the nested production SPECFEM source tree.

## Geometry and root cause

`CHUNK_AB` and `CHUNK_AC` share `AB xi=min` to `AC xi=max`. From
`compute_coordinates_grid.f90`, their unit surface maps are `AB=(-y,x,1)`
and `AC=(-y,-1,x)`, with the same normalization. Therefore eta is not
reversed.

| Endpoint | AB corner / rank (2x2) | AC corner / rank (2x2) | Cartesian coordinate |
| --- | --- | --- | --- |
| eta-min | `(xi-min,eta-min)`, 0 | `(xi-max,eta-min)`, 5 | `(1,-1,1)/sqrt(3)` |
| eta-max | `(xi-min,eta-max)`, 2 | `(xi-max,eta-max)`, 7 | `(-1,-1,1)/sqrt(3)` |

The legacy two-chunk branch made only one three-member corner record: it
omitted eta-min, retained a BC third member absent from the two-face domain,
and used `NPROC_XI` to count a face segmented in eta. The proposed isolated
patch makes two two-member endpoint records, uses `NPROC_ETA` for the face
message count, and uses `INVALID_RANK=-1` only for the unused third slot.
All two-chunk worker-2 accesses in scalar corner assembly are guarded by
`NCHUNKS /= 2`.

For owner-set `{0,2,5,7}`, all six direct pairs are valid: `0-2`, `0-5`,
`0-7`, `2-5`, `2-7`, and `5-7`. Thus `0-7` and `2-5` must not be removed.

## Evidence

The only proposed production change is
`src/meshfem3D/create_chunk_buffers.f90`; the patch is at
`results/two_chunk_implementation_20260715T132433Z/03_patch/two_chunk_fix.patch`.
The isolated build enabled bounds checks, initialized-variable checking, and
invalid/zero/overflow floating-point traps.

| Test | Result |
| --- | --- |
| two-chunk mesh: 1x1, 1x2, 2x1, 2x2, 2x3/chunk | pass |
| one-chunk and six-chunk mesh/short solver regression | pass |
| two-chunk 2-rank and 8-rank short solver | pass |
| actual scalar/vector MPI assembly (`2^rank`) | pass: sum = 15; reset/non-owner checks pass |
| 1x1 versus 2x2 strict waveform comparison | pass, three components |

For the 2x2 database, every buffered coordinate is owned by both endpoints,
reciprocal lists agree, and no directed interface contains a duplicate node.
The strict comparison has zero shift, CC above `0.99999999999`, NRMS below
`4.5e-6`, peak-ratio error below `6e-7`, and energy difference below
`1.1e-6`. See `06_solver_tests/decomposition_invariance.json`.

## Classification

The classification remains **B**. The formal source tree was deliberately
left untouched: the complete A gate still lacks a dedicated endpoint-near
multi-probe wavefield/energy experiment, a Stacey-boundary record audit, and
formal-tree patch/rebuild/repeat validation. This does not establish
scientific-domain safety, production readiness for the current fixture, or a
Hawai'i production recommendation.

Machine-readable status and all result paths are recorded in
`results/two_chunk_implementation_20260715T132433Z/08_reports/summary.json`.
