  # Task 3F ParaView Export Implementation Plan

  ## Summary

  实现 Task 3F 的 ParaView 导出，但仍只修改测试/脚本/文档路径，不改生产 SPECFEM 源码，不解析原始 SPECFEM 二进制数据
  库，不运行 xspecfem3D 或生产尺度网格。

  计划修改/新增文件：

  - Modify: specfem3d_globe/tests/meshfem3D/inspect_s40rts_ulvz_database.f90
  - Modify: specfem3d_globe/tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh
  - Add: scripts/ulvz_mesh_viz/export_paraview_points.py
  - Add: scripts/ulvz_mesh_viz/export_paraview_mesh.py
  - Modify/add helpers/tests under scripts/ulvz_mesh_viz/ and tests/ulvz_mesh_viz/
  - Modify: docs/ulvz_mesh_visualization_guide.md
  - Add: docs/task_3f_paraview_export.md

  默认静态绘图管线保持独立：现有 validate_plot_data.py、make_all_figures.py、静态 plot 脚本不导入 pyvista 或 vtk；
  只有两个 ParaView exporter 脚本允许导入它们，并在缺失时给出明确安装/环境提示。

  ## Key Interfaces And Data Products

  - export_paraview_points.py
      - Inputs: mesh_visualization_metadata.json plus mesh_gll_points.csv or .csv.gz.
      - Outputs: ulvz_gll_points.vtp plus documented metadata field-data or sidecar.
      - Modes: --records default preserves duplicate element-GLL records; --unique-points deduplicates by (rank,
        iglob) only after the same consistency checks as validate_plot_data.py, rejecting inconsistent duplicates.

      - VTP coordinates are physical Cartesian km: (x_norm, y_norm, z_norm) * r_planet_km; preserve x_norm, y_norm,
        z_norm as point-data arrays; metadata records coordinate_units = km.

  - Test-only Fortran mesh export
      - Enabled only with EXPORT_PARAVIEW_MESH_DATA=1.
      - Requires KEEP_TEST_WORKDIR=1; shell harness fails early with a clear message otherwise.
      - Fortran inspector writes plain rank-local CSV files; shell harness compresses with gzip -n -f to
        required .csv.gz products.

      - Reports directory products:
          - paraview_mesh_nodes_rankXXXXXX.csv.gz
          - paraview_mesh_cells_rankXXXXXX.csv.gz
          - paraview_mesh_metadata.json

      - Metadata states: cells are 8-corner linear VTK hexahedra for overview/clipping/slicing/thresholding and do
        not preserve full high-order curved spectral-element geometry.

  - export_paraview_mesh.py
      - Inputs: rank-local mesh CSV.GZ files and paraview_mesh_metadata.json.
      - Default output layout is rank pieces plus wrapper:
          - ulvz_mesh_rank000000.vtu
          - ulvz_mesh_rank000001.vtu
          - ulvz_mesh.pvtu

      - Optional single-file output is allowed only with explicit coordinate welding and validation; if duplicate
        partition-boundary nodes are retained, metadata labels it as non-welded.

      - Metadata records node_merge_policy, weld_tolerance, number_of_rank_local_nodes, number_of_welded_nodes, and
        number_of_exported_cells.

  ## Verified Hexahedron Ordering

  Local SPECFEM source verification comes from specfem3d_globe/src/auxiliaries/combine_vol_data.F90, where
  total_dat_con(1..8) is written from ibool(i,j,k), ibool(i+di,j,k), ibool(i+di,j+dj,k), ibool(i,j+dj,k), then the
  same four nodes at k+dk.

  For Task 3F full spectral-element corner export, use this exact VTK hexahedron node order:

  - node0 = ibool(1,1,1,ispec)
  - node3 = ibool(1,NGLLY,1,ispec)
  - node4 = ibool(1,1,NGLLZ,ispec)
  - node5 = ibool(NGLLX,1,NGLLZ,ispec)
  - node6 = ibool(NGLLX,NGLLY,NGLLZ,ispec)
  - node7 = ibool(1,NGLLY,NGLLZ,ispec)

  Tests will include a unit-cube hexahedron and verify VTK_HEXAHEDRON, expected volume, and positive/non-inverted
  orientation. The real fixture validation will report negative or zero-volume linearized cell count.

  ## Mesh Selection And Scalars

  - Region settings:
      - PARAVIEW_MESH_REGION=all|near-cmb|ulvz-window, default ulvz-window.
      - PARAVIEW_MESH_MAX_CELLS, default 200000; exceedance is a hard failure, never silent truncation.
      - near-cmb: select cells whose center height above CMB is within documented [0, 160] km.
      - ulvz-window: inspect all local GLL points of each element and export every element with at least one GLL
        point satisfying w_expected > 0.

      - Optional context cells use explicit PARAVIEW_MESH_CONTEXT_MARGIN_KM; if unset, no undocumented fixed
        lateral margin is applied. The chosen value is recorded in metadata.

  - Cell scalar aggregation:
      - Compute rho/vsv/vsh/vpv/vph ratios at each GLL point using the existing pointwise formulas.
      - Aggregate from pointwise ratios only; do not reconstruct ratios from averaged elastic/density parameters.
      - Export ratio mean, min, and max per cell for each quantity.
      - Export category membership as cell_has_outside, cell_has_taper, cell_has_core, and cell_category_code,
        where codes are outside=0, taper=1, core=2, mixed=3; any cell spanning multiple categories is mixed.

      - Export material_changed_fraction from pointwise changed flags or ratio differences, documented consistently
        in metadata.

  ## Expected ParaView Arrays

  - VTP point-data arrays include, when present:
    w_expected, category_code, material_changed, cmb_boundary_noncomparable,
    rho_ratio, vsv_ratio, vsh_ratio, vpv_ratio, vph_ratio,
    rho_residual, vsv_residual, vsh_residual, vpv_residual, vph_residual,
    height_above_cmb_km, lateral_distance_km,
    section_distance_km, cross_section_offset_km,
    rank, ispec, iglob, plus preserved x_norm, y_norm, z_norm.

  - VTU/PVTU point-data arrays include:
    rank, iglob, node_id, x_norm, y_norm, z_norm,
    radius_km, height_above_cmb_km, latitude_deg, longitude_deg.

  - VTU/PVTU cell-data arrays include:
    rank, ispec, cell_id,
    cell_center_radius_km, cell_center_height_above_cmb_km,
    cell_w_expected_mean, cell_w_expected_min, cell_w_expected_max,
    cell_has_outside, cell_has_taper, cell_has_core, cell_category_code,
    material_changed_fraction,
    ratio mean/min/max arrays for rho, vsv, vsh, vpv, and vph.

  ## Test And Verification Plan

  - Python-only synthetic tests under tests/ulvz_mesh_viz/:
      - export_paraview_points.py --help succeeds.
      - VTP round-trip with PyVista preserves point count and scalar arrays.
      - --unique-points rejects inconsistent duplicate (rank, iglob) rows.
      - export_paraview_mesh.py --help succeeds.
      - One-hexahedron unit cube writes readable VTU/PVTU, has expected point/cell counts, VTK_HEXAHEDRON cell
        type, expected volume, and positive orientation.

      - Expected point/cell arrays and metadata are preserved as VTK field data or documented sidecar JSON.

  - Real lightweight integration:
      - Run from specfem3d_globe/tests/meshfem3D:
        EXPORT_MESH_VIZ_DATA=1 EXPORT_PARAVIEW_MESH_DATA=1 KEEP_TEST_WORKDIR=1 ./6.test_s40rts_ulvz_mesh.sh

      - Then run both exporters into the preserved workdir paraview/.
      - Reopen VTP and PVTU/VTU with PyVista and report:
        bounds in km, point count, cell count, cell types, point-data arrays, cell-data arrays, core/taper/outside/
        mixed cell counts, negative/zero-volume cell count, node merge policy/result, and output file sizes.

      - Use writable temporary MPLCONFIGDIR and XDG_CACHE_HOME, and MPLBACKEND=Agg for static plotting/tests.

  ## Documentation

  - Update docs/ulvz_mesh_visualization_guide.md with actual commands, output paths, troubleshooting, and ParaView
    opening steps.

  - Create docs/task_3f_paraview_export.md documenting:
      - VTP point cloud vs VTU/PVTU linearized element mesh.
      - Physical km coordinates and preserved normalized coordinates.
      - Exact VTK corner ordering.
      - Region selection and size safety.
      - Node merge policy and rank-local iglob limitation.
      - Recommended ParaView filters: Threshold on cell_w_expected_mean, Clip, Slice, Extract Surface, Cell Data to
        Point Data.

      - Warning that Task 3D fixture validates implementation, not waveform-resolution adequacy.
