# Task 4B Reusable Model Post-Processing Foundation

## Scope

Task 4B implements a foundation phase for the production-oriented
post-processing package:

```text
scripts/ulvz_model_postprocess/
```

It keeps Task 3E/3F unchanged and introduces schema:

```text
ulvz_model_postprocess.v1
```

Task 4B began as a foundation phase, not the complete reusable package for
real waveform simulations. Task 4C now extends that foundation with verified
physical-field extraction for the supported local reg1 `solver_data.bin`
layout described below.

## Implemented and verified

Stable package invocation:

```bash
python -m scripts.ulvz_model_postprocess
```

Subcommands:

```text
validate
extract
compare
plot
paraview
```

The Python package supports:

- complete `DATABASES_MPI` validation;
- safe `summary` extraction manifest generation;
- rank-local `.npy` product writing through the internal rank-store API;
- single-model products without ratio fields;
- delayed comparison with compatibility checks;
- ratio/difference arrays for already extracted compatible rank-store products;
- static histogram plotting without VTK imports;
- ParaView point-cloud and linear-mesh rank-piece products for already
  extracted rank-store products, with VTP/PVTP and VTU/PVTU reopening
  verification;
- layout inspection through `xulvz_model_extract --inspect`;
- Task 4C physical-field extraction from compatible local sequential
  `proc*_reg1_solver_data.bin` files into rank-local `.npy` products.

## Still not implemented or verified

The following remain explicitly outside the current verified capability:

- production-scale raw database extraction validation;
- ADIOS/HDF5 model databases;
- non-reg1 regions;
- full anisotropic mantle `cij` export;
- standalone model-data plus separate geometry paths;
- true record-streaming with memory below one rank database;
- cross-mesh interpolation or resampling.

Current CLI behavior reflects this boundary:

- `validate` may succeed for a complete `DATABASES_MPI` directory;
- `xulvz_model_extract --inspect` may succeed for layout inventory;
- `extract --extract-mode selected` and `extract --extract-mode full --allow-large`
  run physical-field extraction only through
  `xulvz_model_extract --extract-reg1`;
- `compare`, `plot`, and `paraview` support extracted rank-store manifests,
  not raw `DATABASES_MPI` paths.

## Rank-store format

The default store is a rank-local directory of `.npy` arrays:

```text
ranks/rank000000_reg1/
  metadata.json
  x_km.npy
  y_km.npy
  z_km.npy
  x_norm.npy
  y_norm.npy
  z_norm.npy
  ibool.npy
  idoubling.npy
  ispec_is_tiso.npy
  fields/*.npy
```

This supports:

```python
numpy.load(path, mmap_mode="r")
```

## Extractor status

Added SPECFEM auxiliary source:

```text
specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
```

Added build target:

```text
make xulvz_model_extract
```

The Fortran utility implements conservative layout inspection:

```bash
specfem3d_globe/bin/xulvz_model_extract --inspect DATABASES_MPI OUT_DIR
```

It records `CUSTOM_REAL`, GLL dimensions, layout signature, rank/region
inventory, and observed prefix records before any model-array reads.

Task 4C adds:

```bash
specfem3d_globe/bin/xulvz_model_extract --extract-reg1 \
  DATABASES_MPI OUT_DIR MODEL_LABEL EXTRACT_MODE MEMORY_LIMIT_MB
```

Supported extraction layout:

- local sequential Fortran unformatted `proc*_reg1_solver_data.bin`;
- record marker size observed through the compatible SPECFEM/gfortran runtime;
- `CUSTOM_REAL` matching the compiled extractor (`SIZE_REAL` or
  `SIZE_DOUBLE`);
- isotropic records `rhostore`, `kappavstore`, `muvstore`;
- TISO records `rhostore`, `kappavstore`, `muvstore`, `kappahstore`,
  `muhstore`, `eta_anisostore`.

The extractor validates each expected record marker before reading its payload
and fails before model-array reads if the per-rank peak-memory estimate exceeds
`--memory-limit-mb`. If a sibling `OUTPUT_FILES/values_from_mesher.h`
explicitly records `ANISOTROPIC_3D_MANTLE_VAL = .true.`, v1 rejects the
database before raw model-array extraction.

For the preserved Task 3D fixture, full extraction recorded per-rank estimated
peak memory of `150.519257 MB` against a 1024 MB configured limit. The
estimate is recorded as `estimated_peak_memory_*`; it is not a measured peak
RSS.

## Comparison contract

Compatibility requires matching:

- schema version;
- extraction mode;
- ROI;
- sampling rule;
- selection fingerprint;
- rank inventory;
- topology fingerprint;
- geometry fingerprint;
- field units;
- coordinate units;
- model field scaling convention.

Output orientation:

```text
ratio = target / reference
difference = target - reference
```

## Verification

Task 4B tests are under:

```text
tests/ulvz_model_postprocess/
```

Use:

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m pytest tests/ulvz_model_postprocess -q
```

Task 3E/3F non-regression:

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m pytest tests/ulvz_mesh_viz -q
```

Fortran layout-inspection smoke test:

```bash
specfem3d_globe/bin/xulvz_model_extract --inspect \
  specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/reference_disabled/DATABASES_MPI \
  /tmp/ulvz_model_extract_inspect_task4a
```

Observed output:

```text
/tmp/ulvz_model_extract_inspect_task4a/extractor_layout_manifest.json
```

The manifest recorded six files: two ranks for reg1, reg2, and reg3, with
`CUSTOM_REAL = SIZE_REAL` and `NGLLX/Y/Z = 5`.

Task 4C repaired acceptance evidence:

```text
task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/
```

The preserved-fixture acceptance ran full extraction of the independent
`reference_disabled` and `ulvz_enabled` `DATABASES_MPI` directories, delayed
comparison, single-model and comparison histogram plotting, point-cloud
ParaView export, and linearized-mesh ParaView export. VTK reopened every VTP,
VTU, PVTP, and PVTU product. The Task 4C comparison ratios matched the
preserved Task 3D per-GLL CSV evidence with maximum discrepancy
`2.220446049250313e-16`. This is a fixture consistency cross-check, not an
independent scientific validation.

Acceptance output sizes:

- `model_points.pvtp`: 1,080,000 points and 1,080,000 vertex cells.
- `model_linear_mesh.pvtu`: 583,242 points and 8,640 hexahedral cells.
- linearized-cell validation: zero invalid or zero-volume cells.

Fresh regression results after the acceptance repair:

- `tests/ulvz_model_postprocess`: `15 passed`.
- `tests/ulvz_mesh_viz`: `26 passed`.

Production-scale and high-frequency model validation remain unverified.

## Current limitations

v1 does not support:

- Python raw solver-binary parsing;
- standalone model-data plus geometry paths;
- ADIOS databases;
- non-reg1 extraction;
- full anisotropic mantle export;
- cross-mesh interpolation;
- true sub-rank record streaming;
- arbitrary incompatible SPECFEM binary layouts;
- default global welded ParaView meshes.
