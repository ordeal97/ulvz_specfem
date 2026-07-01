# Task 3E Mesh Visualization Plan

## Scope

Task 3E plans a headless, portable, Python-only visualization workflow for
the Task 3D lightweight S40RTS+ULVZ mesher validation fixture. The workflow
must visualize and validate inspector-exported CSV/JSON products. It must not
read SPECFEM binary databases directly.

The authoritative upstream validation specification is
`docs/task_3d_plan.md`. The implemented Task 3D fixture is documented in
`docs/task_3d_s40rts_ulvz_mesh_test.md`, and the S40RTS ULVZ overlay is
documented in `docs/task_3c_external_s40rts_ulvz.md`.

The default Task 3D fixture is an implementation-validation mesh:

```text
S40RTS ULVZ mesher validation fixture
NEX_XI=32, NEX_ETA=32, NPROC=2
Not a production waveform-resolution mesh
```

All Task 3E figures, summaries, metadata, and user-facing documentation must
include that disclaimer or an equivalent unambiguous statement.

## Scientific And Reproducibility Constraints

- Do not change Task 3C or Task 3D scientific assumptions.
- Do not modify production `specfem3d_globe/DATA/Par_file`.
- Do not modify production SPECFEM source code for Task 3E.
- Do not require Cartopy, Basemap, Jupyter, Meshio, or a Python SPECFEM binary
  reader for static plotting.
- Do not add a required dependency beyond Python 3.11, NumPy, pandas,
  Matplotlib, SciPy, and pytest for tests.
- Static plotting must work with `MPLBACKEND=Agg` on a headless Linux server.
- PyVista/VTK may be used only by an optional 3-D viewer and must not affect
  the required static figure pipeline.
- Scripts must use relative repository paths in documentation examples.
- Scripts must write only under the user-provided `--out-dir`.
- CSV/JSON exports are the portable interface. Raw SPECFEM binary databases
  are version- and build-dependent.

## Data Export Contract

The visualization export schema is `ulvz_mesh_viz.v1`.

Task 3D currently preserves aggregate reports. Task 3E requires a small,
optional extension to the test-only inspector
`specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90` so that
pointwise visualization data are emitted only when
`EXPORT_MESH_VIZ_DATA=1`.

The default Task 3D behavior remains lightweight. Without
`EXPORT_MESH_VIZ_DATA=1`, the fixture continues to write only the summary
reports required by Task 3D.

### Required Files

| File | Status | Purpose | Preservation |
| --- | --- | --- | --- |
| `mesh_visualization_metadata.json` | Mandatory when `EXPORT_MESH_VIZ_DATA=1` | Schema, fixture, ULVZ parameters, coordinate conventions, fields, sampling, provenance, and figure disclaimer | Only when export is enabled or the work directory is kept |
| `mesh_gll_points.csv.gz` | Mandatory when `EXPORT_MESH_VIZ_DATA=1` after harness compression | Element-GLL point records for validation and plotting | Only when export is enabled and `KEEP_TEST_WORKDIR=1` |
| `comparison_summary.csv` | Always mandatory in Task 3D | Aggregate validation summary, tolerances, residuals, and category counts | Always preserved with reports |
| `mesh_section_cells.csv.gz` | Optional in schema v1 | Section cell connectivity or edge overlay for selected views | Only with explicit section-cell export |

`preflight_summary.txt` remains useful for human inspection of category
coverage, CMB boundary counts, radius ranges, and PASS/FAIL status, but it is
not sufficient for pointwise visualization.

### Metadata Fields

`mesh_visualization_metadata.json` must contain:

- `schema_version`
- `producer`
- `created_utc`
- `specfem_version`
- `git_commit`
- `mpi_command`
- `nproc`
- `omp_num_threads`
- `r_planet_km`
- `rcmb_km`
- `coordinate_convention`
- `ulvz`
- `fields_present`
- `sampling_rule`
- `duplicate_policy`
- `fixture_disclaimer`
- `tolerances`

The `ulvz` object must record center latitude and longitude, thickness,
lateral radius, lateral taper width, top taper width, `dVp`, `dVs`, and
`dRho`.

The `fields_present` object must drive material plotting. The Python tools
must tolerate absent `vsh` and `vph` columns when metadata says those fields
are absent, and they must fail clearly when metadata says a field is present
but the matching columns are missing.

The `sampling_rule` object must record full source count, exported count,
outside stride, and retained counts by category.

The `duplicate_policy` object must state that the unique plotting key is
`(rank, iglob)`.

### Point CSV Columns

The inspector writes `mesh_gll_points.csv` as plain CSV. The Task 3D shell
harness compresses it with `gzip -n -f` when `EXPORT_MESH_VIZ_DATA=1`.
Python loaders must accept both `mesh_gll_points.csv` and
`mesh_gll_points.csv.gz`.

`mesh_gll_points.csv` and `mesh_gll_points.csv.gz` must include these columns.

Identity:

- `record_id`
- `record_kind`
- `rank`
- `ispec`
- `i`
- `j`
- `k`
- `iglob`
- `is_shared_duplicate`

Coordinates:

- `x_norm`
- `y_norm`
- `z_norm`
- `radius_norm`
- `radius_km`
- `depth_km`
- `height_above_cmb_km`
- `latitude_deg`
- `longitude_deg`

Local ULVZ-centred section coordinates:

- `point_azimuth_deg`
- `angular_distance_deg`
- `lateral_distance_km`
- `section_azimuth_deg`
- `section_distance_km`
- `cross_section_offset_km`

Oracle and category:

- `w_expected`
- `category`

Allowed category values are:

- `outside`
- `taper`
- `core`

Material fields, when present:

- `{rho,vsv,vsh,vpv,vph}_expected`
- `{rho,vsv,vsh,vpv,vph}_ratio`
- `{rho,vsv,vsh,vpv,vph}_residual`

Flags:

- `cmb_boundary_noncomparable`
- `material_changed`
- `is_tiso`

## Duplicate Semantics

Material-ratio validation and material-ratio plots use all
`record_kind=element_gll` rows.

Footprint, CMB sampling, spacing, and section plots first deduplicate by
`(rank, iglob)`.

The Python validator must group by `(rank, iglob)` and fail if duplicate
records disagree beyond metadata tolerances in:

- coordinates
- `category`
- `w_expected`
- any present material ratio
- any present residual

`is_shared_duplicate=false` must be assigned only to the first deterministic
`(rank, iglob)` occurrence in `(rank,ispec,k,j,i)` order.

## Downsampling

Visualization export is disabled unless `EXPORT_MESH_VIZ_DATA=1`.
`EXPORT_MESH_VIZ_DATA=1` requires `KEEP_TEST_WORKDIR=1`; the Task 3D harness
must fail early otherwise so exported plot data are not removed during
cleanup.

When visualization export is enabled:

- retain every row with `w_expected > 0`;
- retain outside rows by deterministic stride in `(rank,ispec,k,j,i)` order;
- set default `outside_stride = max(1, ceil(outside_count / 50000))`;
- do not use unseeded random sampling;
- write full source count, exported count, stride, and retained category
  counts to metadata.

This keeps the default visualization artifact portable while preserving all
core and taper points for the validation fixture.

## Coordinate Conventions

The Task 3D oracle uses SPECFEM normalized Cartesian coordinates and converts
to kilometers with `R_PLANET = 6371.0 km` and `RCMB = 3480.0 km`.

For each exported GLL point:

```text
radius_norm = sqrt(x_norm^2 + y_norm^2 + z_norm^2)
radius_km = radius_norm * 6371.0
depth_km = 6371.0 - radius_km
height_above_cmb_km = radius_km - 3480.0
latitude_deg = geographic latitude from Cartesian coordinates
longitude_deg = geographic longitude from Cartesian coordinates
lateral_distance_km = 3480.0 * angular_distance_rad
```

Longitudes should be normalized consistently and documented in metadata. The
ULVZ centre for the Task 3D fixture is geographic latitude 45 degrees and
longitude 140 degrees.

## Vertical Section Definition

`section_azimuth_deg` is clockwise from local north at the ULVZ centre.

For each point, compute local tangent-plane offsets from the ULVZ centre:

```text
north_km = lateral_distance_km * cos(point_azimuth_deg)
east_km = lateral_distance_km * sin(point_azimuth_deg)
profile_east = sin(section_azimuth_deg)
profile_north = cos(section_azimuth_deg)
section_distance_km = east_km * profile_east + north_km * profile_north
cross_section_offset_km = abs(east_km * profile_north - north_km * profile_east)
```

`plot_vertical_section.py` must provide:

```text
--section-azimuth-deg FLOAT
--section-half-width-km FLOAT
```

Defaults:

- `--section-azimuth-deg` uses metadata when present, otherwise `0.0`.
- `--section-half-width-km` is auto-computed from deduplicated near-CMB
  points.

The auto-width rule is:

1. Select the lowest radial decile above the CMB from deduplicated points.
2. Compute two-dimensional nearest-neighbor spacing in local tangent
   coordinates.
3. Use `2.0 * median_nn_spacing_km`.

If the resulting window selects no core or taper points, the script must fail
clearly and suggest rerunning with explicit `--section-half-width-km`.

## Python Package Layout

The required implementation directory is:

```text
scripts/ulvz_mesh_viz/
```

The package should include shared loader, validation, plotting, and summary
helpers rather than duplicating schema and plotting logic across scripts.

Recommended shared modules:

- `io.py` or `data.py` for loading metadata, points, and comparison summary
- `schema.py` for required-column and schema-version checks
- `geometry.py` for section coordinate and spacing utilities
- `plotting.py` for common Matplotlib configuration, disclaimer text, and
  output writing

All command-line scripts must use `argparse`, support `--help`, and write
machine-readable summary files under `--out-dir`.

## Required Scripts

### `validate_plot_data.py`

Purpose: validate the exported CSV/JSON plotting interface before figure
generation.

Inputs:

- `--data-dir`
- `--out-dir`
- optional explicit `--metadata`, `--points`, `--comparison-summary`, and
  `--section-cells`

Outputs:

- `plot_data_validation_summary.json`
- `plot_data_validation_summary.txt`

Failure conditions:

- bad or unsupported schema
- missing mandatory files
- missing required columns
- absent `outside`, `taper`, or `core` categories
- duplicate `(rank, iglob)` inconsistencies
- metadata says a material field is present but required columns are absent
- comparison summary lacks required aggregate residual or tolerance records

### `plot_fixture_overview.py`

Purpose: show the fixture domain and ULVZ footprint so users can confirm that
the exported data correspond to the expected Task 3D validation setup.

Inputs:

- metadata
- points

Outputs:

- `01_fixture_domain_ulvz_footprint.png`
- `01_fixture_domain_ulvz_footprint.pdf` when PDF output is requested
- `01_fixture_domain_ulvz_footprint_summary.json`

Failure condition:

- no valid unique coordinates after deduplication

### `plot_cmb_sampling.py`

Purpose: show near-CMB point sampling and the `outside`, `taper`, and `core`
categories around the ULVZ footprint.

Inputs:

- metadata
- points

Outputs:

- `02_cmb_ulvz_sampling.png`
- `02_cmb_ulvz_sampling.pdf` when PDF output is requested
- `02_cmb_ulvz_sampling_summary.json`

Failure conditions:

- no near-CMB unique points
- missing or invalid `category`

### `plot_vertical_section.py`

Purpose: show a vertical section through the ULVZ centre using signed
along-profile distance and height above the CMB.

Inputs:

- metadata
- points
- optional `mesh_section_cells.csv.gz`

Outputs:

- `03_vertical_ulvz_section.png`
- `03_vertical_ulvz_section.pdf` when PDF output is requested
- `03_vertical_ulvz_section_summary.json`

Major options:

- `--section-azimuth-deg`
- `--section-half-width-km`

Failure condition:

- the section window lacks core, taper, or outside samples

### `plot_material_response.py`

Purpose: compare observed material ratios and residuals against the Task 3D
pointwise analytical oracle.

Inputs:

- metadata
- points
- `comparison_summary.csv`

Outputs:

- `04_material_ratio_validation.png`
- `04_material_ratio_validation.pdf` when PDF output is requested
- `04_material_ratio_validation_summary.json`

Failure conditions:

- no present material fields
- required residual columns missing for a present material field
- comparison summary tolerance or residual records are missing

### `plot_mesh_resolution.py`

Purpose: summarize exported point spacing and sampling density for the
lightweight validation fixture.

Inputs:

- metadata
- points

Outputs:

- `05_mesh_sampling_resolution.png`
- `05_mesh_sampling_resolution.pdf` when PDF output is requested
- `05_mesh_sampling_resolution_summary.json`
- optional spacing-statistics CSV

Failure condition:

- insufficient deduplicated points for spacing statistics

### `make_all_figures.py`

Purpose: run the required validation and static plotting steps in a stable
order.

Required order:

1. `validate_plot_data.py`
2. `plot_fixture_overview.py`
3. `plot_cmb_sampling.py`
4. `plot_vertical_section.py`
5. `plot_material_response.py`
6. `plot_mesh_resolution.py`

Required CLI:

```bash
python scripts/ulvz_mesh_viz/make_all_figures.py \
  --data-dir path/to/reports \
  --out-dir path/to/figures \
  --formats png,pdf
```

Outputs:

- all required static figures
- all per-figure summary JSON files
- `all_figures_manifest.json`

Failure condition:

- any required validation or plotting step fails

### `view_mesh_3d.py`

Purpose: optional 3-D inspection using PyVista/VTK.

This script is optional in Task 3E and must be excluded from the default
static pipeline. PyVista/VTK import or off-screen rendering failures must not
break `make_all_figures.py`.

Example:

```bash
python scripts/ulvz_mesh_viz/view_mesh_3d.py \
  --metadata reports/mesh_visualization_metadata.json \
  --points reports/mesh_gll_points.csv.gz \
  --out-dir figures/3d \
  --off-screen
```

## Standard Figure Set

The required static figure names are:

- `01_fixture_domain_ulvz_footprint`
- `02_cmb_ulvz_sampling`
- `03_vertical_ulvz_section`
- `04_material_ratio_validation`
- `05_mesh_sampling_resolution`

Each figure must include the fixture disclaimer and write a summary JSON file
that records:

- source input paths relative to invocation when practical
- schema version
- category counts used by the plot
- material fields used by the plot, when applicable
- relevant command-line options
- output files written

## Headless Workflow

The intended workflow is:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_MESH_VIZ_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh

export MPLBACKEND=Agg
python ../../../scripts/ulvz_mesh_viz/make_all_figures.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/figures \
  --formats png,pdf
```

The scripts must not create or overwrite simulation cases. They only consume
the existing reports directory and write figures and summaries under
`--out-dir`.

## Test Plan For Future Code Implementation

Task 3E0 is a documentation task. Future code implementation should add
Python-only tests that do not require MPI, SPECFEM compilation, xmeshfem3D,
raw mesh databases, or Conda environment creation during automated
implementation.

Minimum test fixtures:

- tiny synthetic `mesh_visualization_metadata.json`
- tiny synthetic `mesh_gll_points.csv.gz`
- tiny synthetic `comparison_summary.csv`
- duplicate `(rank, iglob)` consistency case
- duplicate `(rank, iglob)` inconsistency failure case
- missing VSH/VPH case where metadata marks those fields absent
- present-field missing-column failure case
- missing category failure case

Minimum test coverage:

- validator rejects unsupported schema versions
- validator rejects missing mandatory columns
- validator accepts absent VSH/VPH when metadata says absent
- validator fails duplicate inconsistencies
- each required plotting script runs with `MPLBACKEND=Agg`
- each required plotting script writes PNG and summary JSON
- `make_all_figures.py` writes `all_figures_manifest.json`
- every script responds to `--help`

## Version Compatibility

The expected visualization schema version is:

```text
ulvz_mesh_viz.v1
```

Schema changes must be explicit and must not silently reinterpret existing
CSV/JSON files. A future schema should add compatibility handling or fail with
a clear message that names the supported and observed versions.

## Task 3E0 Changed Files

Task 3E0 creates the documentation deliverables only:

- `docs/task_3e_mesh_visualization_plan.md`
- `docs/ulvz_mesh_visualization_guide.md`

No production SPECFEM source code, production DATA file, Python plotting code,
or test inspector code is changed by Task 3E0.

## Task 3E0 Completion Summary

This document records the required schema, data-export contract, plotting
workflow, static figure set, optional PyVista workflow, and Python-only test
plan for a future Task 3E implementation.

The companion user guide is `docs/ulvz_mesh_visualization_guide.md`. It is
written for researchers who need to inspect and visualize Task 3D
S40RTS+ULVZ mesh-validation outputs without reading the Fortran inspector or
Python plotting source code.
