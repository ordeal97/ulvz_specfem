# Two-chunk non-90° width validation: current-source closure

**Status:** closed validation of equal-square widths in the current source.
**Evidence root:**
`results/two_chunk_non90_width_acceptance_20260716T171151Z/`.

## Scope and outcome

This round tested only equal square inputs (`ANGULAR_WIDTH_XI_IN_DEGREES =
ANGULAR_WIDTH_ETA_IN_DEGREES`) at 60°, 75°, 89°, 90°, 91°, and 105°, using the
accepted two-chunk endpoint patch, `NEX_XI=NEX_ETA=96`, and 1×1 MPI processes
per chunk for the initial geometry gate. It did **not** alter source, relax a
guard, construct artificial coordinates, or test rectangular widths.

The source requires xi width 90° whenever `NCHUNKS > 1`:

```fortran
! this MUST be 90 degrees for two chunks or more to match geometrically
if (NCHUNKS > 1 .and. abs(ANGULAR_WIDTH_XI_IN_DEGREES - 90.d0) > 0.00000001d0) &
  stop 'ANGULAR_WIDTH_XI_IN_DEGREES must be 90 for more than one chunk'
```

Source: `specfem3d_globe/src/shared/read_compute_parameters.f90:433-435`.
Thus 60°, 75°, 89°, 91°, and 105° were input-rejected before a mesh existed.
That is an **input-validation result**, not evidence that their hypothetical
shared faces form a measured gap or overlap.

| Equal square width | `input_accepted` | Where it stopped | Downstream geometry/topology/Stacey/decomposition/waveforms | `formally_supported` |
|---:|:---:|---|---|:---:|
| 60° | false | xi-width source guard | not evaluated | false |
| 75° | false | xi-width source guard | not evaluated | false |
| 89° | false | xi-width source guard | not evaluated | false |
| 90° | true | fresh 2-rank control completed | accepted full 2/8/12-rank baseline available | true |
| 91° | false | xi-width source guard | not evaluated | false |
| 105° | false | xi-width source guard | not evaluated | false |

Exact stdout/stderr and statuses are retained per width under
`results/two_chunk_non90_width_acceptance_20260716T171151Z/02_mesher_runs/`.
The later unsandboxed attempts are the source-result provenance; earlier
sandbox attempts are retained separately and were infrastructure failures.

## Source audit

The complete audit is
`results/two_chunk_non90_width_acceptance_20260716T171151Z/00_source_audit/source_audit.md`.
Its operational findings are separated below so that input validation is not
mistaken for a physical measurement.

1. **Input validation.** `read_compute_parameters.f90:430-439` permits
   `NCHUNKS=1,2,3,6`, enforces xi=90° for every multi-chunk configuration, and
   only enforces eta=90° for more than two chunks. Therefore a two-chunk
   rectangular `xi=90°, eta!=90°` case is `not_tested`, not accepted here.
2. **90° cubed-sphere faces and geometric placement.** Before regional
   rotation, the fixed face mappings are AB `(-y,+x,+z)` and AC
   `(-y,-z,+x)`: `create_central_cube.f90:124-137`. The coordinate-location
   helper uses the corresponding AB `atan(y/z),atan(-x/z)` and AC
   `atan(-z/y),atan(x/y)` maps: `write_profile.f90:1290-1357,1437-1492`.
   `initialize_mesher.f90:126-132` converts the two
   widths and creates one Euler matrix from the central longitude/latitude and
   gamma. `euler_angles.f90:45-84` constructs that rotation; its corner helper
   uses the cubed-sphere `tan(xi),tan(eta)` construction at
   `euler_angles.f90:92-165`. This is not an API for independently orienting
   chunk 2.
3. **MPI interface topology.** The two-chunk AB→AC path is fixed as AB
   xi-min to AC xi-max with unchanged eta process index, and it is segmented
   in eta: `create_chunk_buffers.f90:163-186,325-337`.
4. **Accepted endpoint patch.** C1 uses the eta-min two-member path and C2
   the eta-max two-member path; the third array slot remains `INVALID_RANK`.
   The member loops and bounds checks use two members for `NCHUNKS=2`:
   `create_chunk_buffers.f90:843-881,988-997,1064-1072`. This patch is
   unchanged in this validation.
5. **Stacey roles.** `get_absorb.f90:266-281,332-385` adds xmin only to AC
   and xmax only to AB for two chunks. It thereby treats AB xi-min/AC xi-max
   as the internal interface by face role; it does not infer this from shared
   endpoint nodes.

The buffer assembly uses rank/topology mappings; it does not independently
assert coordinate equality. Physical coordinate matching is therefore a mesh
gate, which cannot be evaluated for a rejected input.

## Fresh 90° control and accepted baseline

The already-started fresh 90° 2-rank mesher completed normally. The extraction
at
`results/two_chunk_non90_width_acceptance_20260716T171151Z/03_interface/width_90_deg_fresh_1x1_attempt_4/fresh_90_interface_comparison_canonical.json`
reports:

- interface node counts AB/AC: region 1: 21,469/21,469; region 2:
  4,937/4,937; region 3: 441/441;
- all coordinate keys match, no unmatched nodes, and all paired Cartesian
  residuals are exactly 0.0 at the recorded precision;
- C1 eta-min and C2 eta-max endpoint paired Cartesian and angular residuals
  are 0.0 in all three regions;
- positive minimum Jacobian ratios: 0.0614958592, 0.146539599, 0.577339351;
- zero internal-interface Stacey faces. Rank 0 has only the AB external
  `i_max` role and rank 1 only the AC external `i_min` role.

The JSON's maximum angular values of at most `1.71e-6` degrees are numerical
`acos` evaluation artefacts on Cartesian pairs whose stored Cartesian distance
is zero; they are not an interface separation. This new run is a supplemental
2-rank control. The authoritative full acceptance remains:

- [`two_chunk_corner_topology_acceptance.md`](two_chunk_corner_topology_acceptance.md)
  for C1/C2 reciprocal paths, shallow/mid-mantle/CMB-near topology, ownership
  roles and Stacey checks;
- [`two_chunk_waveform_symmetry_closure.md`](two_chunk_waveform_symmetry_closure.md)
  for 2/8/12-rank decomposition invariance, C1/C2 symmetry, waveform limits,
  one-chunk regression and six-chunk regression.

No 8- or 12-rank mesh, database, solver, or waveform test was run for a
rejected non-90° width.

## Coordinate-comparison provenance

For every rejected width,
`results/two_chunk_non90_width_acceptance_20260716T171151Z/03_interface/width_*_deg_rejected.json`
contains empty node sets, null coordinate metrics, and
`reason=input_rejected_before_mesh`; the corresponding CSV has only its header.
The schema explicitly records `gap_or_overlap=not_evaluated`. No gap/overlap
figure is generated for a geometry that was never constructed.

## Final classification

```text
canonical_90deg_fixture_ready = true
general_two_chunk_mode_classification = B
xi_connection_width_non90_supported = false
equal_square_non90_supported = false
rectangular_xi90_eta_non90_supported = not_tested
arbitrary_non90_two_chunk_supported = false
equal_square_non90_result = input_rejected
measured_gap_overlap_for_rejected_widths = not_evaluated
non90_connection_width_requires_new_implementation = true
```

`arbitrary_non90_two_chunk_supported=false` means that arbitrary non-90° modes
are not project-supported; it is not a claim that every possible rectangular
geometry has been disproved. In particular, the xi=90°, eta≠90° possibility is
outside this test round. Enabling a non-90° **xi connection width** needs new
chunk-2 placement and/or interface mapping, followed by independent topology,
Stacey, decomposition and waveform acceptance.

No formal source or build rule changed, and the accepted patch semantics were
not modified:

```text
formal_source_modified = false
formal_build_rules_modified = false
accepted_patch_modified = false
commit_performed = false
push_performed = false
```
