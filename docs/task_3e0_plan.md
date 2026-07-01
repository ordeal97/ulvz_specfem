 # Task 3E0 Revised Mesh Visualization Plan

  ## Summary

  目标是在 docs/task_3e_mesh_visualization_plan.md 中规划一个 headless、portable、Python-only plotting workflow，用
  于 Task 3D lightweight S40RTS+ULVZ mesher validation fixture。Python 不读取 SPECFEM binary database；只读取 test-
  only Fortran inspector 导出的 JSON/CSV.GZ。

  当前 inspector 的 preflight_summary.* 和 comparison_summary.* 不足以画逐点 footprint、剖面和残差分布，因此计划最
  小可选扩展 tests/meshfem3D/inspect_s40rts_ulvz_database.f90。默认 Task 3D 仍只保留轻量 summary；只有
  EXPORT_MESH_VIZ_DATA=1 时才导出可视化数据。

  ## Recommended data-export contract

  所有可视化导出使用 schema ulvz_mesh_viz.v1。大表默认 gzip 压缩，pandas.read_csv() 可直接读取，不增加依赖。

   File                Status              Purpose                                 Approx size    Preservation
  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━
   mesh_visualizati    mandatory when      schema、                                     <20 KB    only when export
   on_metadata.json    EXPORT_MESH_VIZ_    fixture、ULVZ、                                        enabled or
                       DATA=1              坐标约定、字段可                                       workdir kept
                                           用性、采样规则、
                                           provenance、
                                           figure
                                           disclaimer
  ──────────────────  ──────────────────  ──────────────────  ─────────────────────────────────  ──────────────────
   mesh_gll_points.    mandatory when      element-GLL 逐记     downsampled 10-40 MB; full may    only when export
   csv.gz              EXPORT_MESH_VIZ_    录数据，供材料验                     be hundreds MB    enabled or
                       DATA=1              证和绘图                                               workdir kept
  ──────────────────  ──────────────────  ──────────────────  ─────────────────────────────────  ──────────────────
   comparison_summa    always mandatory    aggregate                                    <20 KB    always preserved
   ry.csv              in Task 3D          validation                                             with reports
                                           summary,
                                           tolerance, max
                                           residuals,
                                           category counts
  ──────────────────  ──────────────────  ──────────────────  ─────────────────────────────────  ──────────────────
   mesh_section_cel    optional v1         optional section                            1-10 MB    only with
   ls.csv.gz                               cell                                                   explicit
                                           connectivity/                                          section-cell
                                           edge overlay                                           export

  mesh_visualization_metadata.json required fields:

  - schema_version, producer, created_utc, specfem_version, git_commit
  - mpi_command, nproc, omp_num_threads
  - r_planet_km, rcmb_km, coordinate_convention
  - ulvz: center lat/lon, thickness, lateral radius, taper widths, dVp/dVs/dRho
  - fields_present: rho, vsv, vsh, vpv, vph
  - sampling_rule: full source count, exported count, outside stride, retain-all-w_expected>0
  - duplicate_policy: unique plotting key is (rank, iglob)
  - fixture_disclaimer:

    S40RTS ULVZ mesher validation fixture
    NEX_XI=32, NEX_ETA=32, NPROC=2
    Not a production waveform-resolution mesh

  mesh_gll_points.csv.gz required columns:

  - identity: record_id, record_kind=element_gll, rank, ispec, i, j, k, iglob, is_shared_duplicate
  - coordinates: x_norm, y_norm, z_norm, radius_norm, radius_km, depth_km, height_above_cmb_km, latitude_deg,
    longitude_deg

  - local section coordinates: point_azimuth_deg, angular_distance_deg, lateral_distance_km, section_azimuth_deg,
    section_distance_km, cross_section_offset_km

  - oracle/category: w_expected, category with values outside, taper, core
  - material fields where present: {rho,vsv,vsh,vpv,vph}_expected, {rho,vsv,vsh,vpv,vph}_ratio,
    {rho,vsv,vsh,vpv,vph}_residual

  - flags: cmb_boundary_noncomparable, material_changed, is_tiso

  Duplicate semantics:

  - Material-ratio plots use all record_kind=element_gll rows.
  - Footprint and spacing plots first deduplicate by (rank, iglob).
  - Python validator groups by (rank, iglob) and fails if duplicate records disagree in coordinates, category,
    w_expected, or any present material ratio/residual beyond metadata tolerances.

  - is_shared_duplicate=false only for the first deterministic (rank, iglob) occurrence in (rank,ispec,k,j,i)
    order.

  Downsampling:

  - Visualization export is off unless EXPORT_MESH_VIZ_DATA=1.
  - Always retain every row with w_expected > 0.
  - Outside rows are retained by deterministic stride in (rank,ispec,k,j,i) order.
  - Default outside_stride = max(1, ceil(outside_count / 50000)).
  - No unseeded random sampling.
  - Metadata records source count, exported count, stride, and retained counts by category.

  ## Vertical section definition

  section_azimuth_deg is clockwise from local north at the ULVZ centre.

  For each point, compute local tangent-plane offsets from centre:

  - north_km = lateral_distance_km * cos(point_azimuth_deg)
  - east_km = lateral_distance_km * sin(point_azimuth_deg)
  - profile unit vector: (east, north) = (sin(section_azimuth_deg), cos(section_azimuth_deg))
  - section_distance_km is signed along-profile distance.
  - cross_section_offset_km is absolute perpendicular distance from the profile.

  plot_vertical_section.py required CLI:

  --section-azimuth-deg FLOAT
  --section-half-width-km FLOAT

  Defaults:

  - --section-azimuth-deg: use metadata default, initially 0.0 unless inspector records another fixture-specific
    default.

  - --section-half-width-km: auto-compute from deduplicated near-CMB points. Select the lowest radial decile above
    the CMB, compute 2-D nearest-neighbor spacing in local tangent coordinates, and use 2.0 * median_nn_spacing_km.

  - If the auto-width still selects no core/taper points, fail clearly and suggest rerunning with explicit
    --section-half-width-km.

  ## Proposed Python package layout

  Future directory: tools/ulvz_mesh_viz/.

   Script              validate_plot_data.py
   Required            yes
   Inputs              metadata, mesh_gll_points.csv.gz, comparison summary, optional cells
   Outputs             plot_data_validation_summary.json/txt
   Headless            yes
   Failure conditions  bad schema, missing columns, absent outside/taper/core, duplicate (rank,iglob) inconsistency
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Script              plot_fixture_overview.py
   Required            yes
   Inputs              metadata, points
   Outputs             01_fixture_domain_ulvz_footprint.png/pdf + summary JSON
   Headless            yes
   Failure conditions  no valid unique coordinates
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Script              plot_cmb_sampling.py
   Required            yes
   Inputs              metadata, points
   Outputs             02_cmb_ulvz_sampling.png/pdf + summary JSON
   Headless            yes
   Failure conditions  no near-CMB unique points or missing category
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Script              plot_vertical_section.py
   Required            yes
   Inputs              metadata, points, optional cells
   Outputs             03_vertical_ulvz_section.png/pdf + summary JSON
   Headless            yes
   Failure conditions  section window lacks core/taper/outside samples
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Script              plot_material_response.py
   Required            yes
   Inputs              metadata, points, comparison
   Outputs             04_material_ratio_validation.png/pdf + summary JSON
   Headless            yes
   Failure conditions  no present material fields; required residual columns missing
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Script              plot_mesh_resolution.py
   Required            yes
   Inputs              metadata, points
   Outputs             05_mesh_sampling_resolution.png/pdf + summary JSON/CSV
   Headless            yes
   Failure conditions  insufficient deduplicated points for spacing stats
   Required            yes
   Inputs              --data-dir, --out-dir
   Outputs             all required figures + all_figures_manifest.json
   Headless            yes
   Failure conditions  any required plot fails
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   Script              view_mesh_3d.py
   Required            optional
   Inputs              metadata, points, optional cells
   Outputs             optional screenshot/HTML
   Headless            optional off-screen
   Failure conditions  PyVista/VTK unavailable or off-screen rendering fails

  All figures and summaries must include the fixture disclaimer text so the output cannot be mistaken for
  production waveform-resolution analysis.

  ## Recommended Conda packages

  Core:

  python=3.11
  numpy
  pandas
  matplotlib
  scipy

  Development/test:

  pytest

  Optional 3-D:

  pyvista
  vtk

  Do not require Cartopy, Basemap, Jupyter, Meshio, or a Python SPECFEM binary reader. Static plotting uses
  MPLBACKEND=Agg, so PNG/PDF rendering works on a headless Linux server. PyVista remains optional because VTK off-
  screen rendering can depend on server OpenGL/EGL/OSMesa support.

  ## Recommended script order

  1. validate_plot_data.py
  2. plot_fixture_overview.py
  3. plot_cmb_sampling.py
  4. plot_vertical_section.py
  5. plot_material_response.py
  6. plot_mesh_resolution.py
  7. make_all_figures.py wraps steps 1-6.

  ## Headless-server workflow

  Future usage:

  export MPLBACKEND=Agg
  python tools/ulvz_mesh_viz/make_all_figures.py \
    --data-dir path/to/s40rts_ulvz_mesh_work_*/reports \
    --out-dir path/to/figures \
    --formats png,pdf

  The scripts use only exported CSV.GZ/JSON, avoid absolute paths, write only under --out-dir, tolerate absent
  VSH/VPH when metadata says absent, and fail if core/taper/outside categories are missing.

  ## Optional PyVista workflow

  python tools/ulvz_mesh_viz/view_mesh_3d.py \
    --metadata reports/mesh_visualization_metadata.json \
    --points reports/mesh_gll_points.csv.gz \
    --out-dir figures/3d \
    --off-screen

  This is excluded from the default pipeline and must not affect static figure generation.

  ## Future implementation task breakdown

  1. Extend only the test inspector with optional EXPORT_MESH_VIZ_DATA=1 gzip CSV/JSON export.
  2. Add synthetic tiny plot-data fixtures, including duplicate (rank,iglob) consistency and missing VSH/VPH cases.
  3. Implement validator and shared loaders.
  4. Implement five static plot scripts and make_all_figures.py.
  5. Add optional PyVista viewer.
  6. Add Python-only tests using MPLBACKEND=Agg pytest, with no MPI, no SPECFEM compilation, no mesh database, and
     no Conda creation by Codex.

  ## Unresolved version-specific issues

  - Current inspector does not yet export pointwise visualization data.
  - TISO/VSH/VPH availability depends on local database layout and must be metadata-driven.
  - CMB-boundary non-comparable records must remain flagged separately from outside/taper/core material validation.
  - Full GLL export can be very large; compressed CSV plus deterministic downsampling is required.
  - mesh_section_cells.csv.gz remains optional for v1.
  - Current Plan Mode means no file was created in this turn; execution should create only docs/
    task_3e_mesh_visualization_plan.md.


  ## Additional required documentation — user guide for ULVZ mesh visualization
    In addition to the Task 3E implementation record, create a user-facing guide:

    docs/ulvz_mesh_visualization_guide.md

    This guide must be written for a researcher who wants to inspect and visualize the S40RTS+ULVZ mesh-validation outputs without reading the Fortran inspector or Python source code.

    It must be maintained as a reusable project document, not as a one-time implementation log.

    Required sections
    1.Purpose and scope
    Explain that the tools visualize and validate the lightweight S40RTS+ULVZ mesher fixture.
    State clearly that the default Task 3D fixture is an implementation-validation mesh, not a production-resolution waveform mesh.
    Explain the distinction between:
    mesh/ULVZ implementation validation;
    mesh-resolution assessment;
    future production waveform simulations.

    2.Prerequisites

    Required Python environment and packages

    Explain headless-server rendering:

    export MPLBACKEND=Agg
    State that Python scripts do not directly read SPECFEM binary databases.
    3.Required input data

    Explain the relationship among:

    mesh_visualization_metadata.json
    mesh_gll_points.csv.gz
    comparison_summary.csv
    preflight_summary.txt
    State which files are mandatory, optional, or version-dependent.

    Explain how to generate/export them from the Task 3D test:

    EXPORT_MESH_VIZ_DATA=1 \
    KEEP_TEST_WORKDIR=1 \
    ./6.test_s40rts_ulvz_mesh.sh
    4.Quick-start workflow

    Give a complete copy-pasteable example:

    export MPLBACKEND=Agg

    python tools/ulvz_mesh_viz/validate_plot_data.py \
    --data-dir path/to/reports \
    --out-dir path/to/figures

    python tools/ulvz_mesh_viz/make_all_figures.py \
    --data-dir path/to/reports \
    --out-dir path/to/figures \
    --formats png,pdf
    Explain expected outputs and directory structure.

    5.Individual plotting scripts
    For every implemented script, provide:

    purpose;
    required inputs;
    example command;
    output figure names;
    major command-line options;
    expected interpretation;
    common failure messages and how to resolve them.

    Include at least:

    validate_plot_data.py
    plot_fixture_overview.py
    plot_cmb_sampling.py
    plot_vertical_section.py
    plot_material_response.py
    plot_mesh_resolution.py
    make_all_figures.py
    view_mesh_3d.py, if implemented

    6.Figure interpretation
    Explain how to interpret the five standard figures:

    01_fixture_domain_ulvz_footprint
    02_cmb_ulvz_sampling
    03_vertical_ulvz_section
    04_material_ratio_validation
    05_mesh_sampling_resolution

    Define:

    outside, taper, and core categories;
    w_expected;
    expected material-ratio behavior;
    residuals;
    why low numbers of core/taper samples indicate an implementation-test mesh rather than a scientifically resolved mesh.
    7.Data conventions
    Document:
    coordinate system;
    normalized Cartesian coordinates;
    latitude/longitude conventions;
    CMB height definition;
    local ULVZ-centred coordinates;
    units for all exported columns;
    deterministic downsampling rules;
    duplicate GLL-point handling.
    8.Portability and reproducibility

    Show how to preserve artifacts:

    KEEP_TEST_WORKDIR=1 \
    TEST_WORK_ROOT="$HOME/specfem-ulvz-test-artifacts" \
    EXPORT_MESH_VIZ_DATA=1 \
    ./6.test_s40rts_ulvz_mesh.sh
    Explain which metadata, checksums, SPECFEM version, MPI command, and fixture configuration should be retained when comparing servers or SPECFEM versions.
    Explain that CSV/JSON exports are the portable interface; raw binary databases are version/build dependent.
    9.Troubleshooting
    Cover at minimum:
    missing visualization export files;
    absent core/taper/outside samples;
    missing VSH/VPH fields;
    CSV schema/version mismatch;
    insufficient write permission in output directory;
    headless Matplotlib failure;
    optional PyVista/VTK import or OpenGL failure;
    unexpectedly sparse CMB or vertical-section sampling.
    10.Limitations
    State explicitly:
    the default Task 3D fixture is intentionally coarse;
    it validates code behavior, not production waveform accuracy;
    figures from the fixture must not be interpreted as a ULVZ resolution study;
    the Python tools require inspector-exported CSV/JSON and do not support arbitrary SPECFEM binary databases directly.


    Documentation quality requirements
    Use relative repository paths only.
    Include shell commands that users can copy directly.
    Do not expose internal Codex prompts, hidden planning history, or machine-specific absolute paths.
    Keep scientific assumptions consistent with the Task 3C/3D documentation.
    Include a short “version compatibility” note identifying the expected CSV/JSON schema version.

    Link to:

    docs/task_3c_external_s40rts_ulvz.md
    docs/task_3d_s40rts_ulvz_mesh_test.md
    Add this guide to the final Task 3E changed-files list and mention it in the Task 3E completion summary.