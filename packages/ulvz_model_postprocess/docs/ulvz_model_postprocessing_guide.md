# ULVZ Model Post-Processing Guide

This is the authoritative user manual for standalone-package usage of
`ulvz_model_postprocess`. The repository-level guide at
`docs/ulvz_model_postprocessing_guide.md` is the in-repository and migration
copy; do not maintain these as two divergent long-term manuals.

Use standalone entry points:

```bash
ulvz-model-postprocess ...
python -m ulvz_model_postprocess ...
```

The old in-repository entry point remains available during migration only:

```bash
python -m scripts.ulvz_model_postprocess --help
```

## 1. Purpose

The standalone package post-processes compatible SPECFEM3D_GLOBE
`DATABASES_MPI` model databases from user-provided paths. It supports
raw-database validation through a compatible extractor, one-model physical
field extraction, delayed two-model comparison, static plotting, and ParaView
export.

The package is copyable outside the original `ulvz_specfem` repository. It
does not require commands to run from the old repository root.

## 2. Supported and unsupported inputs

| Status | Inputs |
| --- | --- |
| Supported | External `DATABASES_MPI` directories containing compatible local sequential `proc*_reg1_solver_data.bin` files |
| Supported | Isotropic and TISO reg1 layouts verified by Task 4C/4E fixture workflows |
| Unsupported / unverified | ADIOS/HDF5 databases, non-reg1 extraction, full anisotropic `cij` export, standalone model arrays plus separate geometry, cross-mesh interpolation/resampling, true sub-rank record streaming, arbitrary incompatible SPECFEM binary layouts, production-scale/high-frequency validation |

Pass complete `DATABASES_MPI` directories, not bare solver files, to
`validate` and `extract`. Labels are user-defined, for example
`reference=/path/to/DATABASES_MPI` or `ulvz=/path/to/DATABASES_MPI`.

Pass extracted manifests to `compare`, `plot`, and `paraview`:

```text
model_manifest.json
comparison_name_manifest.json
```

## 3. Installation and environment

Example conda environment:

```bash
mamba create -n ulvz-post -c conda-forge \
  python=3.11 numpy pandas matplotlib scipy pytest vtk pyvista

conda activate ulvz-post
export MPLBACKEND=Agg
```

Install the standalone package:

```bash
pip install -e /path/to/ulvz_specfem/packages/ulvz_model_postprocess
```

If running from the repository root during development, this is the package
path:

```bash
pip install -e packages/ulvz_model_postprocess
```

On headless servers, also use writable Matplotlib/cache directories:

```bash
export MPLCONFIGDIR=/tmp/ulvz_model_postprocess_mpl
export XDG_CACHE_HOME=/tmp/ulvz_model_postprocess_xdg
```

Static plotting uses Matplotlib and should not require VTK or PyVista.
ParaView export uses VTK Python modules.

## 4. SPECFEM extractor setup

The Python package does not guess or directly parse raw SPECFEM binary
layouts. Any real raw `DATABASES_MPI` validation or extraction requires an
explicit compatible extractor:

```bash
--extractor /path/to/specfem3d_globe/bin/xulvz_model_extract
```

The standalone package bundles the SPECFEM extractor extension under:

```text
packages/ulvz_model_postprocess/specfem_extension/
```

Use its README as the extractor installation guide:

```text
packages/ulvz_model_postprocess/specfem_extension/README.md
```

Helper-based installation into an external compatible SPECFEM checkout:

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

The current verified extractor may print usage and exit with code 2 for
`--help`; treat this as a safe usage/diagnostic command, not as a required
zero-exit success test.

## 5. Quick start

Validate an external output:

```bash
ulvz-model-postprocess validate \
  --model ulvz=/path/to/run/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --out-dir /path/to/postprocess/validate_ulvz
```

Extract one model:

```bash
ulvz-model-postprocess extract \
  --model ulvz=/path/to/run/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --extract-mode full \
  --allow-large \
  --memory-limit-mb 2048 \
  --out-dir /path/to/postprocess/ulvz_full
```

Plot a field:

```bash
ulvz-model-postprocess plot \
  --input /path/to/postprocess/ulvz_full/model_manifest.json \
  --field vsv \
  --kind histogram \
  --out-dir /path/to/postprocess/figures
```

Export ParaView products:

```bash
ulvz-model-postprocess paraview \
  --input /path/to/postprocess/ulvz_full/model_manifest.json \
  --paraview-kind both \
  --out-dir /path/to/postprocess/paraview_ulvz
```

Equivalent module form:

```bash
python -m ulvz_model_postprocess validate --help
python -m ulvz_model_postprocess extract --help
python -m ulvz_model_postprocess compare --help
python -m ulvz_model_postprocess plot --help
python -m ulvz_model_postprocess paraview --help
```

## 6. Command reference

### `validate`

| Item | Value |
| --- | --- |
| Purpose | Check that a raw input path satisfies the v1 `DATABASES_MPI` contract and run extractor inspection |
| Required inputs | `--model label=/path/to/DATABASES_MPI`, `--extractor /path/to/xulvz_model_extract`, `--out-dir /path/to/output` |
| Common options | `--extract-mode summary`, `--memory-limit-mb` |
| Output | `input_validation.json`, `extractor_inspect/extractor_layout_manifest.json`, summary-mode `model_manifest.json` |
| Example | `ulvz-model-postprocess validate --model ulvz=/path/to/DATABASES_MPI --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract --out-dir /path/to/output/validate_ulvz` |

### `extract`

| Item | Value |
| --- | --- |
| Purpose | Extract model metadata or physical fields into a rank-local store |
| Required inputs | `--model label=/path/to/DATABASES_MPI`, `--extractor /path/to/xulvz_model_extract`, `--out-dir /path/to/output` |
| Common options | `--extract-mode {summary,selected,full}`, `--allow-large`, `--memory-limit-mb`, `--max-points`, `--max-points-per-rank`, `--max-cells` |
| Output | `input_validation.json`, `model_manifest.json`, rank-local `.npy` arrays for selected/full physical extraction |
| Example | `ulvz-model-postprocess extract --model ulvz=/path/to/DATABASES_MPI --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract --extract-mode full --allow-large --out-dir /path/to/output/ulvz_full` |

### `compare`

| Item | Value |
| --- | --- |
| Purpose | Compare two already extracted compatible manifests |
| Required inputs | `--reference label=/path/to/reference/model_manifest.json`, `--target label=/path/to/target/model_manifest.json`, `--comparison-name NAME`, `--out-dir /path/to/output` |
| Common options | None beyond required inputs |
| Output | `NAME_manifest.json`, rank-local ratio and difference arrays |
| Example | `ulvz-model-postprocess compare --reference reference=/path/to/ref/model_manifest.json --target ulvz=/path/to/ulvz/model_manifest.json --comparison-name ulvz_over_reference --out-dir /path/to/output/comparison` |

### `plot`

| Item | Value |
| --- | --- |
| Purpose | Make static Matplotlib plots without importing VTK/PyVista |
| Required inputs | `--input /path/to/model_or_comparison_manifest.json`, `--field FIELD`, `--out-dir /path/to/figures` |
| Common options | `--kind {histogram,radial-summary}` |
| Output | PNG figure named from plot kind and field |
| Example | `ulvz-model-postprocess plot --input /path/to/product/model_manifest.json --field vsv --kind histogram --out-dir /path/to/figures` |

### `paraview`

| Item | Value |
| --- | --- |
| Purpose | Export rank-piece VTK XML products and ParaView wrapper files |
| Required inputs | `--input /path/to/model_or_comparison_manifest.json`, `--out-dir /path/to/paraview_output` |
| Common options | `--paraview-kind {points,linear-mesh,both}`, `--max-cells`, optional `--weld-coordinates`, `--weld-tolerance-km` |
| Output | `.vtp`/`.pvtp` point-cloud products and/or `.vtu`/`.pvtu` linearized mesh products |
| Example | `ulvz-model-postprocess paraview --input /path/to/product/model_manifest.json --paraview-kind both --out-dir /path/to/paraview` |

## 7. Single-model workflow

Single-model products contain physical fields only. They do not contain ratio
or difference arrays.

```bash
ulvz-model-postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --extract-mode full \
  --allow-large \
  --memory-limit-mb 2048 \
  --out-dir /path/to/output/ulvz_full
```

Plot one available field from the extracted manifest:

```bash
ulvz-model-postprocess plot \
  --input /path/to/output/ulvz_full/model_manifest.json \
  --field vsv \
  --kind histogram \
  --out-dir /path/to/output/figures
```

Export a single-model ParaView product:

```bash
ulvz-model-postprocess paraview \
  --input /path/to/output/ulvz_full/model_manifest.json \
  --paraview-kind points \
  --out-dir /path/to/output/paraview_points
```

Actual fields depend on the database layout. Isotropic products contain
`rho`, `vp`, and `vs`. TISO products contain `rho`, `vpv`, `vph`, `vsv`,
`vsh`, and `eta`.

## 8. Delayed two-model comparison workflow

Extract the reference and target independently, then compare the extracted
manifests later. Do not pass raw `DATABASES_MPI` paths to `compare`.

```bash
ulvz-model-postprocess extract \
  --model reference=/path/to/reference/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --extract-mode full \
  --allow-large \
  --memory-limit-mb 2048 \
  --out-dir /path/to/output/reference_full

ulvz-model-postprocess extract \
  --model ulvz=/path/to/ulvz/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --extract-mode full \
  --allow-large \
  --memory-limit-mb 2048 \
  --out-dir /path/to/output/ulvz_full

ulvz-model-postprocess compare \
  --reference reference=/path/to/output/reference_full/model_manifest.json \
  --target ulvz=/path/to/output/ulvz_full/model_manifest.json \
  --comparison-name ulvz_over_reference \
  --out-dir /path/to/output/comparison
```

Comparison orientation is fixed:

```text
ratio = target / reference
difference = target - reference
```

Compatibility checks require matching schema, extraction mode, selection
fingerprint, units, scaling convention, rank inventory, topology, and geometry
fingerprints. Incompatible products fail before partial comparison products
are written.

## 9. Plotting examples

| Plot kind | Command | Output | When to use |
| --- | --- | --- | --- |
| `histogram` | `ulvz-model-postprocess plot --input /path/to/product/model_manifest.json --field vsv --kind histogram --out-dir /path/to/figures` | `histogram_vsv.png` | Quick field distribution and sanity checks |
| `radial-summary` | `ulvz-model-postprocess plot --input /path/to/product/model_manifest.json --field rho --kind radial-summary --out-dir /path/to/figures` | `radial-summary_rho.png` | Current static summary entry point for a field; inspect the generated figure before quantitative use |

Generic plots do not require ULVZ geometry metadata.

## 10. ParaView examples

Point-cloud output preserves native GLL point fields as a rank-piece point
cloud. Linearized mesh output creates an 8-corner hexahedral approximation for
visualization; it does not preserve the full high-order spectral-element
geometry or every interior GLL value as mesh vertices.

| Kind | Wrapper to open | Rank pieces kept next to wrapper | Semantics |
| --- | --- | --- | --- |
| `points` | `model_points.pvtp` | `*_points.vtp` | GLL point cloud, coordinates in km, native point fields |
| `linear-mesh` | `model_linear_mesh.pvtu` | `*_linear_mesh.vtu` | 8-corner hexahedra, coordinates in km, corner point values and `*_mean` cell arrays |
| `both` | Both wrappers | Both piece sets | Writes both products |

Users should normally open the wrapper files in ParaView:

```text
model_points.pvtp
model_linear_mesh.pvtu
```

The rank-local `.vtp` and `.vtu` files must stay next to the wrapper files and
should not be moved independently.

Single-model export:

```bash
ulvz-model-postprocess paraview \
  --input /path/to/output/ulvz_full/model_manifest.json \
  --paraview-kind both \
  --out-dir /path/to/output/paraview_ulvz
```

Comparison export:

```bash
ulvz-model-postprocess paraview \
  --input /path/to/output/comparison/ulvz_over_reference_manifest.json \
  --paraview-kind both \
  --out-dir /path/to/output/paraview_comparison
```

Comparison ParaView products contain comparison fields such as `vsv_ratio` and
`vsv_difference`; single-model ParaView products contain physical fields only.

## 11. Large-data safety

- Default extraction mode is `summary`.
- `validate` and `extract` require explicit `--extractor` for raw
  `DATABASES_MPI` inputs.
- `--extract-mode full` requires explicit `--allow-large`.
- Memory estimates are per rank and are recorded as `estimated_peak_memory_*`;
  they are not measured peak RSS.
- Selected/full extraction fails before model-array reads if the estimate
  exceeds `--memory-limit-mb`.
- Output is rank-local; the package does not silently truncate, interpolate,
  or resample incompatible meshes.
- Choose output directories outside the input `DATABASES_MPI` directory.
- Production-scale/high-frequency validation remains unverified.

Default safety-related options include:

```text
--memory-limit-mb 2048
--max-points 10000000
--max-points-per-rank 2000000
--max-cells 1000000
```

## 12. Output layout

Summary validation/extraction output:

```text
/path/to/output/validate_ulvz/
  input_validation.json
  model_manifest.json
  extractor_inspect/
    extractor_layout_manifest.json
```

Single-model output:

```text
/path/to/output/ulvz_full/
  input_validation.json
  model_manifest.json
  ranks/
    rank000000_reg1/
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
      fields/
        rho.npy
        vsv.npy
        ...
```

Comparison output:

```text
/path/to/output/comparison/
  ulvz_over_reference_manifest.json
  ranks/
    rank000000_reg1/
      metadata.json
      fields/
        rho_ratio.npy
        rho_difference.npy
        vsv_ratio.npy
        vsv_difference.npy
        ...
```

Figure and ParaView output:

```text
/path/to/output/figures/
  histogram_vsv.png

/path/to/output/paraview_ulvz/
  points_metadata.json
  model_points.pvtp
  rank000000_reg1_points.vtp
  linear_mesh_metadata.json
  model_linear_mesh.pvtu
  rank000000_reg1_linear_mesh.vtu
```

Acceptance or smoke-test reports may be stored separately as provenance, but
they are not required for normal user workflows.

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `validate` or `extract` fails with missing `--extractor` | Raw `DATABASES_MPI` validation/extraction always requires an explicit compatible extractor | Pass `--extractor /path/to/specfem3d_globe/bin/xulvz_model_extract` |
| `compare`, `plot`, or `paraview` rejects a directory | Raw `DATABASES_MPI` was passed instead of a manifest | Run `extract` first and pass `model_manifest.json` or the comparison manifest |
| Unsupported or incompatible layout error | Database is not a supported local sequential reg1 isotropic/TISO layout, or extractor build is incompatible | Rebuild `xulvz_model_extract` from the compatible SPECFEM checkout; verify the input layout |
| Full extraction fails before reading model arrays | `--extract-mode full` was used without `--allow-large` | Add `--allow-large` intentionally |
| Memory-limit rejection | Per-rank estimate exceeds `--memory-limit-mb` | Increase the limit only if the node has sufficient memory, or use summary mode |
| Missing extractor executable | The configured extractor path is absent or not a file | Install/build the extractor with `specfem_extension/install_extractor.py`, then pass its absolute path with `--extractor` |
| Matplotlib fails on a headless server | Backend or cache directory is not writable | Set `MPLBACKEND=Agg`, `MPLCONFIGDIR`, and `XDG_CACHE_HOME` |
| VTK reader opens empty output | Wrong file opened, wrapper/pieces moved apart, or export failed | Open `model_points.pvtp` or `model_linear_mesh.pvtu`; keep rank pieces next to the wrapper; rerun `paraview` |
| Comparison fails before output | Mesh, geometry, selection, units, or field compatibility mismatch | Re-extract both models with compatible settings from matching databases |

## 14. Capability boundary

```text
Status: implemented and verified on the preserved Task 3D fixture for
compatible local sequential reg1 isotropic/TISO proc*_reg1_solver_data.bin
layouts.

Verified workflow:
external DATABASES_MPI paths -> explicit extractor -> selected/full
extraction -> delayed comparison -> static plotting -> ParaView point cloud
and linearized mesh export.

Still unsupported or unverified:
ADIOS/HDF5 databases; non-reg1 extraction; full anisotropic cij export;
standalone model arrays plus separate geometry; cross-mesh interpolation or
resampling; true sub-rank record streaming; arbitrary incompatible SPECFEM
binary layouts; production-scale/high-frequency validation.
```
