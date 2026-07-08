# SPECFEM Extractor Extension

This directory bundles the auxiliary SPECFEM extractor used by the standalone
ULVZ model post-processing package.

The extension is not a forward-solver behavior change. It adds an auxiliary
program:

```text
xulvz_model_extract
```

The extractor must be compiled from a SPECFEM3D_GLOBE checkout compatible with
the database being post-processed.

## Helper-Based Installation

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

The current verified extractor prints usage for `--help` and exits with code
2. Treat this as a safe usage/diagnostic command, not as a success-return-code
test.

## Patch-Based Installation

Inspect the patch first:

```bash
less /path/to/ulvz_model_postprocess_package/specfem_extension/patches/add_xulvz_model_extract.patch
```

Copy the bundled source:

```bash
cp /path/to/ulvz_model_postprocess_package/specfem_extension/src/auxiliaries/ulvz_model_extract.f90 \
  /path/to/specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90
```

Apply the build-rule patch from the SPECFEM root:

```bash
cd /path/to/specfem3d_globe
patch -p1 < /path/to/ulvz_model_postprocess_package/specfem_extension/patches/add_xulvz_model_extract.patch
make xulvz_model_extract
```

## Installer Safety

`install_extractor.py` defaults to dry-run behavior unless `--apply` is
provided. It checks that:

- the target SPECFEM root exists;
- `src/auxiliaries/rules.mk` exists;
- an existing `src/auxiliaries/ulvz_model_extract.f90` is not overwritten with
  different content;
- an existing `xulvz_model_extract` rule is reported and not duplicated;
- patch context is compatible before mutation.

The installer does not modify `DATABASES_MPI`, solver outputs, or production
simulation files.
