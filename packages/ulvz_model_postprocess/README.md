# ULVZ Model Post-Processing Package

Standalone post-processing tools for compatible SPECFEM3D_GLOBE
`DATABASES_MPI` model outputs used by the ULVZ SPECFEM project.

This package is intended to be copyable outside the original `ulvz_specfem`
repository. It provides:

```bash
ulvz-model-postprocess ...
python -m ulvz_model_postprocess ...
```

The authoritative standalone user guide is:

```text
docs/ulvz_model_postprocessing_guide.md
```

The old in-repository entry point remains supported during migration:

```bash
python -m scripts.ulvz_model_postprocess --help
```

## Install

```bash
mamba create -n ulvz-post -c conda-forge \
  python=3.11 numpy pandas matplotlib scipy pytest vtk pyvista

conda activate ulvz-post

pip install -e /path/to/ulvz_specfem/packages/ulvz_model_postprocess
```

Static plotting uses Matplotlib and should not require VTK or PyVista.
ParaView export requires VTK Python modules.

## Commands

```bash
ulvz-model-postprocess --help
python -m ulvz_model_postprocess --help
```

Main subcommands:

```text
validate
extract
compare
plot
paraview
```

## Extractor Requirement

The Python package does not parse raw SPECFEM binary files directly.
Any command that validates or extracts a raw `DATABASES_MPI` directory requires
an explicit compatible extractor:

```bash
--extractor /path/to/specfem3d_globe/bin/xulvz_model_extract
```

The package does not auto-discover an extractor relative to the old
`ulvz_specfem` repository. All outputs are written under user-provided
`--out-dir`.

The bundled SPECFEM extension lives under:

```text
specfem_extension/
```

See `specfem_extension/README.md` for helper-based and patch-based
installation into a compatible external SPECFEM3D_GLOBE checkout.

## Supported Boundary

Implemented and verified on preserved Task 3D fixture for compatible local
sequential reg1 isotropic/TISO `proc*_reg1_solver_data.bin` layouts.

Still unsupported or unverified:

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

No support is claimed for arbitrary incompatible SPECFEM outputs or production
scale/high-frequency models.
