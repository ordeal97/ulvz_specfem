# Task 3F ParaView Export

## Scope

Task 3F adds optional ParaView export for the Task 3D lightweight
S40RTS+ULVZ mesher validation fixture. It does not modify production SPECFEM
source code, does not parse arbitrary SPECFEM binary databases from Python,
does not run `xspecfem3D`, and does not create a production-scale mesh.

The default static plotting workflow remains independent of VTK and PyVista.
Only these optional exporter scripts import VTK:

- `scripts/ulvz_mesh_viz/export_paraview_points.py`
- `scripts/ulvz_mesh_viz/export_paraview_mesh.py`
- `scripts/ulvz_mesh_viz/export_paraview_model.py`

The first two are diagnostic exporters. They expose ULVZ validation weights,
ratios, categories, and a corner-only diagnostic mesh. The final model exporter
is separate and uses final solver arrays from `proc*_reg1_solver_data.bin`.

## Data Products

Point cloud export:

```bash
python scripts/ulvz_mesh_viz/export_paraview_points.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview
```

Outputs:

- `ulvz_gll_points.vtp`
- `ulvz_gll_points_metadata.json`

Mesh export:

```bash
python scripts/ulvz_mesh_viz/export_paraview_mesh.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview
```

Outputs:

- `ulvz_mesh_rank000000.vtu`
- `ulvz_mesh_rank000001.vtu`
- `ulvz_mesh.pvtu`
- `ulvz_mesh_metadata.json`

Generate both input CSV interfaces from the preserved Task 3D work directory:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_MESH_VIZ_DATA=1 \
EXPORT_PARAVIEW_MESH_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh
```

The shell harness compresses the test-inspector CSV products with
`gzip -n -f`.

Final model export:

```bash
cd specfem3d_globe/tests/meshfem3D
EXPORT_PARAVIEW_MODEL_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh

python ../../../scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_model
```

Outputs:

- `ulvz_model_gll_points.vtp`
- `ulvz_model_mesh_rank000000.vtu`
- `ulvz_model_mesh_rank000001.vtu`
- `ulvz_model_mesh.pvtu`
- `ulvz_model_metadata.json`

Whole-fixture final model export:

```bash
cd specfem3d_globe/tests/meshfem3D
PARAVIEW_MODEL_EXPORT_REGION=all \
PARAVIEW_MODEL_EXPORT_MAX_CELLS=1600000 \
EXPORT_PARAVIEW_MODEL_DATA=1 \
KEEP_TEST_WORKDIR=1 \
./6.test_s40rts_ulvz_mesh.sh

python ../../../scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/reports \
  --out-dir s40rts_ulvz_mesh_work_YYYYMMDD_HHMMSS_PID/paraview_model_full \
  --full-mesh
```

Full-mesh outputs:

- `ulvz_full_model_gll_points.vtp`
- `ulvz_full_model_mesh_rank000000.vtu`
- `ulvz_full_model_mesh_rank000001.vtu`
- `ulvz_full_model_mesh.pvtu`
- `ulvz_full_model_metadata.json`

`--full-mesh` requires raw metadata `region = all`. If the raw records came
from the default `ulvz-window` selection, conversion fails instead of silently
creating misleading whole-mesh file names.

The model exporter derives `vp`, `vs`, and `rho` only from final solver arrays
stored in `solver_data.bin`; it does not infer them from diagnostic masks,
`w_expected`, categories, or analytical ULVZ expectations.

The raw model records also contain dimensionless before/after ratios:

```text
vp_ratio, vs_ratio, rho_ratio, vpv_ratio, vph_ratio, vsv_ratio, vsh_ratio
```

These ratios are paired element-locally. Each enabled record is matched only
to the disabled record with the same `(rank, ispec, i, j, k)`, and the
exporter additionally verifies matching `iglob` and coordinates. A topology,
rank-count, coordinate, or pairing mismatch is a hard failure. Velocity ratios
are computed after deriving enabled and disabled physical velocities with the
same solver definitions; they are not reconstructed from elastic-modulus
ratios. Cell ratio summaries are arithmetic means of the eight corner ratio
values of each exported linear GLL subcell.

## Coordinates

VTP point coordinates are physical Cartesian kilometers:

```text
x_km = x_norm * r_planet_km
y_km = y_norm * r_planet_km
z_km = z_norm * r_planet_km
```

The normalized SPECFEM coordinates are preserved as point-data arrays
`x_norm`, `y_norm`, and `z_norm`.

VTU/PVTU mesh nodes use physical Cartesian kilometers and preserve normalized
coordinates plus radius, height above the CMB, latitude, longitude, rank,
`iglob`, and rank-local `node_id`.

## Hexahedron Ordering

The local SPECFEM VTK/VTU ordering is verified from
`specfem3d_globe/src/auxiliaries/combine_vol_data.F90`, where connectivity is
written from the bottom face followed by the top face:

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

The exported mesh cells are linear 8-corner `VTK_HEXAHEDRON` cells. They are
intended for overview, clipping, slicing, thresholding, and surface
extraction. They do not preserve the full high-order curved spectral-element
geometry.

## Cell Selection

`PARAVIEW_MESH_REGION` controls test-inspector mesh CSV export:

- `ulvz-window`, default: inspect all GLL points in each element and export
  every element with at least one GLL point satisfying `w_expected > 0`.
- `near-cmb`: export cells whose center height above the CMB is in
  `[0, 160]` km.
- `all`: export all elements.

`ulvz-window` selection is not corner-only. It checks every
`NGLLX * NGLLY * NGLLZ` point in each element. Optional context cells are
included only when `PARAVIEW_MESH_CONTEXT_MARGIN_KM` is set explicitly.
`PARAVIEW_MESH_MAX_CELLS` is a hard failure limit and never silently
truncates.

Cell scalar arrays are aggregated from pointwise GLL values:

- `cell_w_expected_mean/min/max`
- `rho/vsv/vsh/vpv/vph_ratio_mean/min/max`
- `cell_has_outside`, `cell_has_taper`, `cell_has_core`
- `cell_category_code`: outside=0, taper=1, core=2, mixed=3
- `material_changed_fraction`

Ratios are aggregated from pointwise ratios. They are not reconstructed from
averaged elastic or density parameters.

## Node Policy

Default mesh export is rank-local:

- one VTU piece per rank;
- one `ulvz_mesh.pvtu` wrapper;
- no implicit merge of partition-boundary nodes;
- `iglob` is treated as rank-local for uniqueness.

For a single-file coordinate-welded export, use:

```bash
python scripts/ulvz_mesh_viz/export_paraview_mesh.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview_welded \
  --weld-coordinates \
  --weld-tolerance 1.0e-6
```

The welded output records `node_merge_policy`, `weld_tolerance`,
`number_of_rank_local_nodes`, `number_of_welded_nodes`, and
`number_of_exported_cells` in `ulvz_mesh_metadata.json`. Welding is never
implicit.

For model fields, the analogous explicit welded commands are:

```bash
python scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview_model_welded \
  --weld-coordinates \
  --weld-tolerance 1.0e-6

python scripts/ulvz_mesh_viz/export_paraview_model.py \
  --data-dir path/to/reports \
  --out-dir path/to/paraview_model_full_welded \
  --full-mesh \
  --weld-coordinates \
  --weld-tolerance 1.0e-6
```

The full-mesh welded command writes `ulvz_full_model_mesh_welded.vtu`.

## ParaView Use

Open `ulvz_gll_points.vtp` for pointwise GLL values, or `ulvz_mesh.pvtu` for
the linearized element mesh.

Open `ulvz_model_mesh.pvtu` for the final-model volume fields. Color by
`vp`, `vs`, `rho`, or the dimensionless ratio arrays. The rank-local PVTU
keeps coincident points separate when coordinates match but final material
fields or ratio fields differ, preserving material discontinuities at
spectral-element interfaces.

Open `ulvz_full_model_mesh.pvtu` when the raw export was generated with
`PARAVIEW_MODEL_EXPORT_REGION=all` and the goal is the whole exported fixture
mesh shape. In `Surface With Edges` mode, ParaView shows the edges of the
exported linear GLL subcells. These are real edges in the VTK visualization
mesh, but they are not an exact rendering of SPECFEM's high-order curved
mapping between GLL nodes.

Recommended filters:

- `Threshold` on `cell_w_expected_mean`, `cell_w_expected_max`, or
  `cell_category_code`
- `Clip`
- `Slice`
- `Extract Surface`
- `Cell Data to Point Data`

The Task 3D fixture validates implementation behavior. It is not a
production waveform-resolution mesh and should not be interpreted as a
production ULVZ resolution study.

## Full-Mesh Validation Evidence

The whole-fixture final model path was generated and reopened with VTK on:

```text
specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260703_102747_261318
```

Validation reports:

```text
paraview_model_full/full_mesh_real_fixture_validation.json
paraview_model_full/full_mesh_real_fixture_validation.txt
```

Observed results:

- raw export metadata: `region = all`
- `coordinate_units = km`
- input records: 1,080,000
- spectral elements: 8,640
- exported GLL subcells: 552,960
- rank-local field-aware nodes: 621,922
- coordinate-welded nodes: 614,141
- `weld_tolerance = 1.0e-6 km`
- `field_aware_split_count = 38667`
- readable VTP, both rank-local VTU pieces, PVTU, and welded VTU
- required final field arrays and ratio arrays are present
- negative-volume count: 0
- near-zero-volume count: 0 with threshold `1.0e-12 km^3`
