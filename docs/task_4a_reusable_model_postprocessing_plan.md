# Task 4A Reusable Model Post-Processing Plan

Post-Task-4C status note: this planning document is retained as historical
design context. Task 4C has since implemented and verified physical-field
extraction for compatible local sequential reg1 isotropic/TISO
`proc*_reg1_solver_data.bin` databases on the preserved Task 3D fixture. The
verified workflow is external `DATABASES_MPI` paths to full extraction,
delayed comparison, static plotting, ParaView point-cloud and linearized-mesh
export, and VTK reopening. Production-scale/high-frequency validation and
unsupported layouts remain out of scope as documented in
`docs/project_status.md` and `docs/ulvz_model_postprocessing_guide.md`.

## 1. Scope and non-goals

Task 4A defines a reusable package:

```text
scripts/ulvz_model_postprocess/
```

The package post-processes external SPECFEM3D_GLOBE `DATABASES_MPI`
directories. It supports one-model summary extraction, selected or full
rank-local products, delayed comparison, static plotting, and ParaView export.

Non-goals for v1:

- no production forward-solver behavior changes;
- no Python parser for raw SPECFEM solver binaries;
- no fixed input paths under `specfem3d_globe/tests/`;
- no single-model ratios or fabricated ratio defaults;
- no interpolation or resampling between incompatible meshes;
- no default monolithic CSV, compressed NPZ, global pandas concatenation, or
  global welded VTK mesh;
- no v1 standalone `--model-data` plus `--geometry-database` interface.

## 2. Why Task 3E/3F cannot simply be reused unchanged

Task 3E/3F is a lightweight fixture workflow. It assumes paired disabled and
enabled Task 3D databases, fixture ULVZ geometry, ratio fields, and schema
`ulvz_mesh_viz.v1`.

Task 4A needs external model paths, one-model workflows, delayed comparison,
rank-local memory-mappable storage, and a separate schema:

```text
ulvz_model_postprocess.v1
```

Reusable pieces are limited to patterns: argparse CLIs, JSON sidecars,
static plotting without VTK imports, and rank-piece ParaView output concepts.

## 3. User workflows

Run from the repository root:

```bash
python -m scripts.ulvz_model_postprocess ...
```

Validate an input database:

```bash
python -m scripts.ulvz_model_postprocess validate \
  --model ulvz=/path/to/DATABASES_MPI \
  --out-dir /path/to/output/validate_ulvz
```

Default safe summary extraction:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extract-mode summary \
  --out-dir /path/to/output/ulvz_summary
```

Selected extraction:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extract-mode selected \
  --region near-cmb \
  --cmb-window-km 0,160 \
  --sample stride \
  --sample-stride 20 \
  --out-dir /path/to/output/ulvz_selected
```

Full extraction:

```bash
python -m scripts.ulvz_model_postprocess extract \
  --model ulvz=/path/to/DATABASES_MPI \
  --extract-mode full \
  --allow-large \
  --memory-limit-mb 8192 \
  --out-dir /path/to/output/ulvz_full
```

Delayed comparison:

```bash
python -m scripts.ulvz_model_postprocess compare \
  --reference reference=/path/to/reference/model_manifest.json \
  --target ulvz=/path/to/ulvz/model_manifest.json \
  --comparison-name ulvz_over_reference \
  --out-dir /path/to/output/comparisons
```

## 4. Input contracts

Supported in v1:

- A complete local sequential SPECFEM `DATABASES_MPI` directory.
- The directory must contain files such as
  `proc000000_reg1_solver_data.bin`.
- Geometry, topology, and model arrays come from the same database directory.
- All package outputs go under `--out-dir`.

Rejected in v1:

- bare model files such as isolated `rho.bin`, `kappa.bin`, or `mu.bin`;
- separate model-data plus geometry paths;
- ADIOS databases;
- paths that require sibling-directory inference.

Standalone model-data plus explicit geometry is future work unless local
SPECFEM inspection identifies a stable documented format.

## 5. Proposed package layout

```text
scripts/ulvz_model_postprocess/
  __init__.py
  __main__.py
  cli.py
  input_contracts.py
  extract.py
  rank_store.py
  compare.py
  paraview.py
  plotting.py
  schema.py
  errors.py
```

Future implementation may add `fortran_runner.py`, `compatibility.py`,
`fields.py`, `geometry.py`, `sampling.py`, and `provenance.py` as the raw
extractor protocol is expanded.

## 6. Fortran extraction utility architecture

Python must not guess raw SPECFEM binary layouts. The v1 boundary is:

```text
specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
make xulvz_model_extract
```

The extractor must be compiled from a SPECFEM checkout/configuration
compatible with the database producer. It records:

- extractor source/build identity;
- `CUSTOM_REAL` representation;
- GLL dimensions;
- layout signature;
- expected versus observed prefix records;
- rank/region inventory.

The current utility supports conservative layout inspection before any
model-array reads. Full raw-to-rank-store extraction remains gated on a
recognized layout signature.

## 7. Portable intermediate schema

Default full-resolution store:

```text
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
      vp.npy
      vs.npy
      vpv.npy
      vph.npy
      vsv.npy
      vsh.npy
      eta.npy
summaries/
  fields_summary.csv.gz
  radial_summary.csv.gz
```

Only available fields are written. Arrays are separate `.npy` files so Python
can use:

```python
numpy.load(path, mmap_mode="r")
```

Compressed NPZ is archival/export-only, not the standard production store.

## 8. Comparison contract and compatibility checks

Orientation:

```text
ratio = target / reference
difference = target - reference
```

Comparison requires matching:

- schema version;
- extraction mode;
- ROI definition;
- sampling rule;
- selection fingerprint;
- rank inventory;
- region layout;
- element counts and GLL dimensions;
- topology fingerprint;
- geometry fingerprint;
- field availability and units;
- coordinate units;
- model field scaling convention.

`summary` products support summary-level comparison only. `selected` products
require identical selection fingerprints. `full` products require compatible
full rank stores.

## 9. Large-model performance and storage strategy

v1 memory is bounded by one rank database, not arbitrary global streaming.
Before reading a rank, the extractor/driver must estimate peak memory from
rank dimensions, geometry arrays, topology arrays, selected fields, and output
arrays. If the estimate exceeds `--memory-limit-mb`, fail before model-array
reads.

Safe defaults:

```text
--extract-mode summary
--max-points 10000000
--max-cells 1000000
--max-points-per-rank 2000000
--memory-limit-mb 2048
--sample none
--paraview-kind points
--weld-coordinates false
```

There is no silent truncation. Full extraction requires `--allow-large`.

## 10. Plotting and ParaView design

Static plotting must not import VTK or PyVista.

Generic single-model plots include histograms, radial summaries, vertical
sections, horizontal/CMB-near slices, and sampling diagnostics. ULVZ-centred
plots activate only when ULVZ geometry metadata is supplied.

ParaView kinds:

- `points`: rank-piece PVTP GLL point cloud with native point fields.
- `linear-mesh`: rank-piece PVTU linearized 8-corner hexahedra.
- `both`: write both metadata/product families.

The linear mesh is for visualization. It does not preserve the full high-order
GLL basis or curved spectral-element geometry.

## 11. CLI specification with examples

The stable invocation is:

```bash
python -m scripts.ulvz_model_postprocess SUBCOMMAND ...
```

Examples are listed in Sections 3 and 10. Direct `cli.py` execution is not the
documented interface.

## 12. Validation and test plan

Use:

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python
```

Headless plotting environment:

```bash
export MPLBACKEND=Agg
export MPLCONFIGDIR=/tmp/ulvz_model_postprocess_mpl
export XDG_CACHE_HOME=/tmp/ulvz_model_postprocess_xdg
```

Core checks:

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m pytest tests/ulvz_model_postprocess -q

/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m pytest tests/ulvz_mesh_viz -q
```

VTK availability check:

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -c "import vtkmodules; print('vtk ok')"
```

## 13. Documentation plan

Implementation creates:

```text
docs/ulvz_model_postprocessing_guide.md
docs/task_4b_reusable_model_postprocessing.md
```

The guide documents input contracts, one-model workflows, delayed comparison,
large-data safety, region/sampling choices, units, field formulas, ParaView
semantics, schema compatibility, and common failures.

## 14. Migration and non-regression strategy for Task 3E/3F

Task 3E/3F remains separate:

- keep existing CLIs;
- keep `ulvz_mesh_viz.v1`;
- do not reinterpret fixture products as production products;
- keep static plotting no-VTK behavior;
- run existing `tests/ulvz_mesh_viz/` unchanged.

## 15. Open design questions requiring inspection of local SPECFEM source

- Full raw model-array export protocol from `solver_data.bin` to `.npy`.
- Regions beyond `reg1`.
- ADIOS support.
- Full anisotropic mantle support.
- Stable standalone model-array format, if any.
- Cross-compiler unformatted record-marker handling for stronger record-length
  checks.

## 16. Proposed implementation phases and changed-files list

Implemented initial files:

```text
scripts/ulvz_model_postprocess/
tests/ulvz_model_postprocess/test_ulvz_model_postprocess.py
specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
specfem3d_globe/src/auxiliaries/rules.mk
specfem3d_globe/Makefile
docs/task_4a_reusable_model_postprocessing_plan.md
docs/ulvz_model_postprocessing_guide.md
docs/task_4b_reusable_model_postprocessing.md
```

Future phases complete raw model-array extraction after the extractor protocol
is extended and validated on real SPECFEM databases.
