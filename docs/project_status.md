# ULVZ SPECFEM Project Status

Last updated: 2026-06-30 17:32:40 CEST +0200

This file summarizes the current state of
`/import/freenas-m-01-seismology/xjiang/ulvz_specfem`. It is based on
repository files, versioned documentation, current command output, and
preserved test artifacts. It does not rely on prior chat context.

## Overview

This project uses SPECFEM3D_GLOBE to study synthetic ultralow-velocity zones
near the core-mantle boundary. Project rules in `AGENTS.md` require explicit
scientific assumptions, separated background and perturbation cases,
machine-readable ULVZ records, copied parameter files in every run directory,
and recorded provenance.

The implemented path in this workspace is a source-level S40RTS overlay
controlled by an external runtime parameter file. The lightweight validation
fixture verifies implementation behavior; it is not a production waveform
resolution study.

## Status At A Glance

| Task | Implementation status | Real-fixture verification status | Key evidence or limitation |
| --- | --- | --- | --- |
| Task 3C S40RTS ULVZ overlay | Implemented in `specfem3d_globe/src/meshfem3D/model_s40rts.f90`; example parameter file and test target present | Verified by `5.test_s40rts_ulvz.sh`; `results.log` records `test_s40rts_ulvz done successfully` | Overlay is enabled only for parsed `MODEL_NAME == 's40rts'`; `s40rts_paper` is explicitly excluded |
| Task 3D two-rank mesher validation | Implemented with fixture Par_file, shell harness, and independent Fortran inspector | Verified on preserved workdir `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829` | Latest report status is PASS with nonzero outside/taper/core coverage and residuals below tolerance |
| Task 3E visualization export and static plotting | Implemented under `scripts/ulvz_mesh_viz/` with CSV/JSON schema `ulvz_mesh_viz.v1` | Verified on preserved fixture outputs and static figures in latest workdir | Default static plotting path is documented and tested to avoid PyVista, VTK, Cartopy, and Meshio imports |
| Task 3F ParaView export | Implemented scripts/docs/tests found: `export_paraview_points.py`, `export_paraview_mesh.py`, inspector/harness mesh CSV support, synthetic VTK tests | Not yet verified using preserved real-fixture ParaView artifacts | No preserved `paraview_mesh_metadata.json` was found; Task 3E figures do not prove ParaView integration |

## Runtime Contract

External S40RTS ULVZ parameter paths:

- runtime path expected by the implementation:
  `specfem3d_globe/DATA/ulvz_s40rts.par`
- example path:
  `specfem3d_globe/DATA/ulvz_s40rts.par.example`

Required keys:

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

Parsed `MODEL_NAME == 's40rts'` enables reading, validating, broadcasting, and
applying the overlay. Compatible raw `MODEL` suffix forms that reduce to
`MODEL_NAME == 's40rts'`, such as `s40rts_crust1.0_AIC`, enter the overlay
path. `s40rts_paper` keeps `MODEL_NAME == 's40rts_paper'` and does not read,
broadcast, or apply the ULVZ overlay.

The Task 3D fixture ULVZ is:

```text
center latitude: 45.0 deg
center longitude: 140.0 deg
thickness: 80 km
lateral radius: 400 km
lateral taper: 100 km
top taper: 20 km
dVs: -0.20
dVp: -0.10
dRho: +0.05
```

## Current Worktree State

The top-level mounted workspace is not a Git repository. The nested SPECFEM
tree is a Git repository. Current status command:

```bash
git -C specfem3d_globe status --short
```

Timestamp: 2026-06-30 17:32:40 CEST +0200

Output:

```text
 M src/meshfem3D/model_s40rts.f90
 M tests/meshfem3D/test_models.makefile
?? DATA/ulvz_s40rts.par.example
?? tests/meshfem3D/5.test_s40rts_ulvz.sh
?? tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh
?? tests/meshfem3D/inspect_s40rts_ulvz_database.f90
?? tests/meshfem3D/results.log
?? tests/meshfem3D/s40rts_ulvz_mesh_fixture/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_102140_2/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_112549_1955966/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_114241_1957826/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_114716_1959884/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_115002_1960459/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_153531_2147228/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_153639_2150987/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_153747_9/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_154733_2192419/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155014_2201348/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/
?? tests/meshfem3D/test_s40rts_ulvz.f90
?? utils/BuildBot/__pycache__/
```

Implementation files are mixed with generated artifacts in the working tree.
Treat run directories, logs, figures, compressed CSVs, binary mesh databases,
build outputs, and `__pycache__` as artifacts rather than source
implementation.

Key implementation files:

- `specfem3d_globe/src/meshfem3D/model_s40rts.f90`
- `specfem3d_globe/DATA/ulvz_s40rts.par.example`
- `specfem3d_globe/tests/meshfem3D/test_models.makefile`
- `specfem3d_globe/tests/meshfem3D/test_s40rts_ulvz.f90`
- `specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh`
- `specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh`
- `specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_fixture/DATA/Par_file`
- `scripts/ulvz_mesh_viz/`
- `tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py`
- `docs/*.md`

Generated artifacts currently include:

- `specfem3d_globe/tests/meshfem3D/results.log`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_*/`
- `specfem3d_globe/bin/`
- `specfem3d_globe/obj/`
- Python `__pycache__` directories

## Verification Evidence

### Task 3C Overlay

Evidence:

- Implementation: `specfem3d_globe/src/meshfem3D/model_s40rts.f90`
- Example parameter file: `specfem3d_globe/DATA/ulvz_s40rts.par.example`
- Test: `specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh`
- Documentation: `docs/task_3c_external_s40rts_ulvz.md`

Verified behavior recorded in documentation and `results.log`:

- `MODEL_NAME == 's40rts'` reads and broadcasts `DATA/ulvz_s40rts.par`.
- `s40rts_paper` does not read or apply the ULVZ overlay.
- S40RTS/P12 coefficient files remain unchanged.
- `5.test_s40rts_ulvz.sh` passed with 2 MPI ranks; `results.log` records
  `test_s40rts_ulvz done successfully`.

### Task 3D Mesher Fixture

Evidence:

- Fixture: `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_fixture/DATA/Par_file`
- Test harness: `specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh`
- Inspector: `specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90`
- Completion document: `docs/task_3d_s40rts_ulvz_mesh_test.md`
- Latest preserved passing artifact:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829`

Fixture disclaimer:

```text
S40RTS ULVZ mesher validation fixture
NEX_XI=32, NEX_ETA=32, NPROC=2
Not a production waveform-resolution mesh
```

Latest preserved report evidence:

```text
status: PASS
outside taper core counts: 1079936 48 16
CMB boundary non-comparable count: 1182
max geometry/topology real-record difference: 0.00000000E+00
material points changed: 64
outside-geometry changed count: 0
wrong-sign material response count: 0
ratio residual tolerance: 5.0e-5
max residual rho: 2.64773818E-07
max residual vsv: 8.00418074E-07
max residual vsh: 8.00418074E-07
max residual vpv: 4.27960636E-07
max residual vph: 4.27960636E-07
```

Latest preserved run provenance:

```text
SPECFEM version: 8.1.1
git commit: 9c312cb2c991b47484a7f302775f4f01ed9470f8
MPI command: mpirun -np 2 /import/freenas-m-01-seismology/xjiang/ulvz_specfem/specfem3d_globe/bin/xmeshfem3D
OMP_NUM_THREADS: 1
elapsed_seconds: 63
artifact_kib: 143179
```

### Task 3E Visualization Export And Static Plotting

Evidence:

- Export support in `specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90`
- Static plotting scripts under `scripts/ulvz_mesh_viz/`
- Tests in `tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py`
- Guide: `docs/ulvz_mesh_visualization_guide.md`
- Latest preserved data:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/mesh_visualization_metadata.json`
  and `reports/mesh_gll_points.csv.gz`
- Latest preserved figures manifest:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/figures/all_figures_manifest.json`

Latest metadata evidence:

```text
schema_version: ulvz_mesh_viz.v1
full_source_count: 1080000
exported_count: 49152
outside_stride: 22
retained outside/taper/core: 49088/48/16
fields_present: rho, vsv, vsh, vpv, vph
```

The default static plotting path is documented and tested to avoid importing
PyVista, VTK, Cartopy, and Meshio.

### Task 3F ParaView Export

Evidence for implementation:

- `scripts/ulvz_mesh_viz/export_paraview_points.py`
- `scripts/ulvz_mesh_viz/export_paraview_mesh.py`
- `specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90`
- `specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh`
- `tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py`
- `docs/task_3f_plan.md`
- `docs/task_3f_paraview_export.md`

Supported by synthetic tests:

- VTP point export preserves point count and scalar arrays for synthetic data.
- `--unique-points` rejects inconsistent duplicate `(rank, iglob)` rows.
- PVTU/VTU unit cube writes readable `VTK_HEXAHEDRON` cells with expected
  positive orientation.
- Explicit coordinate-welded VTU output works on synthetic data.

Real preserved-fixture ParaView status:

```bash
find specfem3d_globe/tests/meshfem3D -maxdepth 3 -type f \
  -name 'paraview_mesh_metadata.json' -print
```

The command output was empty. Therefore no preserved real-fixture
`paraview_mesh_metadata.json` exists in the inspected workspace. Task 3F is
implemented and synthetically tested where supported by evidence, but the
real preserved-fixture ParaView export is not yet verified. Task 3E figure
artifacts do not verify ParaView integration.

## Planned Or Unavailable Work

Planned only:

- production waveform simulations;
- higher-resolution mesh or production-resolution ULVZ studies;
- general external database injection workflow for arbitrary ULVZ cases;
- SPiRaL-based ULVZ workflow.

Unavailable or environment-dependent:

- production solver validation is not established in this status document;
- `docs/current_setup_audit.md` reported `bin/xspecfem3D` was not present at
  audit time;
- local SPiRaL data are not installed according to
  `docs/model_reader_comparison_s40rts_spiral.md`;
- compiler, MPI, and Python package versions beyond those directly stated in
  this file are not recorded in this status document.

Python package availability is interpreter-specific. Command used:

```bash
python - <<'PY'
import importlib.util
import sys
print('sys.executable=' + sys.executable)
for name in ['numpy','pandas','matplotlib','scipy','pytest','vtk','pyvista']:
    print(f'{name}={bool(importlib.util.find_spec(name))}')
PY
```

Output:

```text
sys.executable=/usr/bin/python
numpy=True
pandas=True
matplotlib=True
scipy=True
pytest=True
vtk=True
pyvista=False
```

This result applies only to `/usr/bin/python`. It does not describe every
Conda environment. Earlier work used the `ulvz-specfem` Conda environment,
where PyVista may be available; check the active interpreter before optional
3-D or ParaView workflows.

## Key Commands And Resume Workflow

Read these first on a new server or session:

- `AGENTS.md`
- `docs/task_3c_plan.md`
- `docs/task_3c_external_s40rts_ulvz.md`
- `docs/task_3d_plan.md`
- `docs/task_3d_s40rts_ulvz_mesh_test.md`
- `docs/task_3e_mesh_visualization_plan.md`
- `docs/ulvz_mesh_visualization_guide.md`
- `docs/task_3f_plan.md`
- `docs/task_3f_paraview_export.md`

Check or create the runtime ULVZ file from the example:

- example: `specfem3d_globe/DATA/ulvz_s40rts.par.example`
- runtime: `specfem3d_globe/DATA/ulvz_s40rts.par`

Build/check test targets:

```bash
make -C specfem3d_globe -f tests/meshfem3D/test_models.makefile \
  TEST_SRCDIR=tests/meshfem3D test_s40rts_ulvz

make -C specfem3d_globe -f tests/meshfem3D/test_models.makefile \
  TEST_SRCDIR=tests/meshfem3D inspect_s40rts_ulvz_database
```

Run lightweight validation:

```bash
cd specfem3d_globe/tests/meshfem3D
./5.test_s40rts_ulvz.sh
./6.test_s40rts_ulvz_mesh.sh
```

Generate Task 3E visualization export and static figures:

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

Run the not-yet-verified Task 3F real-fixture ParaView path:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_MESH_VIZ_DATA=1 \
EXPORT_PARAVIEW_MESH_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh

python ../../../scripts/ulvz_mesh_viz/export_paraview_points.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview

python ../../../scripts/ulvz_mesh_viz/export_paraview_mesh.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview
```

## Latest Preserved Artifact

Most relevant latest passing artifact:

- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829`

Contained evidence:

- reference case:
  `reference_disabled/DATA/Par_file`,
  `reference_disabled/DATA/ulvz_s40rts.par`,
  `reference_disabled/manifest.txt`,
  `reference_disabled/xmeshfem3D.log`
- ULVZ case:
  `ulvz_enabled/DATA/Par_file`,
  `ulvz_enabled/DATA/ulvz_s40rts.par`,
  `ulvz_enabled/manifest.txt`,
  `ulvz_enabled/xmeshfem3D.log`
- reports:
  `reports/preflight_summary.txt`,
  `reports/preflight_summary.csv`,
  `reports/comparison_summary.txt`,
  `reports/comparison_summary.csv`,
  `reports/mesh_visualization_metadata.json`,
  `reports/mesh_gll_points.csv.gz`
- figures:
  `figures/plot_data_validation_summary.json`,
  `figures/all_figures_manifest.json`

## Prioritized Next Steps

### Remaining Implementation Verification

1. Run the Task 3F real preserved-fixture ParaView export:

   - generate `paraview_mesh_metadata.json`;
   - generate `paraview_mesh_nodes_rankXXXXXX.csv.gz`;
   - generate `paraview_mesh_cells_rankXXXXXX.csv.gz`;
   - run `export_paraview_points.py`;
   - run `export_paraview_mesh.py`;
   - reopen VTP/PVTU/VTU with the active Python/VTK or PyVista environment;
   - record bounds, point counts, cell counts, cell types, arrays, category
     counts, negative/zero-volume counts, node merge policy, and output sizes.

2. Re-run and preserve Python test output for:

   ```bash
   python -m pytest tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py -q
   ```

3. Verify the active optional 3-D environment explicitly. Record
   `sys.executable`, package availability, and whether PyVista or VTK is used.

### Higher-Resolution Mesh Validation

1. Design a larger but still non-production validation mesh that increases
   core and taper sample counts beyond the coarse Task 3D fixture.

2. Keep the same disabled/enabled comparison structure and independent oracle.

3. Compare sampling density, category counts, residuals, and ParaView
   linearized-cell quality against the Task 3D fixture.

4. Do not interpret the current Task 3D fixture as waveform-resolution
   evidence.

### Future Production Waveform Simulation Work

1. Create separate reference and ULVZ production case directories. Do not
   overwrite existing cases.

2. Copy all parameter files, station/source files, ULVZ parameter records,
   SPECFEM version, git commit, mesh settings, MPI command, and date into each
   run directory.

3. Validate the production reference mesh and database before running the ULVZ
   case.

4. Run a short solver test before any full production waveform simulation.

5. Compare ULVZ waveforms only against the identical reference setup.

6. Check for NaNs, abnormal CFL warnings, missing seismograms, failed MPI
   ranks, and unintended attenuation changes.

## Appendix A: Evidence Sources

Project rules and workflow:

- `AGENTS.md`
- `docs/github_publish_workflow.md`

Design and task documentation:

- `docs/current_setup_audit.md`
- `docs/ulvz_parameter_conventions.md`
- `docs/model_reader_comparison_s40rts_spiral.md`
- `docs/s40rts_ulvz_manual_translation.md`
- `docs/task_3c_plan.md`
- `docs/task_3c_external_s40rts_ulvz.md`
- `docs/task_3d_plan.md`
- `docs/task_3d_s40rts_ulvz_mesh_test.md`
- `docs/task_3e0_plan.md`
- `docs/task_3e_mesh_visualization_plan.md`
- `docs/ulvz_mesh_visualization_guide.md`
- `docs/task_3f_plan.md`
- `docs/task_3f_paraview_export.md`

Implementation and test files:

- `specfem3d_globe/src/meshfem3D/model_s40rts.f90`
- `specfem3d_globe/DATA/ulvz_s40rts.par.example`
- `specfem3d_globe/tests/meshfem3D/test_models.makefile`
- `specfem3d_globe/tests/meshfem3D/test_s40rts_ulvz.f90`
- `specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh`
- `specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh`
- `specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_fixture/DATA/Par_file`
- `scripts/ulvz_mesh_viz/*.py`
- `tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py`

Preserved test artifacts:

- `specfem3d_globe/tests/meshfem3D/results.log`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/comparison_summary.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/comparison_summary.csv`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/preflight_summary.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/preflight_summary.csv`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/mesh_visualization_metadata.json`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reports/mesh_gll_points.csv.gz`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reference_disabled/manifest.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/ulvz_enabled/manifest.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/figures/plot_data_validation_summary.json`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/figures/all_figures_manifest.json`

Current command evidence:

- `git -C specfem3d_globe status --short`
- `python - <<'PY' ... importlib.util.find_spec(...) ... PY`
- `find specfem3d_globe/tests/meshfem3D -maxdepth 3 -type f -name 'paraview_mesh_metadata.json' -print`

## Appendix B: Earlier Retained Work Directories And Artifact Policy

Earlier Task 3D/3E work directories are visible under:

- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_*/`

Some earlier work directories and `results.log` include failed intermediate
attempts. Use the latest passing preserved artifact and completion documents
for status decisions unless a newer run is explicitly verified.

Generated artifacts should generally remain out of source-control commits
unless intentionally retained for provenance. The publishing workflow in
`docs/github_publish_workflow.md` excludes SPECFEM build outputs and
`specfem3d_globe/tests/meshfem3D/results.log` by default.
