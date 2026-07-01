# ULVZ Mesh Visualization Guide

## 1. Purpose And Scope

This guide explains how to inspect and visualize the S40RTS+ULVZ
mesh-validation outputs produced by the lightweight Task 3D mesher fixture.
It is written for researchers who want to use the exported CSV/JSON reports
without reading the Fortran inspector or Python plotting source code.

The visualization tools are intended for mesh and ULVZ implementation
validation. They help answer questions such as:

- Did the test fixture export the expected ULVZ footprint?
- Are outside, taper, and core samples present?
- Do the material ratios match the independent Task 3D pointwise oracle?
- Is the coarse fixture sampling dense enough to exercise the implementation?

The default Task 3D fixture is not a production-resolution waveform mesh:

```text
S40RTS ULVZ mesher validation fixture
NEX_XI=32, NEX_ETA=32, NPROC=2
Not a production waveform-resolution mesh
```

Interpretation should distinguish three separate uses:

- Mesh and ULVZ implementation validation: confirms that the S40RTS ULVZ
  overlay is applied at the intended points with the expected ratios.
- Mesh-resolution assessment: describes how sparse or dense the validation
  fixture sampling is.
- Future production waveform simulations: require production mesh settings,
  waveform runs, and scientific resolution analysis outside the scope of this
  fixture.

Related project documents:

- `docs/task_3c_external_s40rts_ulvz.md`
- `docs/task_3d_s40rts_ulvz_mesh_test.md`
- `docs/task_3e_mesh_visualization_plan.md`
- `docs/task_3f_paraview_export.md`

## 2. Prerequisites

Use the project Python environment with the required plotting packages:

```bash
mamba activate ulvz-specfem
```

Required packages for the static workflow are:

```text
python=3.11
numpy
pandas
matplotlib
scipy
```

`pytest` is used for Python-only development tests. `pyvista` and `vtk` are
optional and are needed only for the optional 3-D viewer.

For headless-server rendering, set:

```bash
export MPLBACKEND=Agg
export MPLCONFIGDIR="${TMPDIR:-/tmp}/ulvz-mplconfig"
export XDG_CACHE_HOME="${TMPDIR:-/tmp}/ulvz-xdg-cache"
```

The Python scripts do not directly read SPECFEM binary databases. They read
only the inspector-exported CSV/JSON files written by the Task 3D test when
visualization export is enabled. The required static pipeline imports NumPy,
pandas, Matplotlib, and SciPy; it does not import PyVista, Cartopy, or Meshio.
The default static pipeline also does not import VTK. VTK is used only by the
optional ParaView exporters and the optional PyVista point viewer.

## 3. Required Input Data

The plotting interface is based on schema:

```text
ulvz_mesh_viz.v1
```

Expected files in a Task 3D `reports` directory are:

| File | Status | Use |
| --- | --- | --- |
| `mesh_visualization_metadata.json` | Mandatory when visualization export is enabled | Schema, fixture metadata, coordinate conventions, ULVZ parameters, sampling rules, provenance, and disclaimer |
| `mesh_gll_points.csv.gz` | Mandatory after Task 3D harness compression when visualization export is enabled | Pointwise GLL records used by validation and plotting |
| `mesh_gll_points.csv` | Accepted by Python loaders before compression or in synthetic tests | Plain CSV pointwise GLL records |
| `comparison_summary.csv` | Mandatory Task 3D report | Aggregate tolerances, residuals, ratio ranges, and category counts |
| `preflight_summary.txt` | Mandatory Task 3D report | Human-readable preflight category coverage and radius summary |
| `mesh_section_cells.csv.gz` | Optional, version-dependent | Optional section cell or edge overlay for vertical-section plots |

Generate the visualization export from the Task 3D fixture with:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_MESH_VIZ_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh
```

`EXPORT_MESH_VIZ_DATA=1` requires `KEEP_TEST_WORKDIR=1`; otherwise the shell
harness exits before starting the mesher so exported plot data are not removed
during cleanup. The Fortran inspector writes plain `mesh_gll_points.csv`; the
shell harness compresses it with `gzip -n -f` to `mesh_gll_points.csv.gz`.
Use the printed preserved work directory's `reports` subdirectory as
`--data-dir`.

To also generate ParaView mesh CSV inputs from the same preserved work
directory, run:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_MESH_VIZ_DATA=1 \
EXPORT_PARAVIEW_MESH_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh
```

This writes and compresses:

```text
reports/paraview_mesh_nodes_rank000000.csv.gz
reports/paraview_mesh_cells_rank000000.csv.gz
reports/paraview_mesh_nodes_rank000001.csv.gz
reports/paraview_mesh_cells_rank000001.csv.gz
reports/paraview_mesh_metadata.json
```

## 4. Quick-Start Workflow

After generating the Task 3D reports, run:

```bash
export MPLBACKEND=Agg
export MPLCONFIGDIR="${TMPDIR:-/tmp}/ulvz-mplconfig"
export XDG_CACHE_HOME="${TMPDIR:-/tmp}/ulvz-xdg-cache"

python scripts/ulvz_mesh_viz/validate_plot_data.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures

python scripts/ulvz_mesh_viz/make_all_figures.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Expected output directory structure:

```text
path/to/figures/
  plot_data_validation_summary.json
  plot_data_validation_summary.txt
  01_fixture_domain_ulvz_footprint.png
  01_fixture_domain_ulvz_footprint.pdf
  01_fixture_domain_ulvz_footprint_summary.json
  02_cmb_ulvz_sampling.png
  02_cmb_ulvz_sampling.pdf
  02_cmb_ulvz_sampling_summary.json
  03_vertical_ulvz_section.png
  03_vertical_ulvz_section.pdf
  03_vertical_ulvz_section_summary.json
  04_material_ratio_validation.png
  04_material_ratio_validation.pdf
  04_material_ratio_validation_summary.json
  05_mesh_sampling_resolution.png
  05_mesh_sampling_resolution.pdf
  05_mesh_sampling_resolution_summary.json
  all_figures_manifest.json
```

When `--formats png` is used, PDF files are not written.

The implementation was tested with the same command shape against an actual
Task 3D export:

```bash
cd specfem3d_globe/tests/meshfem3D
export MPLBACKEND=Agg
export MPLCONFIGDIR="${TMPDIR:-/tmp}/ulvz-mplconfig"
export XDG_CACHE_HOME="${TMPDIR:-/tmp}/ulvz-xdg-cache"

python ../../../scripts/ulvz_mesh_viz/make_all_figures.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/figures \
  --formats png,pdf
```

For the tested fixture, the default vertical section used
`default_section_azimuth_deg = 0.0` from metadata and the automatic section
half-width. The resulting section contained outside, taper, and core samples,
so no fixture-specific nonzero default azimuth was required.

## 5. Individual Plotting Scripts

### `validate_plot_data.py`

Purpose: validate the exported plotting interface before making figures.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`
- `comparison_summary.csv`

Example:

```bash
python scripts/ulvz_mesh_viz/validate_plot_data.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures
```

Outputs:

- `plot_data_validation_summary.json`
- `plot_data_validation_summary.txt`

Major options:

- `--data-dir`
- `--out-dir`
- optional explicit paths for metadata, points, comparison summary, and
  section cells

Expected interpretation: a passing summary means that required files, schema,
columns, category coverage, material-field availability, and duplicate
semantics are internally consistent.

Common failures:

- Missing visualization export files: rerun Task 3D with
  `EXPORT_MESH_VIZ_DATA=1` and `KEEP_TEST_WORKDIR=1`.
- Plain CSV instead of gzip: this is accepted by the Python loader; the Task
  3D harness normally compresses the real export to `mesh_gll_points.csv.gz`.
- Unsupported schema: regenerate files with a matching exporter or use
  plotting tools that support the observed schema.
- Missing category: confirm the Task 3D fixture reached the CMB and used the
  expected ULVZ parameters.
- Duplicate inconsistency: treat this as an exporter or database-layout issue;
  do not ignore it.

### `plot_fixture_overview.py`

Purpose: show the fixture domain and ULVZ footprint.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`

Example:

```bash
python scripts/ulvz_mesh_viz/plot_fixture_overview.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Outputs:

- `01_fixture_domain_ulvz_footprint.png`
- `01_fixture_domain_ulvz_footprint.pdf`
- `01_fixture_domain_ulvz_footprint_summary.json`

Major options:

- `--formats`
- `--metadata`
- `--points`

Expected interpretation: the footprint should confirm the Task 3D fixture
location, centred at geographic latitude 45 degrees and longitude 140 degrees.

Common failures:

- No valid unique coordinates: check `mesh_gll_points.csv.gz` and rerun the
  validator.

### `plot_cmb_sampling.py`

Purpose: visualize near-CMB samples and the outside, taper, and core
categories.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`

Example:

```bash
python scripts/ulvz_mesh_viz/plot_cmb_sampling.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Outputs:

- `02_cmb_ulvz_sampling.png`
- `02_cmb_ulvz_sampling.pdf`
- `02_cmb_ulvz_sampling_summary.json`

Major options:

- `--near-cmb-window-km`, if implemented
- `--formats`

Expected interpretation: the plot should show nonzero outside, taper, and
core samples. Sparse core or taper points are expected for this coarse
implementation-test mesh.

Common failures:

- No near-CMB unique points: confirm that `REGIONAL_MESH_CUTOFF=.false.` was
  used by the fixture and that the reports came from Task 3D.
- Missing category: rerun the validator and check the point CSV schema.

### `plot_vertical_section.py`

Purpose: plot a vertical section through the ULVZ centre.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`
- optional `mesh_section_cells.csv.gz`

Example:

```bash
python scripts/ulvz_mesh_viz/plot_vertical_section.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --section-azimuth-deg 0.0 \
  --section-half-width-km 100.0 \
  --formats png,pdf
```

Outputs:

- `03_vertical_ulvz_section.png`
- `03_vertical_ulvz_section.pdf`
- `03_vertical_ulvz_section_summary.json`

Major options:

- `--section-azimuth-deg`: clockwise from local north at the ULVZ centre
- `--section-half-width-km`: half-width of the selected section window
- `--formats`

Expected interpretation: `section_distance_km` is signed along the selected
profile and `height_above_cmb_km` is vertical distance above the CMB. Core and
taper points should appear only within the ULVZ height and footprint.

Common failures:

- Section window lacks core, taper, or outside samples: rerun with a larger
  `--section-half-width-km` or choose a profile azimuth that crosses the
  retained ULVZ samples.
- Unexpectedly sparse section: remember that the Task 3D mesh is intentionally
  coarse and downsampled outside the ULVZ.

### `plot_material_response.py`

Purpose: compare observed material ratios and residuals against the Task 3D
pointwise analytical oracle.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`
- `comparison_summary.csv`

Example:

```bash
python scripts/ulvz_mesh_viz/plot_material_response.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Outputs:

- `04_material_ratio_validation.png`
- `04_material_ratio_validation.pdf`
- `04_material_ratio_validation_summary.json`

Major options:

- `--fields`, if implemented, to select a subset of present material fields
- `--formats`

Expected interpretation: outside ratios should be 1.0. Core ratios should
match the configured perturbations: rho near 1.05, vsv and vsh near 0.80, and
vpv and vph near 0.90. Taper ratios should fall between outside and core
values according to `w_expected`.

Common failures:

- Missing VSH/VPH fields: this is acceptable only when
  `fields_present` marks them absent. Otherwise regenerate the export.
- Required residual column missing: check schema compatibility.
- Residuals above tolerance: treat as a validation failure, not a plotting
  issue.

### `plot_mesh_resolution.py`

Purpose: summarize point spacing and sampling density in the validation
fixture.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`

Example:

```bash
python scripts/ulvz_mesh_viz/plot_mesh_resolution.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Outputs:

- `05_mesh_sampling_resolution.png`
- `05_mesh_sampling_resolution.pdf`
- `05_mesh_sampling_resolution_summary.json`
- optional spacing-statistics CSV

Major options:

- `--formats`
- optional spacing-window controls, if implemented

Expected interpretation: use this plot to understand validation-fixture
sampling, not production waveform resolution. Low numbers of core or taper
samples indicate that the fixture is exercising code behavior rather than
resolving a scientific ULVZ model.

Common failures:

- Insufficient deduplicated points: rerun the validator and confirm that the
  point CSV contains the expected exported records.

### `make_all_figures.py`

Purpose: run validation and all required static plots in the standard order.

Required inputs:

- `--data-dir`
- `--out-dir`

Example:

```bash
python scripts/ulvz_mesh_viz/make_all_figures.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Outputs:

- all five standard figures
- all per-figure summary JSON files
- `all_figures_manifest.json`

Major options:

- `--formats`
- pass-through section controls for the vertical-section plot, if implemented

Expected interpretation: a complete manifest means that the validation step
and all required static plots ran from the same input data directory.

Common failures:

- Any individual plotting failure: run that script directly to inspect the
  targeted error message.

### `view_mesh_3d.py`

Purpose: optional PyVista/VTK-based 3-D inspection.

This script is optional and is not part of the default static figure pipeline.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`
- optional `mesh_section_cells.csv.gz`

Example:

```bash
python scripts/ulvz_mesh_viz/view_mesh_3d.py \
  --metadata path/to/reports/mesh_visualization_metadata.json \
  --points path/to/reports/mesh_gll_points.csv.gz \
  --out-dir path/to/figures/3d \
  --off-screen
```

Outputs are implementation-dependent, but may include screenshots or an HTML
view.

Common failures:

- PyVista/VTK import failure: install or activate an environment that includes
  optional 3-D packages.
- Off-screen OpenGL failure: use static Matplotlib figures instead, or run on
  a server with compatible EGL or OSMesa support.

### `export_paraview_points.py`

Purpose: export the inspector point CSV to a ParaView-readable VTP point
cloud.

Required inputs:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz` or `mesh_gll_points.csv`

Example:

```bash
python scripts/ulvz_mesh_viz/export_paraview_points.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview
```

Outputs:

- `ulvz_gll_points.vtp`
- `ulvz_gll_points_metadata.json`

Coordinates in the VTP file are physical Cartesian kilometers:
`x/y/z = x_norm/y_norm/z_norm * r_planet_km`. The normalized coordinates are
also preserved as point-data arrays. The default `--records` mode keeps
duplicate element-GLL records. `--unique-points` deduplicates by `(rank,
iglob)` only after the same duplicate-consistency checks used by
`validate_plot_data.py`.

### `export_paraview_mesh.py`

Purpose: export the test-only rank-local mesh CSV files to VTU/PVTU for
ParaView clipping, slicing, thresholding, and surface extraction.

Required inputs:

- `paraview_mesh_metadata.json`
- `paraview_mesh_nodes_rankXXXXXX.csv.gz`
- `paraview_mesh_cells_rankXXXXXX.csv.gz`

Example:

```bash
python scripts/ulvz_mesh_viz/export_paraview_mesh.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview
```

Default outputs:

- `ulvz_mesh_rank000000.vtu`
- `ulvz_mesh_rank000001.vtu`
- `ulvz_mesh.pvtu`
- `ulvz_mesh_metadata.json`

Open `ulvz_mesh.pvtu` in ParaView. The default node policy is rank-local:
partition-boundary nodes are not merged across ranks, and the metadata records
`node_merge_policy = rank-local`.

For an explicit single-file coordinate-welded export:

```bash
python scripts/ulvz_mesh_viz/export_paraview_mesh.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview_welded \
  --weld-coordinates \
  --weld-tolerance 1.0e-6
```

This writes `ulvz_mesh_welded.vtu` and records the rank-local node count,
welded node count, and weld tolerance. Welding is never implicit.

The mesh cells are 8-corner linear VTK hexahedra for overview visualization.
They do not preserve the full high-order curved spectral-element geometry.
The VTK hexahedron corner ordering follows the local SPECFEM implementation:

```text
node0 = ibool(1,1,1,ispec)
node1 = ibool(NGLLX,1,1,ispec)
node2 = ibool(NGLLX,NGLLY,1,ispec)
node3 = ibool(1,NGLLY,1,ispec)
node4 = ibool(1,1,NGLLZ,ispec)
node5 = ibool(NGLLX,1,NGLLZ,ispec)
node6 = ibool(NGLLX,NGLLY,NGLLZ,ispec)
node7 = ibool(1,NGLLY,NGLLZ,ispec)
```

The default mesh region is `PARAVIEW_MESH_REGION=ulvz-window`. For this
region, the test inspector inspects every GLL point in each element and
exports any element with at least one point satisfying `w_expected > 0`.
Selection is not based only on element corners. `PARAVIEW_MESH_REGION` also
accepts `near-cmb` and `all`; `PARAVIEW_MESH_MAX_CELLS` is a hard limit, and
`PARAVIEW_MESH_CONTEXT_MARGIN_KM` adds explicit context only when set.

Recommended ParaView filters:

- `Threshold` on `cell_w_expected_mean` or `cell_category_code`
- `Clip`
- `Slice`
- `Extract Surface`
- `Cell Data to Point Data`

## 6. Figure Interpretation

The five standard figures are:

- `01_fixture_domain_ulvz_footprint`
- `02_cmb_ulvz_sampling`
- `03_vertical_ulvz_section`
- `04_material_ratio_validation`
- `05_mesh_sampling_resolution`

Definitions:

- `outside`: `w_expected = 0`; the point should receive no ULVZ material
  change.
- `taper`: `0 < w_expected < 1`; the point is in a lateral or top cosine
  taper.
- `core`: `w_expected = 1`; the point receives the full configured ULVZ
  perturbation.
- `w_expected`: independent analytical oracle weight computed from Task 3D
  ULVZ geometry, lateral taper, and top taper.
- material ratio: enabled-case material value divided by disabled-case
  material value.
- residual: observed material ratio minus expected ratio.

Expected material-ratio behavior for the Task 3D fixture:

```text
rho expected ratio = 1 + w_expected * 0.05
vsv expected ratio = 1 + w_expected * -0.20
vsh expected ratio = 1 + w_expected * -0.20
vpv expected ratio = 1 + w_expected * -0.10
vph expected ratio = 1 + w_expected * -0.10
```

Low numbers of core and taper samples do not imply that a production ULVZ is
well resolved. They show that the lightweight fixture contains enough samples
to test implementation behavior.

## 7. Data Conventions

Coordinate system:

- `x_norm`, `y_norm`, and `z_norm` are SPECFEM normalized Cartesian
  coordinates.
- `radius_norm = sqrt(x_norm^2 + y_norm^2 + z_norm^2)`.
- `radius_km = radius_norm * 6371.0`.
- `depth_km = 6371.0 - radius_km`.
- `height_above_cmb_km = radius_km - 3480.0`.

Latitude and longitude:

- `latitude_deg` is geographic latitude derived from Cartesian coordinates.
- `longitude_deg` is geographic longitude derived from Cartesian coordinates.
- Metadata must document the longitude normalization convention.

Local ULVZ-centred coordinates:

- `angular_distance_deg` is angular distance from the ULVZ centre.
- `lateral_distance_km = 3480.0 * angular_distance_rad`.
- `point_azimuth_deg` is clockwise from local north at the ULVZ centre.
- `section_azimuth_deg` is the selected profile azimuth.
- `section_distance_km` is signed along the section profile.
- `cross_section_offset_km` is absolute perpendicular distance from the
  section profile.

Units:

- distances are kilometers unless the column name says otherwise.
- angles are degrees unless the column name says otherwise.
- material ratios and residuals are dimensionless.

Downsampling:

- Visualization export is off unless `EXPORT_MESH_VIZ_DATA=1`.
- All points with `w_expected > 0` are retained.
- Outside points are retained by deterministic stride in `(rank,ispec,k,j,i)`
  order.
- No unseeded random sampling is used.
- Metadata records full source count, exported count, outside stride, and
  retained counts by category.

Duplicate handling:

- The unique plotting key is `(rank, iglob)`.
- Footprint, CMB, spacing, and section plots deduplicate by `(rank, iglob)`.
- Material-ratio plots use all `record_kind=element_gll` rows.
- Duplicate records must agree in coordinates, category, `w_expected`, and
  present material ratios and residuals within metadata tolerances.

## 8. Portability And Reproducibility

To preserve artifacts in a controlled location:

```bash
cd specfem3d_globe/tests/meshfem3D
KEEP_TEST_WORKDIR=1 \
TEST_WORK_ROOT="$HOME/specfem-ulvz-test-artifacts" \
EXPORT_MESH_VIZ_DATA=1 \
./6.test_s40rts_ulvz_mesh.sh
```

When comparing servers or SPECFEM versions, retain:

- `mesh_visualization_metadata.json`
- `mesh_gll_points.csv.gz`
- `comparison_summary.csv`
- `comparison_summary.txt`
- `preflight_summary.txt`
- case manifests
- parameter files
- checksums
- SPECFEM version
- git commit, when available
- MPI command
- `OMP_NUM_THREADS`
- fixture configuration
- figure summaries and `all_figures_manifest.json`

The CSV/JSON files are the portable interface. Raw binary databases depend on
SPECFEM version, compile options, and local database layout, so the Python
tools do not treat them as direct plotting inputs.

## 9. Troubleshooting

Missing visualization export files:

Run the Task 3D fixture with both `EXPORT_MESH_VIZ_DATA=1` and
`KEEP_TEST_WORKDIR=1`. Confirm that you are pointing `--data-dir` at the
preserved `reports` directory.

Absent core, taper, or outside samples:

Check `preflight_summary.txt` and `comparison_summary.csv`. The Task 3D
fixture should have nonzero counts for all three categories. If a category is
missing, confirm that the fixture Par_file and ULVZ parameters match Task 3D.

Missing VSH/VPH fields:

Check `mesh_visualization_metadata.json`. Missing VSH/VPH columns are allowed
only when `fields_present` marks those fields absent.

CSV schema or version mismatch:

Check `schema_version` in metadata. The expected version is
`ulvz_mesh_viz.v1`. Use matching plotting tools or regenerate the export.

Insufficient write permission in the output directory:

Choose an `--out-dir` that you can create and write. The plotting scripts
should write only under `--out-dir`.

Headless Matplotlib failure:

Set:

```bash
export MPLBACKEND=Agg
export MPLCONFIGDIR="${TMPDIR:-/tmp}/ulvz-mplconfig"
export XDG_CACHE_HOME="${TMPDIR:-/tmp}/ulvz-xdg-cache"
```

Then rerun the plotting command from the same shell.

Optional PyVista/VTK import or OpenGL failure:

Use `make_all_figures.py` and the static Matplotlib scripts for the required
workflow. The 3-D viewer is optional and may depend on server OpenGL, EGL, or
OSMesa support.

ParaView exporter VTK import failure:

Activate an environment that includes VTK or PyVista. This is not required
for `make_all_figures.py` or any default static Matplotlib plot.

Unexpectedly sparse CMB or vertical-section sampling:

The default fixture is intentionally coarse. For vertical sections, increase
`--section-half-width-km` or choose a section azimuth that intersects retained
ULVZ samples. Do not interpret sparse fixture sampling as a production
resolution result.

## 10. Limitations

The default Task 3D fixture is intentionally coarse. It validates code
behavior, not production waveform accuracy.

Figures from the fixture must not be interpreted as a ULVZ resolution study.
They document the implementation-validation mesh and the exported pointwise
oracle checks.

The Python tools require inspector-exported CSV/JSON files. They do not
support arbitrary SPECFEM binary databases directly.

The optional 3-D workflow is best-effort and may depend on local graphics
support. Static Matplotlib figures are the required portable output.

Version compatibility note:

```text
Expected CSV/JSON schema version: ulvz_mesh_viz.v1
```

Any future schema change should be documented explicitly and should either
provide compatibility handling or fail with a clear message naming the
supported and observed schema versions.
