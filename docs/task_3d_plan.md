  # Task 3D S40RTS+ULVZ Mesher Fixture With Pointwise Analytical Validation

  Summary

  - Add a two-rank xmeshfem3D integration test with a test-only Par_file, disabled/enabled ULVZ cases, and a
    pointwise material validation inspector.

  - Keep ABSORBING_CONDITIONS = .true..
  - Do not modify production specfem3d_globe/DATA/Par_file or prohibited SPECFEM source/model files.
  - The inspector must independently compute ULVZ geometry/taper as a test oracle and must not call
    model_s40rts.f90 ULVZ helpers.

  Key Changes

  - Add tests/meshfem3D/s40rts_ulvz_mesh_fixture/DATA/Par_file.
      - Values: MODEL=s40rts, NCHUNKS=1, NEX_XI=32, NEX_ETA=32, NPROC_XI=1, NPROC_ETA=2, center lat/lon 45/140,
        angular width 90/90, gamma -130.

      - NPROC_XI * NPROC_ETA = 2; with NCHUNKS=1, NPROCTOT=2, matching mpirun -np 2.
      - REGIONAL_MESH_CUTOFF=.false. so the mesh reaches the CMB.
      - Keep ABSORBING_CONDITIONS=.true. and disable unrelated optional physics/output.

  - Add tests/meshfem3D/inspect_s40rts_ulvz_database.f90.
      - Read local sequential unformatted proc*_reg1_solver_data.bin using the write order in
        save_arrays_solver.f90 and read order in read_arrays_solver.f90.

        NPROCTOT_VAL=2, and configured CUSTOM_REAL=SIZE_REAL.

      - Do not unconditionally read TISO fields; read kappahstore/muhstore/eta_anisostore only when
        TRANSVERSE_ISOTROPY_VAL is true and ANISOTROPIC_3D_MANTLE_VAL is false.

      - Verify geometry/topology records are identical before material comparison: xstore, ystore, zstore, ibool,
        idoubling, ispec_is_tiso, and local derivative/Jacobian records.

  - Implement independent pointwise oracle in the inspector.
      - Recover each GLL point coordinate via iglob = ibool(i,j,k,ispec) and xstore/ystore/zstore.
      - Compute radius_norm = sqrt(x*x+y*y+z*z), radius_km = radius_norm * 6371.0, height_above_cmb_km = radius_km
        - 3480.0.

      - Compute latitude/longitude from Cartesian coordinates, great-circle distance to ULVZ center using clamped
        spherical cosine, and lateral distance as 3480.0 * acos(cosang).

      - Analytical weights:
          - outside if height <0, height > THICKNESS_KM, or lateral distance > LATERAL_RADIUS_KM.
          - lateral core if distance <= LATERAL_RADIUS_KM - LATERAL_TAPER_KM, otherwise 0.5*(1+cos(pi*x)).
          - top core if height <= THICKNESS_KM - TOP_TAPER_KM, otherwise 0.5*(1+cos(pi*y)).
          - w_expected = lateral_weight * top_weight.

  - Validate pointwise ratios for every comparable crust-mantle GLL material value:
      - rho_ratio = rho_enabled / rho_disabled
      - vsv_ratio = sqrt((muv/rho)_enabled / (muv/rho)_disabled)
      - vsh_ratio = sqrt((muh/rho)_enabled / (muh/rho)_disabled)
      - vpv_ratio = sqrt(((kappav + 4/3*muv)/rho)_enabled / same_disabled)
      - vph_ratio = sqrt(((kappah + 4/3*muh)/rho)_enabled / same_disabled)
      - Expected ratios: 1+w*DRHO, 1+w*DVS, 1+w*DVS, 1+w*DVP, 1+w*DVP.

  - Add/modify tests/meshfem3D/6.test_s40rts_ulvz_mesh.sh.
      - Create reference_disabled/ and ulvz_enabled/ temp cases.
      - Copy fixture DATA/Par_file byte-identically.
      - Link required data: DATA/s40rts, DATA/s20rts, DATA/crust2.0.
      - Only DATA/ulvz_s40rts.par may differ; use DVS=-0.20, DVP=-0.10, DRHO=+0.05, center 45/140, thickness 80 km,
        lateral radius 400 km, lateral taper 100 km, top taper 20 km.

      - Run only xmeshfem3D with OMP_NUM_THREADS=1 and mpirun -np 2; never run xspecfem3D.
      - Run inspector and fail on any criterion failure.

  - Add docs/task_3d_s40rts_ulvz_mesh_test.md.
      - Include complete fixture Par_file, selected domain/CMB coverage, MPI decomposition, low-cost settings,
        database layout, oracle formulas, tolerances, observed wall time, output size, and validation report
        summary.

  Pass Criteria

  - Both mesher runs succeed.
  - Case Par_file files are byte-identical; intended input difference is only ulvz_s40rts.par.
  - Geometry/topology records are identical.
  - Material database differs and every comparable GLL material ratio agrees with the pointwise oracle within
    tolerance.

  - Categories have nonzero sample counts:
      - outside: w_expected = 0
      - taper: 0 < w_expected < 1
      - core: w_expected = 1

  - No point below CMB or outside the lateral footprint receives a material change.
  - No wrong-sign material response occurs.
  - Reports include per-field maximum residuals and category counts.

  Tolerances And Reports

  - Use explicit single-precision thresholds because local CUSTOM_REAL = SIZE_REAL; start with absolute ratio
    residual threshold 5.0e-5, and document this in the report.

  - Write comparison_summary.txt and comparison_summary.csv with:
      - SPECFEM version, MPI command/process count, fixture checksum, ULVZ file checksums;
      - files compared and geometry/topology identity evidence;
      - field names, formulas, units/status;
      - per-category sample counts, min/max w_expected, min/max observed ratios;
      - max residuals for rho, vsv, vsh, vpv, vph;
      - pass/fail for each criterion.

  - With KEEP_TEST_WORKDIR=1, preserve both case directories, logs, manifests, checksums, and reports.

  Test Plan

  - From specfem3d_globe/tests/meshfem3D run:
      - timeout 120 ./5.test_s40rts_ulvz.sh
      - timeout 120 ./6.test_s40rts_ulvz_mesh.sh

  - Documentation must be updated with final observed wall time, artifact size, and report excerpts from the actual
    run.

  Assumptions

  - bin/xmeshfem3D is available or built before running Task 3D.
  - If local database layout changes or material fields cannot be reconstructed safely, the inspector stops with an
    unsupported-layout message; do not weaken validation silently or modify production SPECFEM code.
