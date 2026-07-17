# ULVZ SPECFEM Project Status

Last updated: 2026-07-16

This file summarizes the current state of
the project working tree. It is based on
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
| Task 3D two-rank mesher validation | Implemented with fixture Par_file, shell harness, and independent Fortran inspector | Verified on preserved workdir `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444` | Latest report status is PASS with nonzero outside/taper/core coverage and residuals below tolerance |
| Task 3E visualization export and static plotting | Implemented under `scripts/ulvz_mesh_viz/` with CSV/JSON schema `ulvz_mesh_viz.v1` | Verified on preserved fixture outputs and static figures in latest workdir | Default static plotting path is documented and tested to avoid PyVista, VTK, Cartopy, and Meshio imports |
| Task 3F ParaView export | Diagnostic mesh exporters and final model exporter are implemented; final model path uses `solver_data.bin` arrays and `export_paraview_model.py`; `--full-mesh` exports `region=all` records with distinct `ulvz_full_model_*` names | implemented and verified on preserved real fixture `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_164822_183226`; latest combined diagnostic/model ParaView generation is `s40rts_ulvz_mesh_work_20260702_165805_185535`; latest full-mesh final model generation is `s40rts_ulvz_mesh_work_20260703_102747_261318` | Final model validation records readable VTP, both VTU rank pieces, PVTU, welded VTU, `vp/vs/rho`, TISO, and before/after ratio arrays, gzip-verified raw rank CSVs, km coordinates, field-aware split preservation, and zero negative/near-zero volumes |
| Task 4A/4B/4C reusable model post-processing | implemented and verified for `scripts/ulvz_model_postprocess/` with schema `ulvz_model_postprocess.v1`: CLI, schema, rank-local `.npy` store, synthetic workflows, comparison/plot/ParaView behavior, SPECFEM layout inspection, and Task 4C physical-field extraction for compatible local sequential reg1 databases | implemented and verified on preserved Task 3D `reference_disabled` and `ulvz_enabled` fixture databases in `task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z`: external `DATABASES_MPI` paths, full extraction, delayed comparison, static plots, VTP/PVTP and VTU/PVTU reopening, and Task 3D CSV consistency cross-check all passed; fresh regressions report `tests/ulvz_model_postprocess: 15 passed` and `tests/ulvz_mesh_viz: 26 passed` | Supported real workflow is limited to compatible `proc*_reg1_solver_data.bin` isotropic/TISO layouts. Production-scale and high-frequency validation remain unverified. Still unsupported: ADIOS/HDF5, non-reg1 extraction, full anisotropic mantle `cij`, standalone model-data paths, cross-mesh interpolation, true sub-rank record streaming, and arbitrary incompatible SPECFEM binary layouts |
| Task 4E standalone model post-processing package | implemented and verified for `packages/ulvz_model_postprocess/`: copyable Python package, `ulvz-model-postprocess` console script, `python -m ulvz_model_postprocess`, standalone docs, tests, and bundled SPECFEM extractor extension | implemented and verified on the preserved Task 3D fixture through the standalone entry point with selected extraction, delayed comparison, static plot, and ParaView `both` export; package tests report `8 passed`; old `scripts.ulvz_model_postprocess` still works | Real raw `DATABASES_MPI` validation/extraction requires explicit compatible `--extractor`; production-scale/high-frequency validation remains unverified; unsupported layouts from Task 4C remain unsupported and no support for arbitrary incompatible SPECFEM outputs is claimed |
| Two-chunk SPECFEM implementation and formal runtime continuation | The accepted project-local patch is documented at `patches/specfem3d_globe/two_chunk_endpoints/`; no production build rule changed | Fresh isolated NEX=96 patched/reversed/v8 builds completed. Patched 2/8/12-rank fingerprints match; topology has reciprocal C1/C2 two-member paths across three depths and no internal Stacey face. Reversed and clean v8 reproduce the historical `(0,1,0)` path. v3 waveform symmetry, fresh one-chunk, and rerun six-chunk regressions pass. | Current patch is formally accepted for the canonical 90° configuration: max NRMS `2.92e-6`, max relative energy difference `2.86e-6`; `canonical_90deg_fixture_ready=true`. General two-chunk classification remains B; Kim/Song Hawaiʻi production inputs remain incomplete. See `docs/two_chunk_waveform_symmetry_closure.md` and its result root. |
| One-chunk Hawai'i/Yuan coverage audit | Source constraints, 90°–150° low-resolution width meshes, constructed-geometry search, short solver smoke, and a 20-minute solver duration run completed; no production source change | All five width meshes had positive Jacobians; final 135° source/station smoke completed with nonzero waveforms; long run completed 6500 steps | Hawai'i and individual Yuan geometry classifications are conditional on locally constructed inputs. The completed long run lacks an independent larger-domain/reference comparison to identify boundary reflections, so production-safe boundary windows remain unverified; see `docs/one_chunk_hawaii_yuan_analysis.md` |
| One-chunk 135° boundary/domain validation | Independent 135° one-chunk and 6-chunk global meshes/runtimes, actual GLL-spacing comparison, 16 deep/shallow probes, a 120° sensitivity run, and complete-record post-processing completed; no production source change | Both 135° and global solvers completed 16,800 steps with all 17 receivers; 135° target-region spacing matches global within the recorded 15% criterion | Hawai'i remains B and `production_safe=false`. Complete-record diagnostics do not make one chunk globally equivalent: no science-window residual was uniquely attributable to a lateral boundary, probe returns are not uniquely separable, and the 120° test is spacing-confounded. See `docs/one_chunk_ulvz_simulation_assessment.md`, `docs/one_chunk_boundary_validation.md`, and timestamped results. |

## Runtime Contract

External S40RTS ULVZ parameter paths:

- runtime path expected by the implementation:
  `specfem3d_globe/DATA/ulvz_s40rts.par`
- example path:
  `specfem3d_globe/DATA/ulvz_s40rts.par.example`
- runtime input documentation:
  `docs/s40rts_ulvz_runtime_inputs.md`

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

Timestamp: 2026-07-08 CEST

Output:

```text
 M src/auxiliaries/rules.mk
 M src/meshfem3D/model_s40rts.f90
 M tests/meshfem3D/test_models.makefile
?? DATA/ulvz_s40rts.par.example
?? src/auxiliaries/ulvz_model_extract.f90
?? tests/meshfem3D/5.test_s40rts_ulvz.sh
?? tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh
?? tests/meshfem3D/inspect_s40rts_ulvz_database.f90
?? tests/meshfem3D/results.log
?? tests/meshfem3D/s40rts_ulvz_mesh_fixture/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_115002_1960459/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155014_2201348/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_161556_177882/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_165805_185535/
?? tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318/
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
- `packages/ulvz_model_postprocess/`
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
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444`

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
MPI command: mpirun -np 2 "$SPECFEM_ROOT/bin/xmeshfem3D"
OMP_NUM_THREADS: 1
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
- `scripts/ulvz_mesh_viz/export_paraview_model.py`
- `specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90`
- `specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh`
- `tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py`
- `docs/task_3f_plan.md`
- `docs/task_3f_paraview_export.md`
- `docs/task_4a_reusable_model_postprocessing_plan.md`
- `docs/task_4b_reusable_model_postprocessing.md`
- `docs/task_4c_specfem_solver_data_physical_field_extraction_plan.md`
- `docs/ulvz_model_postprocessing_guide.md`
- `docs/paraview_model_export_reconnaissance.md`

Supported by synthetic tests:

- VTP point export preserves point count and scalar arrays for synthetic data.
- `--unique-points` rejects inconsistent duplicate `(rank, iglob)` rows.
- PVTU/VTU unit cube writes readable `VTK_HEXAHEDRON` cells with expected
  positive orientation.
- Explicit coordinate-welded VTU output works on synthetic data.
- Final model exporter synthetic tests verify field-aware node merging,
  coincident split preservation for material discontinuities, and welded VTU
  output.
- Final model exporter synthetic tests also verify ratio PointData/CellData,
  ratio-aware coincident splitting, and `is_tiso` PointData export.
- Final model exporter synthetic tests verify `--full-mesh` requires raw
  metadata `region = all`, writes distinct `ulvz_full_model_*` names, and
  keeps default `ulvz_model_*` names unchanged.

Real preserved-fixture ParaView status:

- Latest combined diagnostic/model preserved ParaView generation:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_165805_185535`
- Generation summary:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_165805_185535/paraview_generation_summary.json`
- The latest generation summary records `status: PASS` with VTK 9.6.2 and
  readable diagnostic outputs `paraview/ulvz_gll_points.vtp`,
  `paraview/ulvz_mesh.pvtu`, `paraview_welded/ulvz_mesh_welded.vtu`, plus
  final-model outputs `paraview_model/ulvz_model_gll_points.vtp`,
  `paraview_model/ulvz_model_mesh.pvtu`, and
  `paraview_model_welded/ulvz_model_mesh_welded.vtu`.
- In this generation, the diagnostic point cloud contains 49,152 sampled
  records over a broad fixture domain, while the final model PVTU contains
  450 rank-local GLL points and 256 GLL subcells in the selected ULVZ window.
  The final-model files are byte-identical to the earlier verified
  `s40rts_ulvz_mesh_work_20260702_164822_183226` model outputs.
- Latest final-model preserved validation report:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_164822_183226/paraview_model/paraview_model_real_fixture_validation.json`
- Human-readable final-model summary:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_164822_183226/paraview_model/paraview_model_real_fixture_validation.txt`
- The final-model report records `status: PASS`, readable
  `ulvz_model_gll_points.vtp`, both rank-local model VTU pieces,
  `ulvz_model_mesh.pvtu`, and `paraview_model_welded/ulvz_model_mesh_welded.vtu`.
- It verifies `vp`, `vs`, `rho`, TISO point arrays, coordinate auxiliaries,
  and dimensionless ratio arrays `vp_ratio`, `vs_ratio`, `rho_ratio`,
  `vpv_ratio`, `vph_ratio`, `vsv_ratio`, and `vsh_ratio`; gzip integrity for
  `paraview_model_records_rank000000.csv.gz` and
  `paraview_model_records_rank000001.csv.gz`; `coordinate_units = km`; 256 GLL
  subcells; 450 rank-local model points; 405 welded model points; zero
  negative volumes; zero near-zero volumes; and no field-aware split detected
  in this fixture.
- Latest full-mesh final-model preserved generation:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318`
- Full-mesh validation reports:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318/paraview_model_full/full_mesh_real_fixture_validation.json`
  and
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318/paraview_model_full/full_mesh_real_fixture_validation.txt`
- The full-mesh report records `status: PASS`, raw metadata `region = all`,
  `coordinate_units = km`, 1,080,000 input records, 8,640 spectral elements,
  552,960 exported GLL subcells, 621,922 rank-local field-aware nodes, 614,141
  coordinate-welded nodes, and `weld_tolerance = 1.0e-6 km`.
- It verifies readable `ulvz_full_model_gll_points.vtp`, both rank-local
  `ulvz_full_model_mesh_rank*.vtu` pieces, `ulvz_full_model_mesh.pvtu`, and
  `paraview_model_full_welded/ulvz_full_model_mesh_welded.vtu`; required
  final field arrays and before/after ratio arrays are present.
- The full-mesh run detected `field_aware_split_count = 38667`, meaning
  coincident points with distinct material or ratio values were preserved
  instead of silently merged.
- Full-mesh signed-volume validation found zero negative cells and zero
  near-zero cells with threshold `1.0e-12 km^3`; the minimum signed cell
  volume was `5338.58644079925 km^3`.
- Earlier diagnostic mesh preserved validation report:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/paraview/task_3f_real_fixture_validation.json`
- Human-readable diagnostic mesh summary:
  `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/paraview/task_3f_real_fixture_validation.txt`
- The diagnostic mesh validation report records `status: PASS`, four non-empty
  gzip-integrity-checked rank CSV inputs, readable `ulvz_gll_points.vtp`, both
  rank-local VTU pieces, `ulvz_mesh.pvtu`, and
  `paraview_welded/ulvz_mesh_welded.vtu`.
- Observed environment for the validation was
  `$ULVZ_PYTHON`
  with Python 3.11.15 and VTK 9.6.2.
- The PVTU contains 24 rank-local points and 4 hexahedral cells. The welded
  VTU contains 18 points and 4 cells with `weld_tolerance = 1.0e-6` km.
- The report records `coordinate_units = km`, all required point/cell arrays,
  mixed-cell category semantics from `cell_has_outside`,
  `cell_has_taper`, `cell_has_core`, and `cell_category_code`, zero negative
  volumes, zero near-zero volumes, and minimum signed PVTU volume
  `6.655546350977618E+07 km^3`.
- Python tests were rerun with the specified Conda interpreter after ratio and
  TISO exporter implementation:
  `python -m pytest tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py -q` reported
  `23 passed in 25.07s`.
- Python tests were rerun after adding full-mesh output naming:
  `$ULVZ_PYTHON -m pytest tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py -q`
  reported `26 passed in 26.77s`.

### Task 4A/4B/4C Reusable Model Post-Processing

Evidence for implementation:

- `scripts/ulvz_model_postprocess/`
- `tests/ulvz_model_postprocess/test_ulvz_model_postprocess.py`
- `specfem3d_globe/src/auxiliaries/ulvz_model_extract.f90`
- `specfem3d_globe/src/auxiliaries/rules.mk`
- `docs/task_4a_reusable_model_postprocessing_plan.md`
- `docs/task_4b_reusable_model_postprocessing.md`
- `docs/task_4c_specfem_solver_data_physical_field_extraction_plan.md`
- `docs/ulvz_model_postprocessing_guide.md`

Latest preserved Task 4C acceptance:

- `task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z`
- The acceptance report records `pass: True` and zero failures for external
  `DATABASES_MPI` paths, full extraction, delayed comparison, static plotting,
  point-cloud ParaView export, linearized-mesh ParaView export, and VTK
  reopening.
- Supported verified layout: compatible local sequential reg1
  `proc*_reg1_solver_data.bin` with isotropic or TISO physical fields.
- Single-model extraction writes native physical fields only; ratio and
  difference arrays appear only in explicit comparison products.
- The preserved fixture recorded per-rank estimated peak memory
  `150.519257 MB`, accepted under `--memory-limit-mb 1024`.
- VTK reopened `model_points.pvtp` with 1,080,000 points and 1,080,000 vertex
  cells, and `model_linear_mesh.pvtu` with 583,242 points and 8,640
  hexahedral cells. The acceptance report records zero invalid or zero-volume
  linearized cells.
- Task 3D CSV consistency cross-check maximum ratio discrepancy:
  `2.220446049250313e-16`. This is a fixture consistency cross-check, not an
  independent scientific validation.
- Fresh regression commands using
  `$ULVZ_PYTHON`
  reported `tests/ulvz_model_postprocess: 15 passed` and
  `tests/ulvz_mesh_viz: 26 passed`.

Capability boundary:

- Supported: compatible local sequential reg1 `solver_data.bin`, isotropic and
  TISO physical fields, one-model extraction without ratios, delayed
  comparison after two compatible extracted manifests exist, static plotting,
  and ParaView point-cloud and linearized-mesh export.
- Still unsupported or unverified: production-scale/high-frequency validation,
  ADIOS/HDF5 databases, non-reg1 extraction, full anisotropic `cij` export,
  standalone model-data paths plus separate geometry, cross-mesh
  interpolation/resampling, true sub-rank record streaming, and arbitrary
  incompatible SPECFEM binary layouts.

### Task 4E Standalone Model Post-Processing Package

Evidence for implementation:

- `packages/ulvz_model_postprocess/pyproject.toml`
- `packages/ulvz_model_postprocess/src/ulvz_model_postprocess/`
- `packages/ulvz_model_postprocess/specfem_extension/`
- `packages/ulvz_model_postprocess/tests/test_standalone_entrypoints.py`
- `packages/ulvz_model_postprocess/README.md`
- `packages/ulvz_model_postprocess/docs/ulvz_model_postprocessing_guide.md`
- `docs/task_4d_standalone_package_plan.md`

Verified behavior on 2026-07-08 using
`$ULVZ_PYTHON`:

- `python -m pytest packages/ulvz_model_postprocess/tests -q` reported
  `8 passed`.
- `python -m pytest tests/ulvz_model_postprocess -q` reported `15 passed`,
  preserving the old `scripts.ulvz_model_postprocess` Task 4C path.
- `python -m pytest tests/ulvz_mesh_viz -q` reported `26 passed`.
- `python -m scripts.ulvz_model_postprocess --help` and
  `PYTHONPATH=packages/ulvz_model_postprocess/src python -m ulvz_model_postprocess --help`
  both returned successfully.
- Editable installation was verified in isolated virtual environment
  `/tmp/ulvz_model_postprocess_task4e_venv` with
  `pip install -e packages/ulvz_model_postprocess --no-deps --no-build-isolation`;
  both `ulvz-model-postprocess --help` and
  `python -m ulvz_model_postprocess --help` returned successfully.
- Standalone preserved-fixture smoke output under
  `/tmp/ulvz_model_postprocess_task4e_acceptance` verified `validate`,
  selected `extract` for `reference_disabled` and `ulvz_enabled`, delayed
  `compare`, histogram `plot`, and ParaView `--paraview-kind both` on the
  preserved Task 3D fixture.
- `git -C specfem3d_globe diff --check` passed. The top-level
  `git diff --check` command is not applicable because the mounted workspace
  root is not a Git repository.

Task 4E standalone runtime contract:

- Raw SPECFEM `DATABASES_MPI` validation and extraction require explicit
  `--extractor /path/to/specfem3d_globe/bin/xulvz_model_extract`.
- The standalone package does not auto-discover
  `specfem3d_globe/bin/xulvz_model_extract` relative to the old repository.
- The bundled extractor extension contains the verified Fortran source, a
  build-rule patch for `xulvz_model_extract`, and a dry-run-by-default
  installer.
- The current Fortran extractor `--help` is treated as a safe usage/diagnostic
  command and may exit with code 2 after printing usage.
- `compare`, `plot`, and `paraview` operate on extracted manifests and reject
  raw `DATABASES_MPI` directories.
- The old in-repository `scripts.ulvz_model_postprocess` entry point remains
  available; no deprecation or removal occurred in Task 4E.

Capability boundary remains unchanged from Task 4C:

- Supported verified layout: compatible local sequential reg1
  `proc*_reg1_solver_data.bin` with isotropic or TISO physical fields.
- Still unsupported or unverified: production-scale/high-frequency validation,
  ADIOS/HDF5 databases, non-reg1 extraction, full anisotropic `cij` export,
  standalone model-data paths plus separate geometry, cross-mesh
  interpolation/resampling, true sub-rank record streaming, and arbitrary
  incompatible SPECFEM binary layouts.

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

Python package availability is interpreter-specific. Latest Task 3F optional
VTK environment check used the project interpreter:

```bash
$ULVZ_PYTHON - <<'PY'
import importlib.util
import sys
print('sys.executable=' + sys.executable)
for name in ['vtk', 'pyvista']:
    print(f'{name}={bool(importlib.util.find_spec(name))}')
if importlib.util.find_spec('vtk'):
    import vtk
    print('vtk_version=' + vtk.vtkVersion.GetVTKVersion())
PY
```

Output:

```text
sys.executable=$ULVZ_PYTHON
vtk=True
pyvista=True
vtk_version=9.6.2
```

This result applies only to the checked `ulvz-specfem` Conda interpreter. It
does not describe every Python environment.

## GitHub Publishing

The current project publishing workflow is documented in
`docs/github_publish_workflow.md`. The clean publishing repository is:

```text
$PUBLISH_REPO
```

Latest GitHub publication:

```text
remote: git@github.com:ordeal97/ulvz_specfem.git
branch: main
commit: 2835413 Add ULVZ ParaView model export workflow
published: 2026-07-02
```

The publishing workflow excludes SPECFEM build outputs, simulation databases,
preserved work directories, logs, caches, and local agent/tooling metadata.

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

Run the Task 3F real-fixture ParaView path:

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

python ../../../scripts/ulvz_mesh_viz/export_paraview_mesh.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_welded \
  --weld-coordinates \
  --weld-tolerance 1.0e-6

EXPORT_PARAVIEW_MODEL_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh

python ../../../scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_model

python ../../../scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_model_welded \
  --weld-coordinates \
  --weld-tolerance 1.0e-6

PARAVIEW_MODEL_EXPORT_REGION=all \
PARAVIEW_MODEL_EXPORT_MAX_CELLS=1600000 \
EXPORT_PARAVIEW_MODEL_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh

python ../../../scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_model_full \
  --full-mesh

python ../../../scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_model_full_welded \
  --full-mesh \
  --weld-coordinates \
  --weld-tolerance 1.0e-6
```

## Latest Preserved Artifact

Most relevant latest Task 4C reusable post-processing acceptance artifact:

- `task_4c_acceptance_artifacts/task_4c_real_fixture_acceptance_20260707T221100Z`

Contained evidence:

- extracted single-model products:
  `reference_full/model_manifest.json` and `ulvz_full/model_manifest.json`
- delayed comparison product:
  `comparison/ulvz_over_reference_manifest.json`
- static plots:
  `figures_single/histogram_vsv.png` and
  `figures_comparison/histogram_vsv_ratio.png`
- ParaView single-model products:
  `paraview_single/model_points.pvtp` and
  `paraview_single/model_linear_mesh.pvtu`
- ParaView comparison products:
  `paraview_comparison/model_points.pvtp` and
  `paraview_comparison/model_linear_mesh.pvtu`
- acceptance reports:
  `task_4c_real_fixture_acceptance.json` and
  `task_4c_real_fixture_acceptance.txt`

Most relevant latest full-mesh final-model passing artifact:

- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318`

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
  `reports/paraview_model_metadata.json`,
  `reports/paraview_model_records_rank000000.csv.gz`,
  `reports/paraview_model_records_rank000001.csv.gz`
- full-mesh ParaView final model outputs:
  `paraview_model_full/ulvz_full_model_gll_points.vtp`,
  `paraview_model_full/ulvz_full_model_mesh_rank000000.vtu`,
  `paraview_model_full/ulvz_full_model_mesh_rank000001.vtu`,
  `paraview_model_full/ulvz_full_model_mesh.pvtu`,
  `paraview_model_full/full_mesh_real_fixture_validation.json`,
  `paraview_model_full/full_mesh_real_fixture_validation.txt`,
  `paraview_model_full_welded/ulvz_full_model_mesh_welded.vtu`

Most relevant latest `ulvz-window` final-model passing artifact remains:

- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_164822_183226`

## Prioritized Next Steps

### Remaining Implementation Verification

Task 3F final-model ParaView export is verified for both the `ulvz-window`
subset artifact
`specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_164822_183226`
and the full-mesh `region=all` artifact
`specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318`.
Future reruns should preserve a validation JSON/TXT with the same evidence
categories before replacing either latest artifact in the status document.

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
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/paraview/task_3f_real_fixture_validation.json`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260702_145132_161444/paraview/task_3f_real_fixture_validation.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/reference_disabled/manifest.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/ulvz_enabled/manifest.txt`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/figures/plot_data_validation_summary.json`
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_155814_2228829/figures/all_figures_manifest.json`

Current command evidence:

- `git -C specfem3d_globe status --short`
- `$ULVZ_PYTHON - <<'PY' ... importlib.util.find_spec(...) ... PY`
- `python -m pytest tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py -q`

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

## 2026-07-16 two-chunk waveform-symmetry closure

`results/two_chunk_waveform_symmetry_closure_20260716T144230Z/` 完成 v2
fixture/window 审计和独立 v3 closure。v2 的 0--25 s 窗口在最早直达波之前，因而不
是有效严格波形 fixture。符号精确、内域近场 v3 在 2/8/12 ranks 均通过 1e-5
NRMS/能量 gate；fresh one-chunk clean/patched 和重新运行的 six-chunk regression
也通过。当前版本 patch 已正式接受；一般 two-chunk 分类仍为 B，Kim/Song Hawaiʻi
production 仍缺作者输入。

## 2026-07-16 two-chunk post-processing validation and patch-package relocation

已用 canonical C1/C2、2/8/12-rank 的 six `DATABASES_MPI` fixtures 验证
`ulvz_model_postprocess`：layout inspection、reg1 extraction、数组有限值/shape、
`vp` 绘图和 rank-local linear-mesh ParaView 均通过；2-rank C1/C2 self-compare
残差为零。该结论只覆盖 rank-local 后处理输出，未验证跨 rank/chunk 的全局焊接或
去重；不同 MPI decomposition 的 compare 因 rank inventory 不同按设计拒绝。详见
`docs/two_chunk_postprocess_support.md` 和
`results/two_chunk_postprocess_support_20260716T162353Z/07_reports/acceptance_matrix.json`。

已将 two-chunk forward-mesher patch package 从后处理扩展目录移至
`patches/specfem3d_globe/two_chunk_endpoints/`；patch 字节哈希不变，迁移后 clean
apply/reverse 验证通过。未修改正式构建规则、未 commit、未 push。

## 2026-07-16 canonical two-chunk bilingual guide and teaching case

新增 `docs/two_chunk_regional_simulations_guide.md` 及其英文/中文版，说明当前项目
已验收的 canonical two-chunk regional mode、patch provenance、Par_file、source/
station placement、travel-time-based boundary assessment 与故障排查。新增
`cases/two_chunk_canonical_90deg/`：它提供 NEX=96、2x2/chunk（8 ranks）的教学输入、
只读 `audit_geometry.py`、示意图生成器和拒绝覆盖已有 run directory 的 runner。
教学台站覆盖两个 chunk，但不被声明为 Kim/Song 或生产波形输入。静态检查确认双语
章节/参数/hash/链接一致，且案例输入符合当前 template/readers；未运行 mesher 或
solver，未修改正式源码、构建规则、commit 或 push。

## 2026-07-16 two-chunk non-90° equal-square width closure

当前源码在 `NCHUNKS > 1` 时明确要求
`ANGULAR_WIDTH_XI_IN_DEGREES = 90`（目的为几何匹配）。在 NEX=96、等方形
60°、75°、89°、91°、105° 输入上，mesher 均在该守卫处停止，因而这些案例只有
`input_rejected` 证据；没有构造网格，不能声称测得 gap、overlap、拓扑、Stacey、
分解或波形失败。新鲜 90° 2-rank 控制完成，接口 Cartesian 配对/C1/C2 endpoint
残差为零、Jacobian 为正且 internal Stacey 为零；正式 2/8/12-rank 接受仍引用此前
topology/waveform closure。结论是 canonical 90° xi connection 是唯一正式支持的
连接宽度；`xi=90°, eta!=90°` 的矩形两块情形未测试；非 90° xi 支持需新的 placement/
interface-mapping 实现。`general_two_chunk_mode_classification=B` 保持不变。详见
`docs/two_chunk_non90_width_acceptance.md` 与
`results/two_chunk_non90_width_acceptance_20260716T171151Z/`。未修改正式源码、构建
规则或 accepted patch；未 commit/push。

## 2026-07-16 canonical two-chunk planner

新增独立 `packages/two_chunk_planner/`：它在不运行 mesher/database/solver、
不修改 SPECFEM 输入或 patch 的前提下，使用当前 canonical 90° AB/AC 几何搜索
center/gamma、审计 source/stations/path/target margins，并建议受当前 NEX/MPI
规则约束的资源配置。TauP 仅用于可选 phase-aware 路径覆盖、CMB 邻近代理和带采样
元数据的 polyline 长度估计；不用于 regional 外边界污染时间。v1 的地表边界弧时间
代理固定标记为 `heuristic_not_conservative`，不作为 hard reject。最多输出五个可行
候选；无可行候选仍输出审计和 rejection summary。详见 `docs/two_chunk_planner.md`。
该工具不扩大已验收几何范围，`general_two_chunk_mode_classification=B` 保持不变；
未修改正式源码、构建规则或 accepted patch，未运行大型模拟，未 commit/push。

## 2026-07-17 two-chunk planner phase-aware runtime acceptance

在没有运行 mesher/database/solver 的条件下，`packages/two_chunk_planner/` 已以项目
解释器完成真实 ObsPy TauP `prem` phase-aware 验收：Python 3.11.15、NumPy 2.4.6、
ObsPy 1.5.0、geographiclib 2.1，且 `HAS_GEOGRAPHICLIB=True`。合成（非 Kim/Song）
AB→AC fixture 的 source 0°/0°/50 km 和 receiver 0°/−125° 经实际分类为 central AB
与 supported-left AC；严格模式同时获得 Pdiff 和 Sdiff 的地理路径、到时、Cartesian
polyline 长度与 CMB-near proxy。resample=false/true 的到时和最大深度一致，但长度差
Pdiff 14.7813 km（0.130094%）、Sdiff 8.6426 km（0.076131%）；两种离散设置不足以
构成收敛证明，故 `sampling_stability_status=indeterminate`。等价日期变更线旋转保留
125° 距离和到时、将两相路径正确分为两个绘图段。严格未知相位全局失败并列出缺失
pair，partial 模式不替代相位且写出 inventory。边界时间仍仅为
`heuristic_not_conservative`、`hard_constraint_used=false`、
`boundary_time_production_safe=false`。

证据位于 `results/two_chunk_planner_phase_aware_acceptance_20260717T085352Z/`；完整
pytest 为 13 passed。`phase_aware_runtime_validated=true` 只表示 canonical geometry
planning runtime；`canonical_planner_v1_classification` 为
`canonical_geometry_planning_validated__waveform_and_boundary_production_validation_required`。
未修改正式源码、build rules 或 accepted patch，未运行大型模拟，未 commit/push。
