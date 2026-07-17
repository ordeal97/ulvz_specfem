# Canonical two-chunk absorbing-boundary audit

## Operational conclusion

For the accepted canonical regional configuration (`NCHUNKS=2`, 90° × 90°),
use exposed-face regional Stacey boundaries:

```fortran
ABSORBING_CONDITIONS = .true.
ABSORB_USING_GLOBAL_SPONGE = .false.
```

The current source rejects `ABSORB_USING_GLOBAL_SPONGE=.true.` unless
`NCHUNKS=6`.  The shared AB--AC face is an internal field-exchange face.  It
is never a sponge face, a Stacey face, or any other absorbing boundary.  This
is an implementation fact, not merely a recommended configuration.

## Source audit

| Topic | Current-source evidence | Result for canonical two chunks |
|---|---|---|
| Multi-chunk geometry guard | `src/shared/read_compute_parameters.f90`, `read_compute_parameters`, lines 433--435: `NCHUNKS > 1` requires `ANGULAR_WIDTH_XI_IN_DEGREES == 90.d0` | Required input condition. |
| Regional absorbing-condition guard | same routine, lines 450--454: absorbing conditions are stopped for `NCHUNKS=6` and `NCHUNKS=3` | `NCHUNKS=2` is a permitted regional absorbing-boundary case. |
| Global-sponge guard | same routine, lines 456--457: `ABSORB_USING_GLOBAL_SPONGE` stops unless `NCHUNKS == 6` | Not available for `NCHUNKS=2`; do not bypass this stop. |
| Parameter parsing | `src/shared/read_parameter_file.F90`, `read_parameter_file`, lines 125--138 | `ABSORBING_CONDITIONS`, sponge flag, and sponge parameters are read under their documented control flow. |
| Regional face construction | `src/meshfem3D/create_regions_mesh.F90`, `create_regions_mesh`, lines 210--214 and 353--361 | For non-six-chunk absorbing runs, mesh generation calls `get_absorb` and builds Stacey arrays. |
| Internal-face exclusion | `src/meshfem3D/get_absorb.f90`, `get_absorb`, lines 267--294 and 332--406 | AB `xi-min` and AC `xi-max` are excluded; AC `xi-min`, AB `xi-max`, and eta outer faces are selected by face role. |
| Stacey database output | `get_absorb.f90`, `get_absorb`, lines 525 onward | Selected faces are written to the regional Stacey data used by the run. |
| Sponge physical mechanism | `src/meshfem3D/meshfem3D_models.F90`, `meshfem3D_models_getatten_val`, lines 1828--1852; invoked only when `ATTENUATION` in `get_model.F90`, lines 241--246 | Sponge is an attenuation/Q modification path, not a two-chunk interface boundary treatment. It is source-rejected for this configuration. |

### Compile-time versus run-time controls

The audited parameter guard and face-selection path contain no separate
two-chunk compile-time switch: the decision is made from run-time `Par_file`
values and `NCHUNKS`.  `ABSORB_USING_GLOBAL_SPONGE` is rejected at parameter
validation before mesh construction when `NCHUNKS /= 6`; `get_absorb` selects
regional Stacey faces during meshing when `ABSORBING_CONDITIONS` is true.
`ATTENUATION` is a run-time model flag controlling whether the attenuation
model path is entered.  This audit did not change compilation options or build
rules; it does not infer any uninspected compiler-specific condition.

The exact current stop text is: `Please set NCHUNKS to 6 in Par_file to use
ABSORB_USING_GLOBAL_SPONGE`.

## Why the AB--AC interface is not absorbed

The two chunks meet at the AB/AC cubed-sphere face.  Matching nodes on that
face exchange wavefield buffer values between MPI ranks.  Calling it a
boundary would discard or damp a signal that must continue into the adjacent
chunk.  `get_absorb.f90` therefore classifies faces by *chunk role plus face
role*, not merely by whether a process lies at an xi/eta decomposition edge.

C1 and C2 are the eta-min and eta-max endpoints of that internal face.  An
endpoint can also lie on a genuine outer exposed boundary.  That shared node
does not make the *AB--AC face* a Stacey face: the face-role database must
still record zero internal AB--AC Stacey faces.  The accepted topology report
and waveform closure record this check in
[`two_chunk_corner_topology_acceptance.md`](two_chunk_corner_topology_acceptance.md)
and [`two_chunk_waveform_symmetry_closure.md`](two_chunk_waveform_symmetry_closure.md).

## User configuration rule

1. Set `ABSORBING_CONDITIONS=.true.` for the exposed regional outer faces.
2. Keep `ABSORB_USING_GLOBAL_SPONGE=.false.` for `NCHUNKS=2`.
3. Do not add an absorbing condition to AB--AC in a local input edit or
   analysis script.
4. After meshing, check the face-role report: internal AB--AC Stacey occurrence
   must be zero; exposed outer faces must retain their required role.
5. Treat a sponge/global-boundary attempt with two chunks as a stop condition,
   not as a tunable alternative.

No source, build rule, or accepted endpoint-patch semantics were modified by
this audit.
