# Task 3C External S40RTS ULVZ

## Changed Files

- `specfem3d_globe/src/meshfem3D/model_s40rts.f90`
- `specfem3d_globe/tests/meshfem3D/test_models.makefile`
- `specfem3d_globe/DATA/ulvz_s40rts.par.example`
- `specfem3d_globe/tests/meshfem3D/test_s40rts_ulvz.f90`
- `specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh`
- `docs/task_3c_external_s40rts_ulvz.md`

Not changed: real `DATA/ulvz_s40rts.par`, S40RTS/P12 coefficient files, `DATA/Par_file`, dispatcher, `get_model_parameters`, setup constants, root Makefile, and `src/meshfem3D/rules.mk`.

## Parameter File

Runtime file: `DATA/ulvz_s40rts.par`

Example file: `DATA/ulvz_s40rts.par.example`

Required keys:

- `ENABLED`: logical, turns overlay on/off after the file is read.
- `CENTER_LATITUDE_DEGREES`: geographic latitude, degrees, must be in `[-90,90]`.
- `CENTER_LONGITUDE_DEGREES`: geographic longitude, degrees, finite; normalized to `[-180,180)`.
- `THICKNESS_KM`: ULVZ height above the CMB, km, must be positive and no thicker than the mantle above the CMB.
- `LATERAL_RADIUS_KM`: cylindrical-cap radius along the CMB, km, must be positive.
- `LATERAL_TAPER_KM`: cosine taper width at lateral edge, km, must be in `[0,LATERAL_RADIUS_KM]`.
- `TOP_TAPER_KM`: cosine taper width at top, km, must be in `[0,THICKNESS_KM]`.
- `DVS`, `DVP`, `DRHO`: relative perturbations; each must be greater than `-1`.

The parser accepts `key = value`, blank lines, and `#` comments. Because the existing C parser ignores malformed nonmatching lines and cannot detect duplicates, `check_ulvz_s40rts_parameter_file_keys()` first scans the file for required keys, duplicates, unknown keys, and malformed non-comment lines. Actual value parsing still uses `read_value_logical()` and `read_value_double_precision()`.

## MODEL_NAME

The overlay is triggered only when parsed `trim(MODEL_NAME) == 's40rts'`.

`get_model_parameters.F90` lower-cases the raw `MODEL`, strips supported suffixes such as `_AIC`, `_ACM`, `_crust1.0`, `_crust2.0`, `_1Dcrust`, and related crust options, then sets `MODEL_NAME = trim(MODEL_ROOT)`.

Examples:

- `MODEL = s40rts` gives `MODEL_NAME = s40rts`.
- `MODEL = s40rts_crust1.0_AIC` gives `MODEL_NAME = s40rts`.
- `MODEL = s40rts_paper` gives `MODEL_NAME = s40rts_paper`.

`s40rts_paper` is excluded because it uses the paper scaling path and must not require or apply this external ULVZ overlay.

## Broadcast

In `model_s40rts_broadcast()`, native S40RTS/P12 rank-0 reads and coefficient/spline broadcasts remain first and unchanged. Only after those broadcasts, if `MODEL_NAME == 's40rts'`, rank 0 reads and validates `DATA/ulvz_s40rts.par`, then broadcasts:

- `S40RTS_ULVZ_ENABLED` with `bcast_all_singlel()`
- 9 double precision parameters with one `bcast_all_dp(params,9)`

For any other `MODEL_NAME`, no ULVZ file is opened and no ULVZ parameters are broadcast.

## Geometry

Inputs to `mantle_s40rts()` use normalized radius and spherical angles:

```text
radius = r / EARTH_R
lat = PI_OVER_TWO - theta
lon = normalized(phi)
height_above_cmb_km = (radius * R_EARTH_ - RCMB_) / 1000.d0
cosang = sin(lat) * sin(lat0) + cos(lat) * cos(lat0) * cos(lon - lon0)
cosang = max(-1.d0, min(1.d0, cosang))
lateral_distance_km = (RCMB_ / 1000.d0) * acos(cosang)
```

ULVZ volume:

```text
0 <= height_above_cmb_km <= THICKNESS_KM
lateral_distance_km <= LATERAL_RADIUS_KM
```

Bottom is not tapered. Points below the CMB have zero weight.

## Taper And Overlay

The weight is the product of lateral and top cosine tapers:

```text
w = lateral_weight * top_weight
```

Lateral weight is 1 inside the untapered core or when `LATERAL_TAPER_KM == 0`, tapers with `0.5 * (1 + cos(PI * x))`, and is 0 outside `LATERAL_RADIUS_KM`.

Top weight is 1 below the untapered top zone or when `TOP_TAPER_KM == 0`, tapers with `0.5 * (1 + cos(PI * y))`, and is 0 above `THICKNESS_KM`.

Overlay composition is local-native-S40RTS-relative:

```text
dvs  = (1.d0 + dvs ) * (1.d0 + w * S40RTS_ULVZ_DVS ) - 1.d0
dvp  = (1.d0 + dvp ) * (1.d0 + w * S40RTS_ULVZ_DVP ) - 1.d0
drho = (1.d0 + drho) * (1.d0 + w * S40RTS_ULVZ_DRHO) - 1.d0
```

Early returns skip overlay when `MODEL_NAME /= 's40rts'`, disabled, `w <= 0`, or all three perturbations are zero.

## Commands And Results

Coefficient checksums before final verification:

```text
56870490b155cf68ef07056608bab9bfe8147959829db9582e359dbc35353c4f  DATA/s40rts/S40RTS.dat
ef6fcb940158c09bb16e5c45ba426726a4576c866d2f199ac8891fa21692f7ed  DATA/s20rts/P12.dat
```

Commands run:

```bash
cd specfem3d_globe
git diff --check
sha256sum DATA/s40rts/S40RTS.dat DATA/s20rts/P12.dat
make -j 4 xmeshfem3D
cd tests/meshfem3D
timeout 120 ./5.test_s40rts_ulvz.sh
cd ../../..
rg -n "[ \t]$|^(<<<<<<<|=======|>>>>>>>)" docs/task_3c_external_s40rts_ulvz.md \
  specfem3d_globe/DATA/ulvz_s40rts.par.example \
  specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh \
  specfem3d_globe/tests/meshfem3D/test_s40rts_ulvz.f90
```

Current results:

- `git diff --check` in `specfem3d_globe`: passed, no output.
- `make -j 4 xmeshfem3D`: passed, final run reported nothing to rebuild.
- `5.test_s40rts_ulvz.sh`: passed with 2 MPI ranks outside the sandbox; latest log says `test_s40rts_ulvz done successfully`.
- Text scan for trailing whitespace/conflict markers in new docs/example/test files: no matches.

Final `git -C specfem3d_globe status --short`:

```text
 M src/meshfem3D/model_s40rts.f90
 M tests/meshfem3D/test_models.makefile
?? DATA/ulvz_s40rts.par.example
?? tests/meshfem3D/5.test_s40rts_ulvz.sh
?? tests/meshfem3D/results.log
?? tests/meshfem3D/test_s40rts_ulvz.f90
```

## Unresolved

- Full mesh generation and forward simulations were intentionally not run.
- `tests/meshfem3D/results.log` is produced by the test harness and may contain earlier failed TDD attempts before the final passing run.
- The top-level `.git` directory in this mounted workspace is not usable as a git repository, so `docs/task_3c_external_s40rts_ulvz.md` was verified by text scan rather than top-level `git diff --check`.
