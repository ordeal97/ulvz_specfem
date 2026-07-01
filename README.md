# ULVZ SPECFEM

This repository contains a SPECFEM3D_GLOBE-based workflow for studying
synthetic ultralow-velocity zones (ULVZs) near the core-mantle boundary.

The current implementation focuses on an external, runtime-configured ULVZ
overlay for the S40RTS mantle model, plus lightweight validation and
visualization tooling. The preserved validation fixture is for implementation
testing only; it is not a production waveform-resolution mesh.

## Current Status

The authoritative project summary is `docs/project_status.md`.

At a high level:

- Task 3C S40RTS ULVZ overlay is implemented and verified by the lightweight
  S40RTS overlay test.
- Task 3D two-rank mesher validation is implemented and verified on a
  preserved fixture.
- Task 3E CSV/JSON visualization export and static plotting are implemented
  and verified on preserved fixture outputs.
- Task 3F ParaView export scripts and synthetic tests are implemented, but
  real preserved-fixture ParaView export is not yet verified.

Do not infer production waveform validity from the Task 3D fixture or Task 3E
figures.

## Repository Layout

Key paths:

- `specfem3d_globe/`: local SPECFEM3D_GLOBE source tree.
- `specfem3d_globe/DATA/ulvz_s40rts.par.example`: example runtime ULVZ
  parameter file.
- `specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh`: lightweight S40RTS
  overlay test.
- `specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh`: two-rank
  mesher validation fixture.
- `scripts/ulvz_mesh_viz/`: visualization, plotting, and ParaView export
  scripts.
- `tests/ulvz_mesh_viz/`: Python tests for visualization/export tooling.
- `docs/`: task plans, implementation notes, status, and publishing workflow.

Local run directories, SPECFEM build outputs, Python caches, and generated
mesh artifacts are intentionally excluded from publication.

## Runtime ULVZ Contract

The S40RTS overlay reads runtime parameters from:

```text
specfem3d_globe/DATA/ulvz_s40rts.par
```

Create that file from:

```text
specfem3d_globe/DATA/ulvz_s40rts.par.example
```

Required parameter keys are:

```text
ENABLED
CENTER_LATITUDE_DEGREES
CENTER_LONGITUDE_DEGREES
THICKNESS_KM
LATERAL_RADIUS_KM
LATERAL_TAPER_KM
TOP_TAPER_KM
DVS
DVP
DRHO
```

The implemented perturbation combination is local-native-S40RTS-relative:

```text
d_return = (1 + d_s40rts) * (1 + w * d_ulvz) - 1
```

The overlay is enabled only when parsed `MODEL_NAME == 's40rts'`. Compatible
raw `MODEL` suffix forms that reduce to `s40rts`, such as
`s40rts_crust1.0_AIC`, enter the overlay path. `s40rts_paper` does not read,
broadcast, or apply the ULVZ overlay.

## Verification

Build/check the lightweight test targets:

```bash
make -C specfem3d_globe -f tests/meshfem3D/test_models.makefile \
  TEST_SRCDIR=tests/meshfem3D test_s40rts_ulvz

make -C specfem3d_globe -f tests/meshfem3D/test_models.makefile \
  TEST_SRCDIR=tests/meshfem3D inspect_s40rts_ulvz_database
```

Run the lightweight validation scripts:

```bash
cd specfem3d_globe/tests/meshfem3D
./5.test_s40rts_ulvz.sh
./6.test_s40rts_ulvz_mesh.sh
```

Run the visualization/export Python tests:

```bash
python -m pytest tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py -q
```

These tests validate implementation behavior and plotting/export tooling. They
do not replace higher-resolution mesh validation or production waveform
simulation.

## Visualization

Task 3E exports portable CSV/JSON products and static figures from the
lightweight mesher fixture. The default static plotting path is headless and
does not require PyVista, VTK, Cartopy, Basemap, Meshio, or Jupyter.

Generate fixture visualization data and figures:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_MESH_VIZ_DATA=1 KEEP_TEST_WORKDIR=1 ./6.test_s40rts_ulvz_mesh.sh

export MPLBACKEND=Agg
export MPLCONFIGDIR="${TMPDIR:-/tmp}/ulvz-mplconfig"
export XDG_CACHE_HOME="${TMPDIR:-/tmp}/ulvz-xdg-cache"

python ../../../scripts/ulvz_mesh_viz/make_all_figures.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/figures \
  --formats png,pdf
```

Task 3F ParaView export is documented in `docs/task_3f_paraview_export.md`.
Synthetic exporter tests exist, but real preserved-fixture ParaView export
still needs verification.

## Documentation

Start here:

- `docs/project_status.md`: current evidence-based status and next steps.
- `docs/task_3c_external_s40rts_ulvz.md`: S40RTS ULVZ overlay implementation.
- `docs/task_3d_s40rts_ulvz_mesh_test.md`: lightweight two-rank fixture.
- `docs/task_3e_mesh_visualization_plan.md`: visualization workflow.
- `docs/ulvz_mesh_visualization_guide.md`: plotting and export guide.
- `docs/task_3f_plan.md`: ParaView export plan.
- `docs/task_3f_paraview_export.md`: ParaView export user guide.
- `docs/github_publish_workflow.md`: GitHub publishing process.

## Publishing

The working directory is not the GitHub publishing repository. Publication is
done through the clean copy documented in `docs/github_publish_workflow.md`:

```text
/import/freenas-m-01-seismology/xjiang/ulvz_specfem_publish
```

Do not publish SPECFEM build outputs, simulation databases, preserved work
directories, Python caches, Conda environments, or local secret files.

## Scientific And Reproducibility Notes

- Preserve background models separately from perturbation models.
- Record git commit, SPECFEM version, MPI command, mesh settings, and date for
  every run.
- Do not overwrite existing simulation cases.
- Do not modify attenuation parameters unless explicitly instructed.
- Compare ULVZ waveforms only against the identical reference setup.
- Run a small validation case before any production waveform simulation.
