# Task 3B: translating the S20RTS manual method to local S40RTS

Repository version assumed for this audit:

- `v8.1.0-323-g9c312cb2`
- commit `9c312cb2c991b47484a7f302775f4f01ed9470f8`

This is a research-and-design note only. No SPECFEM source file, model data file,
Makefile, `Par_file`, or simulation input is modified by this task.

## 1. Version mismatch in the user manual

The user manual describes the S20RTS replacement method using an older-style
routine interface:

```fortran
call mantle_s20rts(radius,theta,phi,dvs,dvp,drho,D3MM_V)
```

In the local source, `D3MM_V` is not an argument of either the S20RTS or S40RTS
mantle-evaluation routine. A direct source search finds `D3MM_V` only in the
manual text, not in the local `model_s20rts.f90`, `model_s40rts.f90`, or
`meshfem3D_models.F90` implementation. The local equivalent of the manual's
model-data structure is a Fortran module with saved allocatable arrays.

For S40RTS, the arrays are stored in module `model_s40rts_par`:

- spherical-harmonic degree and radial basis sizes: `NK_20 = 20`,
  `NS_40 = 40` (`specfem3d_globe/src/meshfem3D/model_s40rts.f90:58-65`);
- S-wave and P-wave coefficient arrays:
  `S40RTS_V_dvs_a`, `S40RTS_V_dvs_b`, `S40RTS_V_dvp_a`,
  `S40RTS_V_dvp_b` (`specfem3d_globe/src/meshfem3D/model_s40rts.f90:66-70`);
- radial knot and spline arrays:
  `S40RTS_V_spknt`, `S40RTS_V_qq0`, `S40RTS_V_qq`
  (`specfem3d_globe/src/meshfem3D/model_s40rts.f90:72-75`).

The exact local S40RTS routine signatures are:

```fortran
subroutine model_s40rts_broadcast()
subroutine read_model_s40rts()
subroutine mantle_s40rts(radius,theta,phi,dvs,dvp,drho)
```

Evidence:

- `model_s40rts_broadcast()` is defined without arguments at
  `specfem3d_globe/src/meshfem3D/model_s40rts.f90:83`;
- `read_model_s40rts()` is defined without arguments at
  `specfem3d_globe/src/meshfem3D/model_s40rts.f90:128`;
- `mantle_s40rts(radius,theta,phi,dvs,dvp,drho)` is defined at
  `specfem3d_globe/src/meshfem3D/model_s40rts.f90:183`, with `radius`,
  `theta`, and `phi` as inputs and `dvs`, `dvp`, `drho` as outputs at
  `specfem3d_globe/src/meshfem3D/model_s40rts.f90:193-194`.

The manual is therefore not literally current for this repository, but its
method remains directly applicable if translated as follows:

- Preserve the local call structure: keep
  `mantle_s40rts(radius,theta,phi,dvs,dvp,drho)` callable by the existing
  dispatcher.
- Preserve the returned quantities: continue returning relative `dvs`, `dvp`,
  and `drho`, because the dispatcher multiplies these into the reference
  `vpv`, `vph`, `vsv`, `vsh`, and `rho` fields after the model routine returns
  (`specfem3d_globe/src/meshfem3D/meshfem3D_models.F90:765-770`).
- Preserve rank-0 reading and broadcast logic: local S40RTS reads files on rank
  0 in `model_s40rts_broadcast()` and broadcasts module arrays with
  `bcast_all_dp`, rather than broadcasting `D3MM_V` structure fields
  (`specfem3d_globe/src/meshfem3D/model_s40rts.f90:112-121`).
- Preserve the external model data unless the experiment explicitly requires a
  data-file replacement. For an analytical ULVZ overlay, the S40RTS coefficient
  files can remain unchanged.

## 2. Manual-to-S40RTS mapping table

| User-manual S20RTS concept | Old/manual S20RTS name | Local S40RTS equivalent | Required action for an S40RTS+ULVZ model | Evidence |
| -------------------------- | ---------------------- | ----------------------- | ---------------------------------------- | -------- |
| Model source file | `model_s20rts.f90` replacement file | `src/meshfem3D/model_s40rts.f90` | Prototype: modify only the S40RTS implementation in this file; production: prefer a named wrapper/variant. | Manual replacement statement: `doc/USER_MANUAL/12_changing_the_model.tex:150-153`; S40RTS source: `src/meshfem3D/model_s40rts.f90:1-7`. |
| Broadcast routine | `model_s20rts_broadcast` | `model_s40rts_broadcast()` | Keep the no-argument broadcast routine callable from `meshfem3D_mantle_broadcast`; only extend it if ULVZ parameters are read on rank 0. | Manual broadcast requirement: `doc/USER_MANUAL/12_changing_the_model.tex:156-165`; local S40RTS definition: `src/meshfem3D/model_s40rts.f90:83`; dispatcher call: `src/meshfem3D/meshfem3D_models.F90:189-190`. |
| Model-reading routine | rank-0 model-data read, then broadcast | `read_model_s40rts()` called by rank 0 | Leave native S40RTS coefficient reading unchanged; add ULVZ parameter reading only if a parameter file is introduced. | `src/meshfem3D/model_s40rts.f90:112`, `src/meshfem3D/model_s40rts.f90:128-179`. |
| Mantle-evaluation routine | `mantle_s20rts(radius,theta,phi,dvs,dvp,drho,D3MM_V)` | `mantle_s40rts(radius,theta,phi,dvs,dvp,drho)` | Apply an analytical overlay after native S40RTS `dvs`, `dvp`, `drho` are computed and before returning. | Manual call: `doc/USER_MANUAL/12_changing_the_model.tex:114-119`; local S40RTS signature: `src/meshfem3D/model_s40rts.f90:183-194`. |
| Model arrays | `D3MM_V` structure fields | Module arrays in `model_s40rts_par` | Do not pass a structure; use module storage or local helper arguments consistent with S40RTS style. | Manual structure description: `doc/USER_MANUAL/12_changing_the_model.tex:145-148`, `doc/USER_MANUAL/12_changing_the_model.tex:162-165`; local arrays: `src/meshfem3D/model_s40rts.f90:46-75`. |
| Spline arrays | manual S20RTS model variables | `S40RTS_V_spknt`, `S40RTS_V_qq0`, `S40RTS_V_qq` | Leave spline setup unchanged; overlay should act after native spline and harmonic evaluation. | Declarations: `src/meshfem3D/model_s40rts.f90:72-75`; setup call: `src/meshfem3D/model_s40rts.f90:177`; spline setup: `src/meshfem3D/model_s40rts.f90:311-356`. |
| Spherical-harmonic degree | S20RTS model truncation | `NS_40 = 40` | Treat S40RTS as degree 40 for S-wave coefficients; P12 coefficients are zero-filled above degree 12. | `src/meshfem3D/model_s40rts.f90:58-65`, `src/meshfem3D/model_s40rts.f90:156-174`. |
| S-wave coefficient file | S20RTS data file | `DATA/s40rts/S40RTS.dat` | Keep this file unmodified for an analytical overlay. | `src/meshfem3D/model_s40rts.f90:137`, `src/meshfem3D/model_s40rts.f90:140-154`. |
| P-wave coefficient file | companion P model in manual method | `DATA/s20rts/P12.dat` | Keep this file unmodified; S40RTS locally obtains `dvp` from the P12 coefficients. | `src/meshfem3D/model_s40rts.f90:138`, `src/meshfem3D/model_s40rts.f90:156-174`. |
| Rank-0 file reading | `if (myrank == 0) read...` | `if (myrank == 0) call read_model_s40rts()` | Preserve rank-0-only file I/O. If ULVZ parameters are read from a file, read them on rank 0 and broadcast them. | Manual rank-0 pattern: `doc/USER_MANUAL/12_changing_the_model.tex:168-195`; local S40RTS: `src/meshfem3D/model_s40rts.f90:112`. |
| MPI broadcasting | `MPI_BCAST` of model variables | `bcast_all_dp` of S40RTS module arrays | Existing S40RTS data-array broadcasts remain unchanged; add broadcasts only for new ULVZ parameters if they are read at runtime. | `src/meshfem3D/model_s40rts.f90:115-121`. |
| Relative `dvs`, `dvp`, `drho` outputs | manual output variables | `dvs`, `dvp`, `drho` returned by `mantle_s40rts` | Return final relative perturbations using the chosen ULVZ combination convention. | Manual output description: `doc/USER_MANUAL/12_changing_the_model.tex:140-148`; local intent-out variables: `src/meshfem3D/model_s40rts.f90:193-194`. |
| Final multiplication into the 1-D reference model | apply perturbation after model routine | Dispatcher multiplication after `mantle_s40rts` | Do not duplicate PREM multiplication inside `mantle_s40rts`; return relative perturbations only. | S40RTS call and multiplication: `src/meshfem3D/meshfem3D_models.F90:765-770`; PREM/aniso reference path: `src/meshfem3D/meshfem3D_models.F90:439-445`. |

## 3. Exact S40RTS calculation path and ULVZ insertion point

The local S40RTS calculation path is:

```text
model_s40rts_broadcast()
  -> rank 0 calls read_model_s40rts()
      -> read DATA/s40rts/S40RTS.dat
      -> read DATA/s20rts/P12.dat
      -> zero-fill P coefficients above degree 12
      -> call s40rts_splhsetup()
  -> broadcast S40RTS coefficient and spline arrays

meshfem3D_models_get3Dmntl_val()
  -> construct the 1-D reference model before model perturbation
  -> S40RTS branch calls mantle_s40rts(r_used,theta,phi,dvs,dvp,drho)
  -> multiply vpv, vph, vsv, vsh, rho by (1 + dvp/dvs/drho)
```

Evidence:

- S40RTS and P12 file names:
  `src/meshfem3D/model_s40rts.f90:137-138`;
- S40RTS coefficient read:
  `src/meshfem3D/model_s40rts.f90:140-154`;
- P12 coefficient read and zero fill above degree 12:
  `src/meshfem3D/model_s40rts.f90:156-174`;
- radial spline setup:
  `src/meshfem3D/model_s40rts.f90:177`, `src/meshfem3D/model_s40rts.f90:311-356`;
- native S40RTS spherical-harmonic evaluation:
  `src/meshfem3D/model_s40rts.f90:235-270`;
- S40RTS paper/default scaling of `dvs`, `dvp`, and `drho`:
  `src/meshfem3D/model_s40rts.f90:272-305`;
- dispatcher combination with the 1-D reference model:
  `src/meshfem3D/meshfem3D_models.F90:765-770`.

Two possible insertion points are available.

**A. Inside `mantle_s40rts`.** Apply the ULVZ overlay after the native S40RTS
`dvs`, `dvp`, and `drho` have been computed, including the local
`S40RTS_PERTURBATION_SCALING` and `S40RTS_USE_3D_PERTURBATION_PAPER_VERSION`
logic, but before `mantle_s40rts` returns. In the current source this means
after the scaling block ending at `src/meshfem3D/model_s40rts.f90:305` and
before the subroutine ends at `src/meshfem3D/model_s40rts.f90:307`.

Advantages:

- It follows the manual's "replace or modify the model routine while preserving
  the call structure" approach.
- It can be prototyped while keeping `MODEL = s40rts`.
- It leaves the generic dispatcher and the PREM multiplication logic unchanged.
- It keeps all S40RTS-native coefficient reading, spline setup, and MPI
  broadcasting intact.

Limitations:

- It silently changes all `MODEL = s40rts` runs in that build unless the ULVZ is
  disabled or amplitudes are zero.
- It is less explicit than a named production model variant in `Par_file`.

**B. In the S40RTS branch of `meshfem3D_models_get3Dmntl_val`.** Apply the ULVZ
overlay after the call at `src/meshfem3D/meshfem3D_models.F90:765`, before the
multiplications at `src/meshfem3D/meshfem3D_models.F90:766-770`.

Advantages:

- It makes the overlay location visible in the generic model-combination layer.
- It is a natural place for a production named variant such as `s40rts_ulvz`.

Limitations:

- It modifies shared dispatcher logic rather than the S40RTS model routine
  itself.
- It is not the closest translation of the user manual's S20RTS replacement
  method.
- If used with `MODEL = s40rts`, it still changes the behavior of the generic
  S40RTS branch.

Recommendation for the first ULVZ prototype: use insertion point A, inside
`mantle_s40rts`, after native `dvs`, `dvp`, and `drho` are finalized and before
return. This is the smallest source-level translation of the manual method
because it preserves the existing S40RTS call structure and the dispatcher's
relative-perturbation contract.

## 4. Perturbation-combination equations

Let `d_s40` denote one of the native perturbations returned by S40RTS:
`dvs_s40`, `dvp_s40`, or `drho_s40`. Let `d_ulvz` denote the corresponding
analytical ULVZ perturbation, and let `w` be the ULVZ taper:

```text
w = 0 outside the ULVZ
w = 1 inside the ULVZ core
0 < w < 1 within the boundary taper
```

The dispatcher applies returned perturbations as:

```text
X_final = X_PREM * (1 + d_return)
```

where `X` is `vpv`, `vph`, `vsv`, `vsh`, or `rho`.

### Convention A: ULVZ perturbation relative to the local S40RTS background

Native S40RTS gives:

```text
X_s40 = X_PREM * (1 + d_s40)
```

If the ULVZ perturbation is relative to the local S40RTS background, the desired
value is:

```text
X_final = X_s40 * (1 + w * d_ulvz)
```

Substituting the native S40RTS value:

```text
X_final = X_PREM * (1 + d_s40) * (1 + w * d_ulvz)
```

Because the dispatcher still expects one relative perturbation `d_return`, a
modified `mantle_s40rts` should return:

```text
d_return = (1 + d_s40) * (1 + w * d_ulvz) - 1
         = d_s40 + w * d_ulvz + w * d_s40 * d_ulvz
```

This satisfies the required limits:

- outside the ULVZ, `w = 0`, so `d_return = d_s40`;
- inside the ULVZ core, `w = 1`, so the ULVZ perturbation is relative to the
  local S40RTS velocity or density.

Numerical check:

```text
dvs_s40  = +0.03
dvs_ulvz = -0.20
w        = 1

dvs_return = (1 + 0.03) * (1 - 0.20) - 1
           = 1.03 * 0.80 - 1
           = -0.176
```

Simple addition would give `0.03 - 0.20 = -0.17`, which is not the exact
local-background-relative result.

### Convention B: ULVZ perturbation relative to the 1-D PREM background

If the ULVZ is defined as an additive PREM-relative perturbation superimposed on
S40RTS, then:

```text
X_final = X_PREM * (1 + d_s40 + w * d_ulvz_prem)
```

and the returned perturbation is:

```text
d_return = d_s40 + w * d_ulvz_prem
```

If instead the ULVZ is defined as the total desired PREM-relative material
inside the ULVZ, then it is a replacement or blend convention:

```text
d_return = (1 - w) * d_s40 + w * d_ulvz_total_prem
```

This second PREM-relative convention partly replaces the local tomography inside
the ULVZ and is scientifically different from superimposing an anomaly on the
local S40RTS background.

For the first ULVZ parameter sweep, convention A should be used: define ULVZ
`dVp`, `dVs`, and `dRho` relative to the local S40RTS background. This preserves
native S40RTS outside the ULVZ and treats the ULVZ as a superimposed material
anomaly on the actual local tomographic background.

## 5. Smallest modification compatible with the manual

For a prototype that keeps:

```text
MODEL = s40rts
```

the smallest manual-compatible design is:

- keep `model_s40rts_broadcast()`, `read_model_s40rts()`, and
  `mantle_s40rts(radius,theta,phi,dvs,dvp,drho)` callable with their current
  signatures;
- calculate the analytical ULVZ geometry in a small helper inside
  `model_s40rts.f90`, for example a helper that receives
  `radius, theta, phi` and returns a taper weight `w`, or a helper that receives
  `radius, theta, phi, dvs, dvp, drho` and updates the perturbations;
- call that helper from `mantle_s40rts` after the native S40RTS perturbations
  have been computed and scaled, before the subroutine returns;
- store initial ULVZ parameters as module-level constants or parameters in the
  S40RTS implementation for the prototype.

Hard-coded parameters are acceptable only for a first local prototype if the
values are explicitly reported and the zero-amplitude case is used to verify
native S40RTS reproducibility. They are not suitable for parameter sweeps or
production runs.

No new file read is required for the hard-coded prototype, so
`model_s40rts_broadcast()` does not need to change. The existing S40RTS data
array broadcast remains unchanged:

- coefficient and spline arrays are allocated and read as before
  (`src/meshfem3D/model_s40rts.f90:101-112`);
- `S40RTS_V_dvs_a`, `S40RTS_V_dvs_b`, `S40RTS_V_dvp_a`, `S40RTS_V_dvp_b`,
  `S40RTS_V_qq0`, and `S40RTS_V_qq` are broadcast as before
  (`src/meshfem3D/model_s40rts.f90:115-121`).

If ULVZ parameters are later read only by rank 0, the following values must be
broadcast to all ranks:

- enable/disable flag;
- center latitude in degrees;
- center longitude in degrees;
- CMB height/thickness in km;
- lateral radius in km;
- boundary-taper width in km;
- `dvp_ulvz`;
- `dvs_ulvz`;
- `drho_ulvz`;
- convention flag identifying local-S40RTS-relative or PREM-relative
  interpretation.

The safer production design is:

```text
MODEL = s40rts_ulvz
```

That design should keep native `s40rts` untouched and route the new model name
through a clearly named S40RTS+ULVZ branch. The source/build files that would
need changes for a named model variant are:

- `setup/constants.h.in`: define a new model constant such as
  `THREE_D_MODEL_S40RTS_ULVZ` near the existing S40RTS constants
  (`setup/constants.h.in:968-989`);
- `setup/constants.h`: generated/local configured counterpart currently
  containing `THREE_D_MODEL_S40RTS` (`setup/constants.h:968-989`);
- `src/meshfem3D/meshfem3D_par.f90`: import the new model constant alongside
  existing model constants (`src/meshfem3D/meshfem3D_par.f90:66-78`);
- `src/shared/get_model_parameters.F90`: add a `case ('s40rts_ulvz')` with the
  same core flags as `s40rts`, but using the new model constant
  (`src/shared/get_model_parameters.F90:492-498`);
- `src/meshfem3D/meshfem3D_models.F90`: add broadcast and evaluation branches
  for the new named variant, reusing native S40RTS reading and applying the ULVZ
  overlay only for the variant (`src/meshfem3D/meshfem3D_models.F90:184-190`,
  `src/meshfem3D/meshfem3D_models.F90:765-770`);
- `src/meshfem3D/model_s40rts.f90` or a new shared helper source: provide the
  ULVZ geometry/taper and perturbation-combination logic;
- `src/meshfem3D/rules.mk`: update object lists and module dependencies only if
  a new source file or module is introduced
  (`src/meshfem3D/rules.mk:115-116`, `src/meshfem3D/rules.mk:184-186`,
  `src/meshfem3D/rules.mk:369`).

## 6. Geometry and coordinate requirements

The local `mantle_s40rts` coordinate convention is:

- `radius`: non-dimensional radius, scaled by Earth radius;
- `theta`: colatitude in radians;
- `phi`: longitude in radians;
- radial domain: active only for `r_cmb < radius < r_moho`; outside this range
  the routine returns zero perturbations;
- local constants: `R_EARTH_ = EARTH_R`, `RMOHO_ = EARTH_R - 24400.d0`,
  `RCMB_ = 3480000.d0`;
- radial coordinate used by the S40RTS basis:
  `xr = 2.0 * (radius - r_cmb) / (r_moho - r_cmb) - 1.0`.

Evidence:

- input units and declarations:
  `src/meshfem3D/model_s40rts.f90:183-194`;
- CMB and Moho radii:
  `src/meshfem3D/model_s40rts.f90:208-210`;
- radial domain return:
  `src/meshfem3D/model_s40rts.f90:225-229`;
- S40RTS radial scaling:
  `src/meshfem3D/model_s40rts.f90:230-233`.

For a ULVZ specified by:

```text
center latitude [degrees]
center longitude [degrees]
CMB height/thickness [km]
lateral radius [km]
boundary-taper width [km]
```

the implementation should convert:

- center latitude and longitude from degrees to radians;
- evaluation latitude from colatitude:

```text
lat = pi / 2 - theta
lon = phi
```

- longitude difference with wraparound into `[-pi, pi]`;
- lateral distance on the CMB sphere:

```text
angular_distance =
  acos(sin(lat) * sin(lat0) + cos(lat) * cos(lat0) * cos(lon - lon0))

lateral_distance_km = RCMB_km * angular_distance
```

- height above the CMB:

```text
height_above_cmb_km = radius * R_EARTH_km - RCMB_km
```

The overlay must prevent extension below the CMB by returning `w = 0` whenever
`height_above_cmb_km < 0` or when `radius <= r_cmb`. The radial ULVZ interval
should be clamped to:

```text
0 <= height_above_cmb_km <= thickness_km
```

The lower radial boundary is the CMB itself; tapering should not create material
below the CMB. A smooth taper can be applied laterally near the specified
lateral radius and radially near the top of the ULVZ, with all taper distances
defined in km.

## Recommended prototype route

Keep `MODEL = s40rts` and follow the manual's model-routine replacement method:
modify only the S40RTS implementation, apply the analytical ULVZ overlay inside
`mantle_s40rts` after native S40RTS perturbations are computed and before the
routine returns, and keep the dispatcher multiplication unchanged.

This route is appropriate for Task 3B's first S40RTS-only prototype because it
preserves the local S40RTS call structure:

```fortran
subroutine mantle_s40rts(radius,theta,phi,dvs,dvp,drho)
```

The prototype should use convention A: ULVZ perturbations relative to the local
S40RTS background, combined as:

```text
d_return = (1 + d_s40) * (1 + w * d_ulvz) - 1
```

## Recommended production route

Introduce a named model variant:

```text
MODEL = s40rts_ulvz
```

The production route should keep native `MODEL = s40rts` behavior unchanged and
make the ULVZ experiment explicit in `Par_file`. The named variant should reuse
the native S40RTS reader, coefficient arrays, radial splines, and MPI broadcast,
then apply a shared analytical ULVZ overlay only in the `s40rts_ulvz` branch.

## Minimal future code changes

For the prototype:

- `src/meshfem3D/model_s40rts.f90`: add a small analytical ULVZ helper and call
  it from `mantle_s40rts` after native `dvs`, `dvp`, and `drho` are finalized.

For the production named model:

- `setup/constants.h.in`;
- `setup/constants.h`;
- `src/meshfem3D/meshfem3D_par.f90`;
- `src/shared/get_model_parameters.F90`;
- `src/meshfem3D/meshfem3D_models.F90`;
- `src/meshfem3D/model_s40rts.f90` or a new shared ULVZ helper source;
- `src/meshfem3D/rules.mk` if a new source file or module is added.

The native S40RTS external files should remain unmodified:

- `DATA/s40rts/S40RTS.dat`;
- `DATA/s20rts/P12.dat`.

## Scientific convention to decide before implementation

Before writing code, the project must choose whether ULVZ `dVp`, `dVs`, and
`dRho` are defined relative to:

- the local S40RTS background, recommended for the first sweep; or
- the 1-D PREM background, which can mean either additive PREM-relative
  superposition or replacement by a PREM-relative target material.

This choice changes the algebra and the scientific meaning of the model. It
must be recorded with every ULVZ parameter set.

## Verification tests required before the first forward run

The required verification tests are:

1. zero-amplitude ULVZ reproduces native S40RTS;
2. a point outside the ULVZ reproduces native S40RTS;
3. a point inside the ULVZ has the analytically expected perturbation;
4. taper continuity;
5. all MPI ranks receive identical ULVZ parameters;
6. the original `DATA/s40rts/S40RTS.dat` and `DATA/s20rts/P12.dat` remain
   unmodified.

Inspection commands used for this document:

```bash
# The original local skill-cache inspection is intentionally omitted from the
# public workflow because its path is machine-specific.
test -e docs/s40rts_ulvz_manual_translation.md && nl -ba docs/s40rts_ulvz_manual_translation.md | sed -n '1,80p' || true
nl -ba specfem3d_globe/doc/USER_MANUAL/12_changing_the_model.tex | sed -n '105,197p'
nl -ba specfem3d_globe/src/meshfem3D/model_s40rts.f90 | sed -n '1,360p'
nl -ba docs/model_reader_comparison_s40rts_spiral.md | sed -n '1,220p'
nl -ba specfem3d_globe/src/meshfem3D/model_s20rts.f90 | sed -n '46,180p'
nl -ba specfem3d_globe/src/meshfem3D/model_s20rts.f90 | sed -n '220,360p'
nl -ba specfem3d_globe/src/meshfem3D/meshfem3D_models.F90 | sed -n '160,205p'
nl -ba specfem3d_globe/src/meshfem3D/meshfem3D_models.F90 | sed -n '639,775p'
nl -ba specfem3d_globe/src/shared/get_model_parameters.F90 | sed -n '91,244p'
nl -ba specfem3d_globe/src/shared/get_model_parameters.F90 | sed -n '260,305p'
nl -ba specfem3d_globe/src/shared/get_model_parameters.F90 | sed -n '484,500p'
nl -ba specfem3d_globe/src/meshfem3D/rules.mk | sed -n '105,130p'
nl -ba specfem3d_globe/src/meshfem3D/rules.mk | sed -n '178,196p'
find specfem3d_globe/src/meshfem3D -maxdepth 1 -type f \( -name 'meshfem3D_models.f90' -o -name 'meshfem3D_models.F90' \) -print
grep -RIn --exclude-dir=.git --exclude='*.o' --exclude='*.mod' 'D3MM_V' specfem3d_globe/src/meshfem3D/model_s20rts.f90 specfem3d_globe/src/meshfem3D/model_s40rts.f90 specfem3d_globe/src/meshfem3D/meshfem3D_models.F90 specfem3d_globe/doc/USER_MANUAL/12_changing_the_model.tex
grep -RIn --exclude-dir=.git --exclude='*.o' --exclude='*.mod' -E 'THREE_D_MODEL_S40RTS|model_s40rts_broadcast|mantle_s40rts|read_model_s40rts|S40RTS_V_' specfem3d_globe/src/meshfem3D specfem3d_globe/src/shared | head -120
grep -RIn --exclude-dir=.git --exclude='*.o' --exclude='*.mod' 'THREE_D_MODEL_S40RTS' specfem3d_globe/src specfem3d_globe/setup specfem3d_globe/DATA | head -80
nl -ba specfem3d_globe/setup/constants.h.in | sed -n '650,690p'
nl -ba specfem3d_globe/setup/constants.h | sed -n '650,690p'
nl -ba specfem3d_globe/src/meshfem3D/meshfem3D_par.f90 | sed -n '66,78p'
nl -ba specfem3d_globe/setup/constants.h.in | sed -n '960,990p'
nl -ba specfem3d_globe/setup/constants.h | sed -n '960,990p'
nl -ba specfem3d_globe/src/meshfem3D/meshfem3D_models.F90 | sed -n '436,490p'
nl -ba specfem3d_globe/src/meshfem3D/rules.mk | sed -n '360,375p'
wc -l docs/s40rts_ulvz_manual_translation.md
grep -n "^## Recommended prototype route\|^## Recommended production route\|^## Minimal future code changes\|^## Scientific convention to decide before implementation\|^## Verification tests required before the first forward run" docs/s40rts_ulvz_manual_translation.md
git status --short
grep -n "Only `docs/s40rts_ulvz_manual_translation.md` was created\." docs/s40rts_ulvz_manual_translation.md
git status --short
grep -n 'Only `docs/s40rts_ulvz_manual_translation.md` was created\.' docs/s40rts_ulvz_manual_translation.md
find docs -maxdepth 1 -type f -name 's40rts_ulvz_manual_translation.md' -print
grep -n '^| User-manual S20RTS concept |' docs/s40rts_ulvz_manual_translation.md
grep -n -i 'spiral' docs/s40rts_ulvz_manual_translation.md
find specfem3d_globe -path specfem3d_globe/.git -prune -o -type f -newer docs/s40rts_ulvz_manual_translation.md -print
grep -n 'zero-amplitude ULVZ\|point outside the ULVZ\|point inside the ULVZ\|taper continuity\|all MPI ranks\|S40RTS.dat.*P12.dat' docs/s40rts_ulvz_manual_translation.md
```

Only `docs/s40rts_ulvz_manual_translation.md` was created.
