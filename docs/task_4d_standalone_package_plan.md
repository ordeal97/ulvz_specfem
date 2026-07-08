# Task 4D Standalone Package Plan

## 1. Scope and goal

Task 4D plans the migration of the verified reusable ULVZ model
post-processing tools into a standalone Python package plus a bundled SPECFEM
extractor extension. This is a planning-only task: it does not implement the
standalone package, move files, modify production source, alter tests, change
generated artifacts, rewrite Git history, or update GitHub settings.

The final standalone package should be developed under:

```text
packages/ulvz_model_postprocess/
```

It must be self-contained and copyable outside the `ulvz_specfem` repository.
The final supported user entry points are:

```bash
ulvz-model-postprocess ...
python -m ulvz_model_postprocess ...
```

The package must process arbitrary user-provided SPECFEM `DATABASES_MPI`
paths. It must not depend on commands being run from the old repository root,
and it must not require sibling `ulvz_specfem/`, `scripts/`, or
`specfem3d_globe/` directories.

Task 4D must preserve the current capability boundary. Supported and verified
so far:

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

The plan must not broaden the supported SPECFEM database/layout contract beyond
the explicit verified layouts above.

## 2. Current coupling to `ulvz_specfem`

The current verified implementation lives under:

```text
scripts/ulvz_model_postprocess/
```

Current coupling points that must be removed from the standalone package:

- Python imports use `scripts.ulvz_model_postprocess.*`.
- The current stable in-repository invocation is:

  ```bash
  python -m scripts.ulvz_model_postprocess ...
  ```

- `extract.py` falls back to a repository-relative extractor:

  ```text
  specfem3d_globe/bin/xulvz_model_extract
  ```

- Current tests derive `REPO = Path(__file__).resolve().parents[2]` and use
  fixture and extractor paths under `REPO/specfem3d_globe/...`.
- Repository-level documentation currently gives examples from the old
  repository root.
- The SPECFEM extractor source and build-rule additions currently live inside
  the local SPECFEM checkout:

  ```text
  specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
  specfem3d_globe/src/auxiliaries/rules.mk
  ```

These are acceptable for the verified Task 4C implementation, but not for a
copyable standalone package.

## 3. Target standalone architecture

Task 4D separates the system into two explicit parts.

### A. Standalone Python package

The Python package provides:

```text
validate
extract
compare
plot
paraview
```

It owns:

- input-path validation for complete `DATABASES_MPI` directories;
- rank-local `.npy` product schema and metadata;
- comparison compatibility checks;
- ratio and difference generation only for explicit comparisons;
- static plotting;
- ParaView VTP/PVTP point-cloud and VTU/PVTU linearized-mesh export;
- clear user-facing failures for unsupported raw inputs.

It must write all outputs under user-provided `--out-dir`.

### B. SPECFEM extractor extension

The SPECFEM extractor extension provides a compiled boundary for reading raw
solver database files. Python must not directly guess or parse raw SPECFEM
binary layouts.

For physical-field extraction from real `DATABASES_MPI` directories, the
primary runtime interface is:

```bash
--extractor /path/to/specfem3d_globe/bin/xulvz_model_extract
```

An optional future convenience interface such as:

```bash
--specfem-root /path/to/specfem3d_globe
```

may be considered later, but it is not the primary Task 4D interface. The CLI
must fail clearly if selected/full extraction is requested without a compatible
extractor.

## 4. Python package layout under `packages/ulvz_model_postprocess/`

Proposed standalone tree:

```text
packages/
  ulvz_model_postprocess/
    pyproject.toml
    README.md
    src/
      ulvz_model_postprocess/
        __init__.py
        __main__.py
        cli.py
        input_contracts.py
        extract.py
        compare.py
        compatibility.py
        fields.py
        geometry.py
        sampling.py
        plotting.py
        paraview.py
        schema.py
        rank_store.py
        provenance.py
        errors.py
    specfem_extension/
      README.md
      src/
        auxiliaries/
          ulvz_model_extract.f90
      patches/
        add_xulvz_model_extract.patch
      install_extractor.py
    tests/
      test_ulvz_model_postprocess.py
    docs/
      ulvz_model_postprocessing_guide.md
```

Migration source:

```text
scripts/ulvz_model_postprocess/
```

The standalone package copy should rewrite imports from:

```python
from scripts.ulvz_model_postprocess...
```

to:

```python
from ulvz_model_postprocess...
```

`pyproject.toml` should define a console script entry point:

```toml
[project.scripts]
ulvz-model-postprocess = "ulvz_model_postprocess.cli:main"
```

The module entry point must support:

```bash
python -m ulvz_model_postprocess ...
```

The package must not include repo-root discovery as a normal runtime
dependency. For real extraction, users supply `--extractor`.

## 5. SPECFEM extractor extension layout

The standalone package should bundle source and installation materials for
adding the extractor to a compatible external SPECFEM3D_GLOBE checkout:

```text
packages/ulvz_model_postprocess/specfem_extension/
  README.md
  src/
    auxiliaries/
      ulvz_model_extract.f90
  patches/
    add_xulvz_model_extract.patch
  install_extractor.py
```

Source provenance:

- `specfem_extension/src/auxiliaries/ulvz_model_extract.f90` should be copied
  from the verified local source:

  ```text
  specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
  ```

- `specfem_extension/patches/add_xulvz_model_extract.patch` should capture
  only the required build-rule additions currently represented in:

  ```text
  specfem3d_globe/src/auxiliaries/rules.mk
  ```

The extension is not a production forward-solver behavior change. It is an
auxiliary utility that must be compiled from a SPECFEM checkout/configuration
compatible with the database producer.

## 6. Extractor installation into external SPECFEM

Recommended installation mechanism: provide both a patch and a helper script.
The helper is the primary user path because it can perform safety checks and
explain failures clearly.

Dry-run policy:

- `install_extractor.py` without `--apply` must behave as a dry-run.
- Dry-run must not modify an external SPECFEM checkout.
- `--apply` is required before copying source files or modifying build rules.

Required safety checks before applying:

- target SPECFEM root exists;
- `src/auxiliaries/rules.mk` exists; in short, `rules.mk exists` must be true
  before patching;
- `src/auxiliaries/ulvz_model_extract.f90` is not accidentally overwritten
  without explicit confirmation;
- the `xulvz_model_extract` build rule is not already present;
- patch context matches, or failure is reported clearly with no partial
  modification.

Example helper-script workflow:

```bash
cd /path/to/specfem3d_globe

python /path/to/ulvz_model_postprocess_package/specfem_extension/install_extractor.py \
  --specfem-root .

python /path/to/ulvz_model_postprocess_package/specfem_extension/install_extractor.py \
  --specfem-root . \
  --apply

make xulvz_model_extract

/path/to/specfem3d_globe/bin/xulvz_model_extract --help
```

Patch-only fallback instructions should also be documented in
`specfem_extension/README.md` for users who prefer to inspect and apply the
patch manually.

## 7. Runtime CLI and examples

### Install Python package

```bash
mamba create -n ulvz-post -c conda-forge \
  python=3.11 numpy pandas matplotlib scipy pytest vtk pyvista

conda activate ulvz-post

pip install -e /path/to/ulvz_specfem/packages/ulvz_model_postprocess
```

Static plotting should not require VTK or PyVista. ParaView export requires
VTK Python modules.

### Install extractor into SPECFEM

```bash
cd /path/to/specfem3d_globe

python /path/to/ulvz_model_postprocess_package/specfem_extension/install_extractor.py \
  --specfem-root .

python /path/to/ulvz_model_postprocess_package/specfem_extension/install_extractor.py \
  --specfem-root . \
  --apply

make xulvz_model_extract
```

### Validate an arbitrary external SPECFEM output

```bash
ulvz-model-postprocess validate \
  --model ulvz=/path/to/run/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --out-dir /path/to/postprocess/validate_ulvz
```

### Extract one external model

```bash
ulvz-model-postprocess extract \
  --model ulvz=/path/to/run/DATABASES_MPI \
  --extractor /path/to/specfem3d_globe/bin/xulvz_model_extract \
  --out-dir /path/to/postprocess/ulvz \
  --extract-mode full \
  --allow-large
```

### Delayed comparison

```bash
ulvz-model-postprocess compare \
  --reference reference=/path/to/postprocess/reference/model_manifest.json \
  --target ulvz=/path/to/postprocess/ulvz/model_manifest.json \
  --comparison-name ulvz_over_reference \
  --out-dir /path/to/postprocess/comparisons
```

Comparison orientation:

```text
ratio = target / reference
difference = target - reference
```

### Plot and ParaView

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

ParaView users should normally open wrapper files:

```text
model_points.pvtp
model_linear_mesh.pvtu
```

Rank-local `.vtp` and `.vtu` pieces must remain beside the wrapper files.

## 8. Compatibility and safety contract

The standalone package inherits the Task 4C verified contract.

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

Safety requirements:

- Python must not directly parse raw SPECFEM binary files.
- Selected/full real extraction must go through a compatible
  `xulvz_model_extract`.
- All outputs must be written under user-provided `--out-dir`.
- Single-model extraction must create only physical fields, not ratios or
  differences.
- Ratios and differences must be created only by explicit `compare`.
- Raw `DATABASES_MPI` directories must not be accepted by `compare`, `plot`,
  or `paraview`.
- Incompatible meshes or selection fingerprints must fail before partial
  comparison outputs are written.
- Production-scale and high-frequency validation remain unverified until a
  separate acceptance task proves them.

## 9. Migration strategy

The migration must preserve current repository usage until the standalone
package is verified.

Required sequence:

1. Keep the old command working during transition:

   ```bash
   python -m scripts.ulvz_model_postprocess ...
   ```

2. Add the standalone package under:

   ```text
   packages/ulvz_model_postprocess/
   ```

3. Add:

   ```bash
   python -m ulvz_model_postprocess ...
   ulvz-model-postprocess ...
   ```

4. Update tests to cover both old and new entry points during migration.
5. Update package documentation examples to use standalone commands.
6. Deprecate the old `scripts.*` entry point only after standalone extraction,
   delayed comparison, plotting, and ParaView export pass on the preserved Task
   3D fixture.
7. Preserve Task 3E/3F fixture visualization tools unless explicitly migrated
   later.

Synchronization rules during transition:

- `scripts/ulvz_model_postprocess/` remains the verified in-repository
  implementation while `packages/ulvz_model_postprocess/` becomes the
  standalone package.
- Behavioral changes must be applied to both trees or explicitly documented as
  package-only or repo-only.
- Tests must exercise both entry points for shared behavior to prevent
  divergence.
- Shared acceptance scenarios must compare schema version, field units,
  rank-store layout, comparison orientation, ParaView metadata, and failure
  messages where practical.
- The old path may be reduced to a compatibility wrapper only after the
  standalone path has passed Task 4C-equivalent verification.

## 10. Documentation updates

Future documentation files:

```text
packages/ulvz_model_postprocess/README.md
packages/ulvz_model_postprocess/docs/ulvz_model_postprocessing_guide.md
packages/ulvz_model_postprocess/specfem_extension/README.md
```

Documentation ownership:

- During migration, the repository-level guide may remain:

  ```text
  docs/ulvz_model_postprocessing_guide.md
  ```

- After migration, the authoritative user manual should live at:

  ```text
  packages/ulvz_model_postprocess/docs/ulvz_model_postprocessing_guide.md
  ```

- The repository-level guide must not become a long-term divergent manual.
  After migration it should either become a short pointer to the package guide
  or be generated/synchronized from the package guide by an explicit documented
  process.

The package documentation should include:

- standalone installation guide;
- SPECFEM extractor installation guide;
- extractor compatibility checklist;
- examples using arbitrary external paths;
- troubleshooting for extractor not found, incompatible SPECFEM extractor,
  unsupported database layout, output-directory permission errors, missing VTK
  for ParaView export, large-model memory rejection, and raw `DATABASES_MPI`
  passed to `compare`, `plot`, or `paraview`.

## 11. Test and validation plan

Task 4D implementation must add or preserve tests for:

- package import from outside the old `ulvz_specfem` repository;
- console script entry point `ulvz-model-postprocess`;
- `python -m ulvz_model_postprocess`;
- no dependency on current working directory;
- all outputs written under `--out-dir`;
- selected/full extraction fails clearly when `--extractor` is missing;
- extraction succeeds with a provided compatible extractor on the preserved
  Task 3D fixture;
- compare, plot, and paraview work from standalone installation;
- current Task 4C tests continue to pass;
- Task 3E/3F fixture tools are not regressed.

Suggested verification commands for implementation:

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m pytest tests/ulvz_model_postprocess -q

/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m pytest tests/ulvz_mesh_viz -q
```

Standalone package tests should also install the package in editable mode in a
temporary or controlled environment and run commands from outside the old repo
root. Automated tests must not require production-scale or high-frequency
simulations.

## 12. Open questions

- Should an optional `--specfem-root` convenience flag be added after the
  primary `--extractor` interface is stable?
- Should packaging metadata expose VTK and PyVista as optional extras, for
  example `ulvz_model_postprocess[paraview]`?
- Should the SPECFEM patch target one known SPECFEM commit/configuration or
  support multiple patch variants?
- How should bundled extractor source be versioned relative to Python package
  releases?
- Should the standalone package include a tiny synthetic smoke fixture, or
  should real-fixture testing continue to rely on the preserved Task 3D fixture
  in this repository?

## 13. Proposed implementation phases and changed-files list

### Phase 1: Package skeleton

Create:

```text
packages/ulvz_model_postprocess/pyproject.toml
packages/ulvz_model_postprocess/README.md
packages/ulvz_model_postprocess/src/ulvz_model_postprocess/
```

Copy the verified Python implementation from `scripts/ulvz_model_postprocess/`
into the package source tree.

### Phase 2: Standalone imports and entry points

Rewrite imports for the package copy, add `python -m ulvz_model_postprocess`,
and add the `ulvz-model-postprocess` console script. Keep the old
`scripts.ulvz_model_postprocess` entry point working during transition.

### Phase 3: Extractor extension materials

Create:

```text
packages/ulvz_model_postprocess/specfem_extension/src/auxiliaries/ulvz_model_extract.f90
packages/ulvz_model_postprocess/specfem_extension/patches/add_xulvz_model_extract.patch
packages/ulvz_model_postprocess/specfem_extension/install_extractor.py
packages/ulvz_model_postprocess/specfem_extension/README.md
```

The installer must default to dry-run and require `--apply` for changes.

### Phase 4: Standalone tests

Add package tests for import, CLI entry points, CWD independence, explicit
extractor behavior, output-directory confinement, and preserved Task 3D fixture
extraction with a compatible extractor.

### Phase 5: Task 4C-equivalent standalone acceptance

Run external `DATABASES_MPI` paths through standalone:

```text
extract -> delayed comparison -> static plotting -> ParaView point cloud ->
ParaView linearized mesh -> VTK reopening
```

Compare results with current Task 4C behavior and preserve evidence.

### Phase 6: Documentation ownership cleanup

Move the authoritative user guide to:

```text
packages/ulvz_model_postprocess/docs/ulvz_model_postprocessing_guide.md
```

Keep the repository-level guide as a short pointer or synchronized copy so the
project does not maintain two divergent user manuals.

### Future changed-files list

Future implementation is expected to modify or create:

```text
packages/ulvz_model_postprocess/
docs/ulvz_model_postprocessing_guide.md
tests/ulvz_model_postprocess/
```

It may add extractor extension materials under the package, but must not modify
production forward-solver behavior. Task 3E/3F tools must remain unchanged
unless a separate migration task explicitly includes them.
