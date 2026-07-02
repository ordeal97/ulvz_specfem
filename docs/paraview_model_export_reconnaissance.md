# ParaView Model Export Reconnaissance

Date: 2026-07-02

## Summary

The preserved S40RTS + ULVZ mesh runs contain `solver_data.bin` databases, not
standalone `proc*_vp.bin`, `proc*_vs.bin`, or `proc*_rho.bin` files. The final
model exporter therefore uses the solver database path as the authoritative
source for actual GLL-node geometry and final material fields.

## Authoritative Data Path

The final model values are assigned in
`specfem3d_globe/src/meshfem3D/get_model.F90`. At each GLL point, the code
first evaluates the reference model, S40RTS mantle perturbations, crustal or
GLL overrides where enabled, and the S40RTS ULVZ overlay. It then stores the
final solver state as:

- `rhostore`
- `kappavstore`
- `muvstore`
- `kappahstore`
- `muhstore`
- `eta_anisostore`

The mesher writes these arrays in
`specfem3d_globe/src/meshfem3D/save_arrays_solver.f90` together with
`xstore/ystore/zstore`, `ibool`, and element metadata into
`proc*_reg1_solver_data.bin`. The solver reads the same layout in
`specfem3d_globe/src/specfem3D/read_arrays_solver.f90`, called through
`read_mesh_databases.F90`.

For the current preserved fixture, this makes `solver_data.bin` the selected
authoritative export source. The exporter converts final solver arrays to:

- `vp = vpv = sqrt((kappavstore + 4/3*muvstore) / rhostore) * velocity_scale`
- `vs = vsv = sqrt(muvstore / rhostore) * velocity_scale`
- `rho = rhostore * density_scale`

where the scale factors match `save_model_meshfiles.f90`.

## Existing Utilities

`utils/Visualization/VTK_ParaView/mesh2vtu` is a legacy C++ converter from a
generic binary `.mesh` format to VTU. Its input format contains point
coordinates, one scalar, and 8-node cell connectivity. It does not read
SPECFEM `DATABASES_MPI`, `solver_data.bin`, `ibool`, or final `vp/vs/rho`.
It is useful only as a VTK XML reference.

`src/auxiliaries/combine_vol_data.F90` combines database-derived volume data
and topology for historical VTK/VTU workflows. It is relevant for connectivity
and post-processing context, but it is not the chosen implementation path for
the preserved runs because those runs do not contain standalone
`proc*_vp/vs/rho.bin` model files.

The existing Python exporters are diagnostic:

- `export_paraview_points.py` exports inspector diagnostic point records such
  as `w_expected` and material ratios.
- `export_paraview_mesh.py` exports corner-only diagnostic hexahedra with cell
  summaries.

Neither should be described as exporting final solver `vp/vs/rho` fields.

## Implemented Export Strategy

`EXPORT_PARAVIEW_MODEL_DATA=1` extends the test inspector to write raw
rank-local records from the enabled run:

```text
rank,ispec,i,j,k,iglob,x_norm,y_norm,z_norm,
radius_km,depth_km,height_above_cmb_km,latitude_deg,longitude_deg,
vp,vs,rho,vpv,vph,vsv,vsh,eta,
vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio,is_tiso
```

`scripts/ulvz_mesh_viz/export_paraview_model.py` converts those records into
GLL-node-resolved linear hexahedral subcells. It uses rank-local,
field-aware node merging: records merge only when `(rank, iglob)`,
coordinates, exported material fields, and exported ratio fields agree within
documented tolerances. Coincident records with distinct final material or ratio
values remain separate VTK points to preserve discontinuities.

The before/after ratio records are produced by element-local pairing against
the disabled run using `(rank, ispec, i, j, k)`. Matching `iglob` and
coordinates are verified before ratios are written. Velocity ratios are formed
from physical enabled and disabled velocities derived with the same solver
definitions, then divided.

The output is accurately described as:

```text
GLL-node-resolved linear subcell visualization of the computational
spectral-element mesh.
```
