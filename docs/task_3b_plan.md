# Task 3B — Translate the S20RTS user-manual modification method to local S40RTS

This is a research-and-design task only.

Do not change SPECFEM source files.
Do not compile, mesh, or run simulations.
Do not propose SPiRaL changes in this task.

The goal is to determine exactly how the user-manual procedure for replacing or modifying `model_s20rts.f90` should be applied to the local S40RTS implementation in this repository.

The local SPECFEM version is:

```text
v8.1.0-323-g9c312cb2
commit 9c312cb2c991b47484a7f302775f4f01ed9470f8
```

The previous broad audit is available at:

```text
docs/model_reader_comparison_s40rts_spiral.md
```

Read and compare these local files directly:

```text
doc/USER_MANUAL/12_changing_the_model.tex
src/meshfem3D/model_s20rts.f90
src/meshfem3D/model_s40rts.f90
src/meshfem3D/meshfem3D_models.F90
src/meshfem3D/meshfem3D_models.f90 or equivalent dispatch files if present
src/shared/get_model_parameters.F90
src/meshfem3D/rules.mk
```

Create exactly one new document:

```text
docs/s40rts_ulvz_manual_translation.md
```

Do not modify any other file.

## Required analysis

### 1. Explain the version mismatch in the manual

The manual describes S20RTS with a `D3MM_V` structure. Verify whether that structure is actually an argument of the local S20RTS and S40RTS routines.

State clearly:

* whether `D3MM_V` exists in the current local S40RTS interface;
* where S40RTS model arrays are actually stored;
* the exact signatures of:

  * `model_s40rts_broadcast`
  * `read_model_s40rts`
  * `mantle_s40rts`
* which parts of the manual remain directly applicable despite this implementation difference.

Do not merely state that the manual is outdated. Explain the concrete local equivalent of each requirement.

### 2. Build a manual-to-S40RTS mapping table

Create a table with these columns:

| User-manual S20RTS concept | Old/manual S20RTS name | Local S40RTS equivalent | Required action for an S40RTS+ULVZ model | Evidence |
| -------------------------- | ---------------------- | ----------------------- | ---------------------------------------- | -------- |

It must include at least:

* model source file;
* broadcast routine;
* model-reading routine;
* mantle-evaluation routine;
* model arrays;
* spline arrays;
* spherical-harmonic degree;
* S-wave coefficient file;
* P-wave coefficient file;
* rank-0 file reading;
* MPI broadcasting;
* relative `dvs`, `dvp`, `drho` outputs;
* final multiplication of velocity and density perturbations into the 1-D reference model.

For every row, give local source-file line references.

### 3. Identify the exact ULVZ insertion point

Trace the exact calculation path for S40RTS:

```text
read S40RTS/P12 coefficients
→ construct radial splines
→ evaluate spherical-harmonic S40RTS perturbations
→ obtain dvs, dvp, drho
→ combine with the PREM background model
```

Identify two possible insertion points:

A. Inside `mantle_s40rts`, after the native S40RTS `dvs`, `dvp`, and `drho` have been computed but before the routine returns.

B. In the S40RTS branch of the generic mantle-model dispatcher, after `mantle_s40rts()` returns but before the perturbations are multiplied into `vpv`, `vph`, `vsv`, `vsh`, and `rho`.

Compare these two choices. Recommend one for a first ULVZ implementation and explain why.

The recommendation must explicitly consider the user manual’s “replace the model routine but preserve the call structure” approach.

### 4. Derive the perturbation-combination equations

Assume an analytical ULVZ taper weight `w`, where:

```text
w = 0 outside the ULVZ
w = 1 inside the ULVZ core
0 < w < 1 within the boundary taper
```

Let `dvs_s40`, `dvp_s40`, and `drho_s40` be the perturbations returned by the native S40RTS implementation.

Derive and explain two distinct conventions:

A. ULVZ perturbations relative to the local S40RTS background.

B. ULVZ perturbations relative to the 1-D PREM background.

For convention A, derive the correct formula for the final perturbation returned by a modified `mantle_s40rts` routine. It must satisfy:

```text
outside ULVZ: original S40RTS is unchanged
inside ULVZ: ULVZ perturbation is relative to local S40RTS velocity/density
```

Check the formula with this numerical example:

```text
dvs_s40 = +0.03
dvs_ulvz = -0.20
w = 1
```

Do not assume that simple addition is automatically correct.

State which convention should be used for the first ULVZ parameter sweep and why.

### 5. Determine the smallest modification compatible with the manual

Describe the minimal source-level design for a prototype that keeps:

```text
MODEL = s40rts
```

and modifies only the S40RTS implementation in the same spirit as the S20RTS user-manual replacement method.

Specify:

* which subroutine would calculate the analytical ULVZ geometry;
* where ULVZ parameters would reside;
* whether they can initially be hard-coded;
* whether a new file read requires changes to `model_s40rts_broadcast`;
* exactly which parameters must be broadcast when parameters are read only by rank 0;
* whether the existing S40RTS data-array broadcast remains unchanged.

Then describe the safer production design:

```text
MODEL = s40rts_ulvz
```

List every additional source file that would need modification for this named model variant.

Do not write code or patches yet.

### 6. Geometry and coordinate requirements

State the local S40RTS coordinate convention used by `mantle_s40rts`:

* radius;
* colatitude;
* longitude;
* units;
* radial domain.

Then state the required conversion for a ULVZ specified by:

```text
center latitude [degrees]
center longitude [degrees]
CMB height/thickness [km]
lateral radius [km]
boundary-taper width [km]
```

Explain how the implementation should prevent the ULVZ from extending below the CMB.

### 7. Required conclusion

Finish with exactly these sections:

```text
Recommended prototype route
Recommended production route
Minimal future code changes
Scientific convention to decide before implementation
Verification tests required before the first forward run
```

The verification tests must include:

1. zero-amplitude ULVZ reproduces native S40RTS;
2. a point outside the ULVZ reproduces native S40RTS;
3. a point inside the ULVZ has the analytically expected perturbation;
4. taper continuity;
5. all MPI ranks receive identical ULVZ parameters;
6. the original `DATA/s40rts/S40RTS.dat` and `DATA/s20rts/P12.dat` remain unmodified.

At the end, state every shell command used for inspection and confirm that only `docs/s40rts_ulvz_manual_translation.md` was created.
