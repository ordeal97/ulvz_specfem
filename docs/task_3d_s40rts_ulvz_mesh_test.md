# Task 3D S40RTS ULVZ Mesh Fixture Test

## Scope

Task 3D adds a two-rank `xmeshfem3D` integration test for the external
S40RTS ULVZ overlay. It does not run `xspecfem3D` and does not modify
production SPECFEM source code.

The authoritative fixture Par_file is:

```text
specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_fixture/DATA/Par_file
```

Final observed fixture checksum:

```text
4a7b7c76502c33406e8f20a62bfad9961537b247d7c6ddfe78aadf2c95b7945e
```

## Fixture Par_file

The complete fixture Par_file is versioned at the path above. The selected
settings are:

```text
MODEL                           = s40rts
NCHUNKS                         = 1
ANGULAR_WIDTH_XI_IN_DEGREES     = 90.d0
ANGULAR_WIDTH_ETA_IN_DEGREES    = 90.d0
CENTER_LATITUDE_IN_DEGREES      = 45.d0
CENTER_LONGITUDE_IN_DEGREES     = 140.d0
GAMMA_ROTATION_AZIMUTH          = -130.d0
NEX_XI                          = 32
NEX_ETA                         = 32
NPROC_XI                        = 1
NPROC_ETA                       = 2
REGIONAL_MESH_CUTOFF            = .false.
ABSORBING_CONDITIONS            = .true.
OCEANS                          = .false.
ELLIPTICITY                     = .false.
TOPOGRAPHY                      = .false.
GRAVITY                         = .false.
ROTATION                        = .false.
ATTENUATION                     = .false.
ADIOS_ENABLED                   = .false.
ADIOS_FOR_MODELS                = .false.
LOCAL_PATH                      = ./DATABASES_MPI
```

`NPROC_XI * NPROC_ETA = 2`, matching the fixed two-rank test. The script
rejects any `NPROC` other than `2`.

## Domain And CMB Coverage

The fixture uses one 90 by 90 degree regional chunk centered at geographic
latitude 45 degrees and longitude 140 degrees, with gamma rotation -130
degrees. `REGIONAL_MESH_CUTOFF = .false.` keeps the crust-mantle database
down to the CMB.

The disabled-case preflight reads the generated GLL coordinates before the
enabled case is launched. The final preflight observed nonzero category
coverage:

```text
outside taper core counts:          1079936              48              16
CMB boundary non-comparable count:             1182
normalized radius min/max:   5.46134419E-01  1.00000287E+00
R_PLANET_km RCMB_km:   6.37100000E+03  3.48000000E+03
```

The CMB boundary count is reported separately because the local production
mesher applies 3D mantle perturbations only for `r_prem > RCMB/R_PLANET`.
Points on the exact CMB are geometry-valid but not comparable for the S40RTS
ULVZ material-ratio oracle.

## MPI And Resource Use

The script supports portable direct MPI configuration:

```bash
MPIEXEC=${MPIEXEC:-mpirun}
MPI_NPROC_FLAG=${MPI_NPROC_FLAG:--np}
NPROC=${NPROC:-2}
OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
```

Final observed MPI command:

```text
mpirun -np 2 "$SPECFEM_ROOT/bin/xmeshfem3D"
```

Final observed resource summary:

```text
SPECFEM version: 8.1.1
elapsed_seconds: 60
artifact_kib: 117288
du -sh workdir: 140M
```

## DATA Dependencies

The test stages these read-only dependencies as symlinks into each case:

```text
DATA/s40rts
DATA/s20rts
DATA/crust2.0
```

The final run checksummed the required files:

```text
56870490b155cf68ef07056608bab9bfe8147959829db9582e359dbc35353c4f  DATA/s40rts/S40RTS.dat
ef6fcb940158c09bb16e5c45ba426726a4576c866d2f199ac8891fa21692f7ed  DATA/s20rts/P12.dat
a2928e8a4f9ab7f6164d3453801035bdc0f0b244fc88c316041a9cf7776a20ec  DATA/crust2.0/CNtype2.txt
8e6e033938aa2518523ad0d4fc82e6eaf507221da0e0fce8eda4aed0349872c4  DATA/crust2.0/CNtype2_key_modif.txt
6cfdd5b36fad09e727efba49782a962d324237794ff4465c5b9a5ba7c4333038  DATA/crust2.0/CNelevatio2.txt
```

No additional DATA dependency was required by the local run.

## Database Layout

The inspector reads local sequential unformatted crust-mantle files:

```text
DATABASES_MPI/proc000000_reg1_solver_data.bin
DATABASES_MPI/proc000001_reg1_solver_data.bin
```

File names follow `src/shared/create_name_database.f90`. Record order follows
`src/meshfem3D/save_arrays_solver.f90` and is checked against
`src/specfem3D/read_arrays_solver.f90`:

```text
nspec
nglob
xstore
ystore
zstore
ibool
idoubling
ispec_is_tiso
xixstore, xiystore, xizstore
etaxstore, etaystore, etazstore
gammaxstore, gammaystore, gammazstore
rhostore
kappavstore
muvstore
kappahstore, muhstore, eta_anisostore
```

For this local `s40rts` configuration, `TRANSVERSE_ISOTROPY` is true and
`ANISOTROPIC_3D_MANTLE` is false, so the TISO fields are required. The
inspector stops on unsupported layout rather than weakening validation.

Before material comparison, the inspector verifies identical geometry and
topology records for disabled and enabled cases:

```text
xstore, ystore, zstore, ibool, idoubling, ispec_is_tiso,
xix/xiy/xiz, etax/etay/etaz, gammax/gammay/gammaz
```

Final observed maximum geometry/topology real-record difference:

```text
0.00000000E+00
```

## Independent Oracle

The oracle does not call `model_s40rts.f90` ULVZ helper routines. It links to
local SPECFEM constants and initializes local model parameters, then validates
that generated coordinates use SPECFEM normalized radius before converting to
kilometers.

For each GLL point:

```text
iglob = ibool(i,j,k,ispec)
rnorm = sqrt(x^2 + y^2 + z^2)
radius_km = rnorm * R_PLANET / 1000
height_above_cmb_km = radius_km - RCMB / 1000
lat = asin(z / rnorm)
lon = atan2(y, x)
cosang = sin(lat) * sin(lat0) + cos(lat) * cos(lat0) * cos(lon - lon0)
cosang = clamp(cosang, -1, 1)
lateral_distance_km = (RCMB / 1000) * acos(cosang)
```

The lateral geometry guard is:

```text
lateral_distance_km <= LATERAL_RADIUS_KM + GEOMETRY_TOL_KM
GEOMETRY_TOL_KM = 1.0e-3
```

`GEOMETRY_TOL_KM` is a small coordinate tolerance and is not the taper width.

Expected weight:

```text
outside if height < 0, height > 80 km, or lateral distance > 400 km
lateral core if distance <= 400 km - 100 km
lateral taper otherwise: 0.5 * (1 + cos(pi*x))
top core if height <= 80 km - 20 km
top taper otherwise: 0.5 * (1 + cos(pi*y))
w_expected = lateral_weight * top_weight
```

## Material Ratios

The comparable pointwise fields are:

```text
rho_ratio = rho_enabled / rho_disabled
vsv_ratio = sqrt((muv/rho)_enabled / (muv/rho)_disabled)
vsh_ratio = sqrt((muh/rho)_enabled / (muh/rho)_disabled)
vpv_ratio = sqrt(((kappav + 4/3*muv)/rho)_enabled / same_disabled)
vph_ratio = sqrt(((kappah + 4/3*muh)/rho)_enabled / same_disabled)
```

Expected ratios are:

```text
rho: 1 + w_expected * 0.05
vsv: 1 + w_expected * -0.20
vsh: 1 + w_expected * -0.20
vpv: 1 + w_expected * -0.10
vph: 1 + w_expected * -0.10
```

The configured build has `CUSTOM_REAL = SIZE_REAL`, so the ratio residual
tolerance is `5.0e-5`. The inspector uses a tighter double-precision threshold
only when `CUSTOM_REAL = SIZE_DOUBLE`.

Final observed maximum residuals:

```text
rho: 2.64773818E-07
vsv: 8.00418074E-07
vsh: 8.00418074E-07
vpv: 4.27960636E-07
vph: 4.27960636E-07
```

All are below `5.0e-5`.

Final observed ratio ranges:

```text
rho outside: 1.00000000E+00 to 1.00000000E+00
rho taper:   1.00240017E+00 to 1.03148459E+00
rho core:    1.04999998E+00 to 1.05000011E+00

vsv/vsh outside: 1.00000000E+00 to 1.00000000E+00
vsv/vsh taper:   8.74062001E-01 to 9.90399148E-01
vsv/vsh core:    7.99999955E-01 to 8.00000007E-01

vpv/vph outside: 1.00000000E+00 to 1.00000000E+00
vpv/vph taper:   9.37030965E-01 to 9.95199580E-01
vpv/vph core:    8.99999945E-01 to 8.99999995E-01
```

No point below the CMB or outside the lateral footprint received a material
change:

```text
outside-geometry changed count: 0
wrong-sign material response count: 0
material points changed: 64
status: PASS
```

## Commands

Final verification commands:

```bash
cd specfem3d_globe/tests/meshfem3D
./5.test_s40rts_ulvz.sh
./6.test_s40rts_ulvz_mesh.sh
```

The 3D script preserves case directories, logs, manifests, checksums, and
reports in `s40rts_ulvz_mesh_work_*`. The final documented run is:

```text
specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_20260630_115002_1960459
```
