# ULVZ Model Post-Processing Guide

## Purpose

`scripts/ulvz_model_postprocess` is the production-oriented successor to the
Task 3E/3F fixture visualization tools. It is designed for external
SPECFEM3D_GLOBE `DATABASES_MPI` directories and uses schema:

```text
ulvz_model_postprocess.v1
```

The stable invocation is:

```bash
python -m scripts.ulvz_model_postprocess ...
```

## Input-path contracts

v1 accepts a complete local sequential `DATABASES_MPI` directory:

```bash
python -m scripts.ulvz_model_postprocess validate \
  --model ulvz=/path/to/DATABASES_MPI \
  --out-dir /path/to/output/validate_ulvz
```

The directory must contain files named like:

```text
proc000000_reg1_solver_data.bin
```

v1 rejects bare model files and separate model-data/geometry paths. Python
does not parse raw SPECFEM solver binaries.

## One-model workflow

Safe summary extraction:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extract-mode summary \
  --out-dir /path/to/output/ulvz_summary
```

Selected extraction writes physical model fields from supported local
sequential reg1 `solver_data.bin` files into the rank-local `.npy` store:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extract-mode selected \
  --memory-limit-mb 2048 \
  --out-dir /path/to/output/ulvz_selected
```

Task 4C extraction currently preserves all reg1 GLL records for the selected
product; ROI filtering and deterministic sub-sampling remain future work. The
command does not create ratio or difference fields.

Full extraction requires explicit large-output consent:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extract-mode full \
  --allow-large \
  --memory-limit-mb 2048 \
  --out-dir /path/to/output/ulvz_full
```

A single-model product contains native physical fields only. It does not
contain ratios.

## Delayed comparison workflow

Compare already extracted rank-store manifests:

```bash
python -m scripts.ulvz_model_postprocess compare \
  --reference reference=/path/to/reference/model_manifest.json \
  --target ulvz=/path/to/ulvz/model_manifest.json \
  --comparison-name ulvz_over_reference \
  --out-dir /path/to/output/comparisons
```

Orientation:

```text
ratio = target / reference
difference = target - reference
```

Selected products must have identical selection fingerprints. Full products
must have compatible mesh and geometry fingerprints.

Raw `DATABASES_MPI` directories are not valid inputs to `compare`, `plot`, or
`paraview`. Those commands require an extracted rank-store manifest such as
`model_manifest.json`.

## Rank-store layout

Full-resolution products use rank-local directories and separate `.npy`
arrays:

```text
model_manifest.json
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
  fields/rho.npy
  fields/vp.npy or fields/vpv.npy
  fields/vs.npy or fields/vsv.npy
```

Use memory mapping for large arrays:

```python
values = numpy.load("fields/vs.npy", mmap_mode="r")
```

Compressed NPZ is not the default production store.

## Units and fields

Stored coordinates use physical Cartesian kilometers:

```text
x_km, y_km, z_km
```

Normalized SPECFEM coordinates may also be retained:

```text
x_norm, y_norm, z_norm
```

Stored field units:

```text
rho: kg m^-3
vp, vs, vpv, vph, vsv, vsh: m s^-1
eta: dimensionless
```

Isotropic fields:

```text
vp = sqrt((kappa + 4 mu / 3) / rho) * velocity_scale
vs = sqrt(mu / rho) * velocity_scale
rho = rhostore * density_scale
```

TISO fields:

```text
vpv = sqrt((kappav + 4 muv / 3) / rho) * velocity_scale
vph = sqrt((kappah + 4 muh / 3) / rho) * velocity_scale
vsv = sqrt(muv / rho) * velocity_scale
vsh = sqrt(muh / rho) * velocity_scale
eta = eta_anisostore
```

Plots may display velocities in km/s, but stored products remain SI.

Task 4C records the SPECFEM scale factors in `model_manifest.json`:

```text
density_scale_to_kg_m-3 = EARTH_RHOAV
velocity_scale_to_m_s-1 = EARTH_R * sqrt(PI * GRAV * EARTH_RHOAV)
```

## Large-data safety

Default extraction mode is `summary`. v1 memory is bounded by one rank
database. A pre-read memory estimate must stay below `--memory-limit-mb`.

Defaults:

```text
--max-points 10000000
--max-cells 1000000
--max-points-per-rank 2000000
--memory-limit-mb 2048
```

Task 4C memory is bounded by one rank database. The extractor estimates peak
per-rank memory before model-array reads and fails clearly instead of silently
truncating.

The preserved Task 3D fixture acceptance recorded an estimated per-rank peak
of `150.519257 MB` against `--memory-limit-mb 1024`. The manifest field is
`estimated_peak_memory_*`; it is not a measured runtime peak RSS.

## Static plotting

Static plotting does not import VTK or PyVista:

```bash
export MPLBACKEND=Agg
export MPLCONFIGDIR=/tmp/ulvz_model_postprocess_mpl
export XDG_CACHE_HOME=/tmp/ulvz_model_postprocess_xdg

python -m scripts.ulvz_model_postprocess plot \
  --input /path/to/product/model_manifest.json \
  --field vs \
  --kind histogram \
  --out-dir /path/to/figures
```

Generic plots work without ULVZ geometry. ULVZ-centred plots are future work
unless ULVZ metadata is supplied.

## ParaView workflow

Point cloud:

```bash
python -m scripts.ulvz_model_postprocess paraview \
  --input /path/to/product/model_manifest.json \
  --paraview-kind points \
  --out-dir /path/to/paraview_points
```

Linear mesh:

```bash
python -m scripts.ulvz_model_postprocess paraview \
  --input /path/to/product/model_manifest.json \
  --paraview-kind linear-mesh \
  --max-cells 1000000 \
  --out-dir /path/to/paraview_mesh
```

`points` means a rank-piece PVTP GLL point cloud with native point fields.
`linear-mesh` means rank-piece PVTU linearized 8-corner hexahedra. The linear
mesh does not preserve the full high-order GLL field or curved spectral-element
geometry.

The current exporter writes one non-empty `.vtp` point-cloud piece per rank and
one `.pvtp` wrapper, or one non-empty `.vtu` linearized mesh piece per rank and
one `.pvtu` wrapper. Point-cloud fields are native GLL point fields.
Linear-mesh point fields are corner-node samples, and cell fields named
`*_mean` are per-element means of the GLL values. Comparison products export
only comparison fields such as `vsv_ratio` and `vsv_difference`.

The preserved Task 3D fixture acceptance reopened `model_points.pvtp` with
1,080,000 points and 1,080,000 vertex cells, and `model_linear_mesh.pvtu` with
583,242 points and 8,640 hexahedral cells. It recorded zero invalid or
zero-volume linearized cells.

## Common failures

- Bare file input: pass the complete `DATABASES_MPI` directory.
- Selected/full raw extraction failure: rebuild/use `xulvz_model_extract` from
  the compatible SPECFEM checkout and check `--memory-limit-mb`.
- Full extraction without `--allow-large`: add the flag intentionally.
- Selected comparison mismatch: re-extract with identical ROI and sampling.
- Missing VTK: static plotting still works; ParaView verification requires VTK.
- Unsupported raw layout: v1 supports only compatible local sequential reg1
  `solver_data.bin` layouts with isotropic or TISO fields. ADIOS/HDF5,
  non-reg1 regions, full anisotropic mantle `cij` export, standalone
  model-data paths, cross-mesh interpolation/resampling, true sub-rank record
  streaming, and arbitrary incompatible SPECFEM binary layouts remain out of
  scope.

## Tested preserved-fixture commands

The Task 4C repaired acceptance test uses the preserved Task 3D fixture only.
It does not run `xmeshfem3D`, `xspecfem3D`, or a production-scale model:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model reference=/import/freenas-m-01-seismology/xjiang/ulvz_specfem/specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/reference_disabled/DATABASES_MPI \
  --extract-mode full \
  --allow-large \
  --extractor specfem3d_globe/bin/xulvz_model_extract \
  --memory-limit-mb 1024 \
  --out-dir task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/reference_full

python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/import/freenas-m-01-seismology/xjiang/ulvz_specfem/specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/ulvz_enabled/DATABASES_MPI \
  --extract-mode full \
  --allow-large \
  --extractor specfem3d_globe/bin/xulvz_model_extract \
  --memory-limit-mb 1024 \
  --out-dir task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/ulvz_full

python -m scripts.ulvz_model_postprocess compare \
  --reference reference=task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/reference_full/model_manifest.json \
  --target ulvz=task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/ulvz_full/model_manifest.json \
  --comparison-name ulvz_over_reference \
  --out-dir task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/comparison
```

Acceptance report:

```text
task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/task_4c_real_fixture_acceptance.json
task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z/task_4c_real_fixture_acceptance.txt
```

The repaired acceptance reopened every generated VTP, VTU, PVTP, and PVTU file
with VTK, verified non-empty expected arrays, verified no invalid/zero-volume
linearized cells, and cross-checked ratios against the preserved Task 3D
per-GLL CSV evidence. The maximum Task 3D CSV ratio discrepancy was
`2.220446049250313e-16`.

Fresh regression results after the acceptance repair:

```text
tests/ulvz_model_postprocess: 15 passed
tests/ulvz_mesh_viz: 26 passed
```

Production-scale and high-frequency validation remain unverified.
