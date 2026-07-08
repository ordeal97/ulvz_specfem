# ULVZ Model Post-Processing Guide

This is the authoritative user guide for the standalone
`ulvz_model_postprocess` package.

## Purpose

The package post-processes compatible SPECFEM3D_GLOBE `DATABASES_MPI` model
outputs from user-provided paths. It supports validation, one-model extraction,
delayed two-model comparison, static plotting, and ParaView export.

Use standalone commands:

```bash
ulvz-model-postprocess ...
python -m ulvz_model_postprocess ...
```

The old repository command remains available for backward compatibility:

```bash
python -m scripts.ulvz_model_postprocess --help
```

## Supported Inputs

Supported and verified:

```text
compatible local sequential reg1 isotropic/TISO proc*_reg1_solver_data.bin
```

Unsupported or unverified:

```text
ADIOS/HDF5
non-reg1
full anisotropic cij
standalone model arrays plus separate geometry
cross-mesh interpolation/resampling
true sub-rank record streaming
arbitrary incompatible SPECFEM binary layouts
production-scale/high-frequency validation
```

Pass complete `DATABASES_MPI` directories to `validate` and `extract`.
Pass extracted `model_manifest.json` products to `compare`, `plot`, and
`paraview`.

## Install Package

```bash
mamba create -n ulvz-post -c conda-forge \
  python=3.11 numpy pandas matplotlib scipy pytest vtk pyvista

conda activate ulvz-post

pip install -e /path/to/ulvz_specfem/packages/ulvz_model_postprocess
```

Static plotting should not require VTK/PyVista. ParaView export requires VTK.

## Install Extractor Into External SPECFEM

```bash
cd /path/to/specfem3d_globe

python /path/to/ulvz_model_postprocess_package/specfem_extension/install_extractor.py \
  --specfem-root . \
  --dry-run

python /path/to/ulvz_model_postprocess_package/specfem_extension/install_extractor.py \
  --specfem-root . \
  --apply

make xulvz_model_extract
```

Safe diagnostic usage check:

```bash
/path/to/specfem3d_globe/bin/xulvz_model_extract --help
```

The verified extractor may print usage and exit with code 2 for `--help`.

## Validate Arbitrary External Output

```bash
ulvz-model-postprocess validate \
  --model ulvz=/path/to/run/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --out-dir /path/to/postprocess/validate_ulvz
```

`validate` runs extractor inspection through the explicit `--extractor` and
writes inspection/validation metadata below `--out-dir`.

## Extract One Model

```bash
ulvz-model-postprocess extract \
  --model ulvz=/path/to/run/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --out-dir /path/to/postprocess/ulvz \
  --extract-mode full \
  --allow-large
```

Single-model products contain physical fields only. Ratios and differences are
created only by `compare`.

## Delayed Comparison

```bash
ulvz-model-postprocess compare \
  --reference reference=/path/to/postprocess/reference/model_manifest.json \
  --target ulvz=/path/to/postprocess/ulvz/model_manifest.json \
  --comparison-name ulvz_over_reference \
  --out-dir /path/to/postprocess/comparisons
```

Comparison orientation is fixed:

```text
ratio = target / reference
difference = target - reference
```

## Plot And ParaView

```bash
ulvz-model-postprocess plot \
  --input /path/to/postprocess/ulvz/model_manifest.json \
  --field vsv \
  --kind histogram \
  --out-dir /path/to/postprocess/ulvz/figures

ulvz-model-postprocess paraview \
  --input /path/to/postprocess/ulvz/model_manifest.json \
  --out-dir /path/to/postprocess/ulvz/paraview
```

The default ParaView export writes point-cloud products. Use
`--paraview-kind both` to write both point-cloud and linearized-mesh products.
ParaView users should normally open wrapper files:

```text
model_points.pvtp
model_linear_mesh.pvtu
```

Keep rank-local `.vtp/.vtu` pieces beside the wrappers.

## Command Reference

Use command help for the exact supported options:

```bash
ulvz-model-postprocess validate --help
ulvz-model-postprocess extract --help
ulvz-model-postprocess compare --help
ulvz-model-postprocess plot --help
ulvz-model-postprocess paraview --help
```

Important runtime rules:

- `validate` and `extract` require `--extractor` for raw `DATABASES_MPI`
  inputs.
- `extract --extract-mode full` requires `--allow-large`.
- `compare`, `plot`, and `paraview` require extracted manifest JSON files and
  reject raw `DATABASES_MPI` directories.
- All command outputs are written below the user-provided `--out-dir`.
