# Task 4C SPECFEM Solver-Data Physical-Field Extraction Plan

Post-acceptance status: Task 4C has been implemented and verified on the
preserved Task 3D real fixture for compatible local sequential reg1
isotropic/TISO `proc*_reg1_solver_data.bin` layouts. The repaired acceptance
artifact is:

```text
task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/
```

That acceptance verified external `DATABASES_MPI` paths, full extraction,
delayed comparison, static plotting, ParaView point-cloud and linearized-mesh
export, VTK reopening, and Task 3D CSV consistency. It recorded per-rank
estimated peak memory `150.519257 MB` under a 1024 MB limit,
`model_points.pvtp` with 1,080,000 points and 1,080,000 vertex cells,
`model_linear_mesh.pvtu` with 583,242 points and 8,640 hexahedral cells, zero
invalid or zero-volume linearized cells, and maximum Task 3D CSV ratio
discrepancy `2.220446049250313e-16`. Production-scale/high-frequency
validation, ADIOS/HDF5, non-reg1 extraction, full anisotropic `cij`,
standalone model-data paths, cross-mesh interpolation, true sub-rank record
streaming, and arbitrary incompatible SPECFEM binary layouts remain unsupported
or unverified.

## Scope

Task 4C is the next implementation milestone required before the reusable
post-processing package can process real external waveform-simulation model
databases.

Goal:

```text
Extract physical model fields from compatible SPECFEM proc*_reg1_solver_data.bin
files into rank-local ulvz_model_postprocess.v1 .npy products.
```

Task 4C must preserve the Task 4B boundaries:

- Python must not parse raw SPECFEM solver binaries.
- Raw binary reading stays in a SPECFEM-compiled Fortran utility.
- The extractor must reject incompatible or unrecognized layouts before model
  array reads.
- Tests must use preserved small fixtures before any production model.

## First planning step

Before implementation, inspect and document the local SPECFEM source for:

- exact record order in `proc*_reg1_solver_data.bin`;
- all supported isotropic and TISO records;
- unsupported full-anisotropic, ADIOS, and non-reg1 layouts;
- `CUSTOM_REAL` and unformatted-record layout validation;
- expected versus observed record lengths where available;
- physical scaling to SI fields;
- rank-local bounded-memory estimates;
- tests based on the preserved Task 3D fixture.

Required source files to inspect:

```text
specfem3d_globe/src/meshfem3D/save_arrays_solver.f90
specfem3d_globe/src/specfem3D/read_arrays_solver.f90
specfem3d_globe/src/auxiliaries/extract_database.f90
specfem3d_globe/src/shared/create_name_database.f90
specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90
```

## Required field contract

Stored products must use:

```text
coordinates: km
density: kg m^-3
velocities: m s^-1
```

Isotropic fields:

```text
rho = rhostore * density_scale_to_kg_m-3
vp = sqrt((kappav + 4*muv/3) / rhostore) * velocity_scale_to_m_s-1
vs = sqrt(muv / rhostore) * velocity_scale_to_m_s-1
```

TISO fields:

```text
rho = rhostore * density_scale_to_kg_m-3
vpv = sqrt((kappav + 4*muv/3) / rhostore) * velocity_scale_to_m_s-1
vph = sqrt((kappah + 4*muh/3) / rhostore) * velocity_scale_to_m_s-1
vsv = sqrt(muv / rhostore) * velocity_scale_to_m_s-1
vsh = sqrt(muh / rhostore) * velocity_scale_to_m_s-1
eta = eta_anisostore
```

The implementation must record scale factors, source SPECFEM constants,
field units, and derivation provenance in metadata.

## Bounded-memory design

Task 4C memory is bounded by one rank database. Before reading model arrays,
the extractor must estimate peak memory for:

- coordinates;
- topology;
- metric records that must be skipped or validated;
- physical field arrays;
- output `.npy` arrays.

If the estimate exceeds `--memory-limit-mb`, fail before model-array reads.
A true record-streaming solver-data reader remains out of scope unless it is
designed and tested in this task.

## Test and validation strategy

Required tests:

- exact reg1 record-order documentation test or fixture manifest check;
- isotropic synthetic extraction;
- TISO synthetic extraction;
- unsupported layout rejection;
- `CUSTOM_REAL`/layout mismatch rejection;
- physical unit and scaling checks;
- rank-local `.npy` output with `mmap_mode="r"`;
- memory-limit pre-read failure;
- preserved Task 3D fixture smoke test before any production model.

Preserved fixture smoke test must use:

```text
specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444
```

Automated tests must not require a high-frequency production simulation.

## Acceptance criteria

Task 4C is complete only when:

- `extract --extract-mode selected` can write physical fields from a compatible
  preserved fixture into rank-local `.npy` products;
- `extract --extract-mode full --allow-large` is implemented with explicit
  memory checks;
- comparison, plotting, and ParaView work from those extracted products;
- incompatible raw layouts fail before model-array reads;
- Task 3E/3F tests remain unchanged and passing.
