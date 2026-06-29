# S40RTS and SPiRaL Model Reader Audit

## Initial record

- Local SPECFEM tree inspected: `specfem3d_globe/`.
- Git commit: `9c312cb2c991b47484a7f302775f4f01ed9470f8`.
- Git description: `v8.1.0-323-g9c312cb2`.
- S20RTS data are installed locally: `DATA/s20rts/S20RTS.dat`, `DATA/s20rts/S20RTS.sph`, `DATA/s20rts/P12.dat`, and `DATA/s20rts/P12.sph`.
- S40RTS data are installed locally: `DATA/s40rts/S40RTS.dat`, `DATA/s40rts/s40rts.sph`, and `DATA/s40rts/README`.
- SPiRaL model data are not installed locally. `DATA/spiral1.4/` contains only `howto_download_the_SPiRal_model_files.md`; that file says the data are in the external `SPECFEM/specfem-data` repository (`DATA/spiral1.4/howto_download_the_SPiRal_model_files.md:1-5`).
- Precise model strings:
  - S20RTS: `MODEL = s20rts` or `MODEL = s20rts_paper` (`src/shared/get_model_parameters.F90:484-490`).
  - S40RTS: `MODEL = s40rts` or `MODEL = s40rts_paper` (`src/shared/get_model_parameters.F90:492-498`).
  - SPiRaL: `MODEL = spiral`; the file header also documents `spiral_crust1.0`, `spiral_crustspiral`, and `s362ani_crustspiral` as suffix combinations (`src/shared/get_model_parameters.F90:699-710`, `src/meshfem3D/model_spiral.f90:40-52`).

This audit inspected the requested model readers, model-selection logic, model broadcast and evaluation dispatch, mantle discontinuity topography logic, local model data directories, build inclusion, and the local user manual section on changing S20RTS-like models.

## 1. Call-path diagram

### Shared selection path

```text
DATA/Par_file: MODEL
  -> read into shared MODEL parameter
  -> get_model_parameters()
  -> get_model_parameters_flags()
       lowercases MODEL and strips suffix options
       sets MODEL_NAME, reference model flags, crust flags, 3-D model flags
  -> setup_model()
  -> meshfem3D_models_broadcast()
       meshfem3D_reference_model_broadcast()
       meshfem3D_mantle_broadcast()
       meshfem3D_crust_broadcast()
  -> get_model()
       meshfem3D_models_get1D_val()
       meshfem3D_models_get3Dmntl_val()
       meshfem3D_models_get3Dcrust_val()
```

Supporting lines:
- `get_model_parameters()` calls `get_model_parameters_flags()` first (`src/shared/get_model_parameters.F90:28-44`).
- `MODEL` is lowercased and suffixes are stripped before dispatch (`src/shared/get_model_parameters.F90:91-244`).
- Defaults are PREM reference, CRUSTAL false, no 3-D mantle perturbations, no `THREE_D_MODEL` (`src/shared/get_model_parameters.F90:260-297`).
- `setup_model()` calls `meshfem3D_models_broadcast()` before mesh optimization output (`src/meshfem3D/setup_model.f90:65-66`).
- `meshfem3D_models_broadcast()` calls reference, mantle, and crust broadcasts (`src/meshfem3D/meshfem3D_models.F90:65-72`).
- `get_model()` first obtains 1-D values and then calls the 3-D mantle dispatcher (`src/meshfem3D/get_model.F90:172-200`).

### `s20rts`

```text
MODEL = s20rts or s20rts_paper
  -> MODEL_NAME = s20rts or s20rts_paper
  -> CASE_3D = true
  -> CRUSTAL = true
  -> MODEL_3D_MANTLE_PERTUBATIONS = true
  -> ONE_CRUST = true
  -> THREE_D_MODEL = THREE_D_MODEL_S20RTS
  -> TRANSVERSE_ISOTROPY = true
  -> meshfem3D_mantle_broadcast()
       model_s20rts_broadcast()
         rank 0 read_model_s20rts()
         bcast_all_dp() S/P coefficients and spline arrays
  -> meshfem3D_models_get3Dmntl_val()
       mantle_s20rts(r_used, theta, phi, dvs, dvp, drho)
       vpv/vph/vsv/vsh/rho *= 1 + relative perturbation
```

Main evidence:
- Flags: `src/shared/get_model_parameters.F90:484-490`.
- Broadcast selection: `src/meshfem3D/meshfem3D_models.F90:181-188`.
- Reader and broadcast: `src/meshfem3D/model_s20rts.f90:71-110`, `src/meshfem3D/model_s20rts.f90:118-164`.
- Evaluation and combination: `src/meshfem3D/meshfem3D_models.F90:754-762`.

### `s40rts`

```text
MODEL = s40rts or s40rts_paper
  -> MODEL_NAME = s40rts or s40rts_paper
  -> CASE_3D = true
  -> CRUSTAL = true
  -> MODEL_3D_MANTLE_PERTUBATIONS = true
  -> ONE_CRUST = true
  -> THREE_D_MODEL = THREE_D_MODEL_S40RTS
  -> TRANSVERSE_ISOTROPY = true
  -> meshfem3D_mantle_broadcast()
       model_s40rts_broadcast()
         rank 0 read_model_s40rts()
         bcast_all_dp() S/P coefficients and spline arrays
  -> meshfem3D_models_get3Dmntl_val()
       mantle_s40rts(r_used, theta, phi, dvs, dvp, drho)
       vpv/vph/vsv/vsh/rho *= 1 + relative perturbation
```

Main evidence:
- Flags: `src/shared/get_model_parameters.F90:492-498`.
- Broadcast selection: `src/meshfem3D/meshfem3D_models.F90:189-190`.
- Reader and broadcast: `src/meshfem3D/model_s40rts.f90:83-121`, `src/meshfem3D/model_s40rts.f90:128-179`.
- Evaluation and combination: `src/meshfem3D/meshfem3D_models.F90:763-770`.

### `spiral`

```text
MODEL = spiral
  -> MODEL_NAME = spiral
  -> REFERENCE_CRUSTAL_MODEL = ICRUST_SPIRAL
  -> CASE_3D = true
  -> CRUSTAL = true
  -> ONE_CRUST = true
  -> REFERENCE_1D_MODEL = REFERENCE_MODEL_1DREF
  -> TRANSVERSE_ISOTROPY = true
  -> MODEL_3D_MANTLE_PERTUBATIONS = true
  -> THREE_D_MODEL = THREE_D_MODEL_SPIRAL
  -> ANISOTROPIC_3D_MANTLE = true
  -> ATTENUATION_3D = true
  -> meshfem3D_mantle_broadcast()
       model_mantle_spiral_broadcast()
         rank 0 read_mantle_spiral_model()
         bcast_all_dp()/bcast_all_i() mantle coefficients, density, bands, dzones, d410/d660
  -> meshfem3D_crust_broadcast()
       model_crust_spiral_broadcast()
         rank 0 read_crust_spiral_model()
         bcast_all_dp()/bcast_all_i() crust coefficients, density, thickness, bands
  -> meshfem3D_models_get3Dmntl_val()
       model_mantle_spiral(r_used, lat, lon, velocities, rho, c_ij)
  -> meshfem3D_models_get3Dcrust_val()
       model_crust_spiral(lat, lon, r, velocities, rho, c_ij, moho, sediment)
```

Main evidence:
- Flags: `src/shared/get_model_parameters.F90:699-710`.
- Mantle broadcast selection: `src/meshfem3D/meshfem3D_models.F90:238-240`.
- Crust broadcast selection: `src/meshfem3D/meshfem3D_models.F90:353-355`.
- Mantle evaluation: `src/meshfem3D/meshfem3D_models.F90:916-925`.
- SPiRaL tensor conversion is not re-converted by the generic Love-parameter path because the dispatcher recognizes that `model_mantle_spiral()` already sets `c11...c66` (`src/meshfem3D/meshfem3D_models.F90:1084-1096`).

### Mantle discontinuity topography call path

S20RTS and S40RTS do not trigger 410/660 topography mesh stretching in this local source version. `setup_model()` reports internal topography only for S362ANI family, full SH, and SPiRaL (`src/meshfem3D/setup_model.f90:101-113`). `compute_element_properties.f90` applies S362ANI topography for S362ANI/BKMNS models, full-SH topography for `THREE_D_MODEL_MANTLE_SH`, and SPiRaL topography for `THREE_D_MODEL_SPIRAL`; no S20RTS or S40RTS case appears in that internal-topography block (`src/meshfem3D/compute_element_properties.f90:300-347`).

For SPiRaL:

```text
compute_element_properties()
  if not SUPPRESS_INTERNAL_TOPOGRAPHY
  if THREE_D_MODEL == THREE_D_MODEL_SPIRAL
  if idoubling is IFLAG_670_220 or IFLAG_MANTLE_NORMAL
  call add_topography_mantle_spiral(xelm, yelm, zelm)
    subtopo_spiral(lat, lon, topo410, topo660)
    stretch anchor points between 220 and 770 km
```

Supporting lines: `src/meshfem3D/compute_element_properties.f90:338-345`, `src/meshfem3D/model_spiral.f90:1996-2074`, `src/meshfem3D/model_spiral.f90:2084-2189`.

## 2. S20RTS versus S40RTS

| Item | S20RTS | S40RTS |
|---|---|---|
| Mantle S file | `DATA/s20rts/S20RTS.dat` (`src/meshfem3D/model_s20rts.f90:129-139`) | `DATA/s40rts/S40RTS.dat` (`src/meshfem3D/model_s40rts.f90:137-153`) |
| P file | `DATA/s20rts/P12.dat` (`src/meshfem3D/model_s20rts.f90:129-159`) | `DATA/s20rts/P12.dat`; comment says P12 is in the S20RTS directory (`src/meshfem3D/model_s40rts.f90:137-174`) |
| File format | ASCII spherical-harmonic coefficient tables read as one row per `(k,l)`, with `a(k,l,0)` then `(a,b)` for `m=1,l` (`src/meshfem3D/model_s20rts.f90:136-150`) | Same read pattern (`src/meshfem3D/model_s40rts.f90:149-164`) |
| S degree | 20 (`src/meshfem3D/model_s20rts.f90:51-53`) | 40 (`src/meshfem3D/model_s40rts.f90:63-65`; README confirms order 40 at `DATA/s40rts/README:21-31`) |
| P degree | P12, degrees 13-20 zero-filled (`src/meshfem3D/model_s20rts.f90:143-158`) | P12, degrees 13-40 zero-filled (`src/meshfem3D/model_s40rts.f90:156-173`) |
| Radial basis | 21 spline knots, `NK_20=20`, scaled radius `xr` in `[-1,1]` (`src/meshfem3D/model_s20rts.f90:51-64`, `248-254`, `324-357`) | Same 21 spline knots and scaled radius (`src/meshfem3D/model_s40rts.f90:63-75`, `230-238`, `321-354`) |
| Radial domain | PREM Moho radius `EARTH_R - 24.4 km` down to CMB radius 3480 km; returns zero outside (`src/meshfem3D/model_s20rts.f90:227-249`) | Same domain (`src/meshfem3D/model_s40rts.f90:208-231`) |
| Absolute or relative | Relative `dvs`, `dvp`, `drho`; applied by multiplying local background values (`src/meshfem3D/meshfem3D_models.F90:754-762`) | Relative `dvs`, `dvp`, `drho`; same multiplication (`src/meshfem3D/meshfem3D_models.F90:763-770`) |
| dVs | Spherical-harmonic sum over S model (`src/meshfem3D/model_s20rts.f90:256-286`) | Spherical-harmonic sum over S model (`src/meshfem3D/model_s40rts.f90:240-270`) |
| dVp | Default: P12 model. `_paper`: scaled from dVs (`src/meshfem3D/model_s20rts.f90:288-305`) | Default: P12 model. `_paper`: depth-dependent scale from dVs (`src/meshfem3D/model_s40rts.f90:272-303`) |
| dRho | Default: `0.40*dVs`; `_paper`: `0.50*dVs` (`src/meshfem3D/model_s20rts.f90:220-225`, `291-305`) | Default: `0.40*dVs`; `_paper`: `0.50*dVs` (`src/meshfem3D/model_s40rts.f90:197-207`, `275-303`) |
| Reference model | Default PREM, with transverse isotropy enabled by model flags (`src/shared/get_model_parameters.F90:260-297`, `484-498`) | Same |
| Crust handling | `CRUSTAL=.true.`, default crust2.0 unless suffix overrides; mantle may be extended above Moho before crust overwrite (`src/shared/get_model_parameters.F90:484-490`, `src/meshfem3D/meshfem3D_models.F90:730-748`) | Same (`src/shared/get_model_parameters.F90:492-498`, `src/meshfem3D/meshfem3D_models.F90:730-748`) |
| MPI reading/broadcast | Rank 0 reads; arrays broadcast with `bcast_all_dp` (`src/meshfem3D/model_s20rts.f90:100-110`) | Rank 0 reads; arrays broadcast with `bcast_all_dp` (`src/meshfem3D/model_s40rts.f90:111-121`) |
| Routine signature and units | `mantle_s20rts(radius,theta,phi,dvs,dvp,drho)`, radius non-dimensional, theta/phi radians, returns relative perturbations (`src/meshfem3D/model_s20rts.f90:168-179`) | `mantle_s40rts(radius,theta,phi,dvs,dvp,drho)`, same conventions (`src/meshfem3D/model_s40rts.f90:183-194`) |

The S20RTS ULVZ-overlay strategy can be transferred directly to S40RTS if the overlay is expressed as relative perturbations and is applied at the same logical stage. The exact later insertion point for S40RTS is inside `meshfem3D_models_get3Dmntl_val()`, immediately after `call mantle_s40rts(r_used,theta,phi,dvs,dvp,drho)` at `src/meshfem3D/meshfem3D_models.F90:765` and before the code multiplies `vpv`, `vph`, `vsv`, `vsh`, and `rho` by `(1+d*)` at `src/meshfem3D/meshfem3D_models.F90:766-770`.

This position preserves the original S40RTS reader, MPI broadcast, P12 handling, radial basis functions, and background tomography outside the ULVZ.

## 3. SPiRaL reading and interpolation

### Files read by SPiRaL

SPiRaL crust constants define 13 latitude bands, 9 crustal layers, and `CRUST_NB=248291`; coefficients are stored as `CIJ: 1=c11, 2=c13, 3=c33, 4=c44, 5=c66` (`src/meshfem3D/model_spiral.f90:147-183`).

Crust files:
- `DATA/spiral1.4/crust/crust_bands_info.txt` (`src/meshfem3D/model_spiral.f90:299-318`).
- Per-band files built as `DATA/spiral1.4/crust/crust_band_lat1_<lat1>_lat2_<lat2>_dlat_<dlat>_dlon_<dlon>.<var>` for `C11`, `C13`, `C33`, `C44`, `C66`, `depths`, and `density` (`src/meshfem3D/model_spiral.f90:330-363`, `471-486`).

SPiRaL mantle constants define 13 latitude bands, 3 depth zones, `MANTLE_NB=248291`, `MANTLE_NBZ=70`, and topography grid dimensions `TOPO_NLO=721`, `TOPO_NLA=361`, `TOPO_RES=2` for 0.5 degree spacing (`src/meshfem3D/model_spiral.f90:1186-1218`).

Mantle files:
- `DATA/spiral1.4/mantle/mantle_bands_info.txt` (`src/meshfem3D/model_spiral.f90:1332-1356`).
- `DATA/spiral1.4/mantle/mantle_dzones_info.txt` (`src/meshfem3D/model_spiral.f90:1360-1387`).
- Per-band/depth-zone files built as `DATA/spiral1.4/mantle/mantle_band_lat1_<lat1>_lat2_<lat2>_dlat_<dlat>_dlon_<dlon>_d1_<dep1>_d2_<dep2>_dZ_<dep>.<var>` for `C11`, `C13`, `C33`, `C44`, `C66`, and `density` (`src/meshfem3D/model_spiral.f90:1399-1431`, `1547-1567`).
- `DATA/spiral1.4/mantle/transitionzone_topo.txt`, read as `lat lon d410 d660` after an `NLA NLO` header (`src/meshfem3D/model_spiral.f90:1478-1497`).

Because only `DATA/spiral1.4/howto_download_the_SPiRal_model_files.md` is present locally, this local installation would fail when selecting `MODEL = spiral` unless the external SPiRaL data are installed. The download note is at `DATA/spiral1.4/howto_download_the_SPiRal_model_files.md:1-5`.

### Absolute values, physical meaning, and units

SPiRaL mantle and crust values are absolute material properties, not relative perturbations. The model routines read elastic coefficients and density, derive velocities from `sqrt(Cij/rho)`, non-dimensionalize them, and rotate the elastic tensor into the SPECFEM global frame.

The physical meanings are documented in the code:
- `C11 = A = rho * vph**2`
- `C13 = F = eta * (A - 2*L)`
- `C33 = C = rho * vpv**2`
- `C44 = L = rho * vsv**2`
- `C66 = N = rho * vsh**2 = (C11-C12)/2`

Supporting lines: `src/meshfem3D/model_spiral.f90:1694-1705`. The same relationships are used in crustal evaluation when `d12=d11-2*d66`, `d22=d11`, `d23=d13`, and `d55=d44` are assigned by layer (`src/meshfem3D/model_spiral.f90:767-851`).

The code implies `Cij` are in GPa-like units compatible with `[g/cm^3][(km/s)^2]` because it non-dimensionalizes them using `scale_GPa` (`src/meshfem3D/model_spiral.f90:877-902`, `1738-1763`). Density is treated as `g/cm^3` before non-dimensionalization because the routines use `rho * 1000.0d0 / RHOAV` (`src/meshfem3D/model_spiral.f90:871`, `1732`).

### Coordinate and radial conventions

- SPiRaL model evaluation expects geographic latitude in `[-90,90]` degrees and longitude in `[-180,180]` degrees (`src/meshfem3D/model_spiral.f90:544`, `583-587`, `1620-1635`, `1815-1819`).
- `meshfem3D_models_get3Dmntl_val()` converts geocentric `theta,phi` to latitude and longitude in degrees and wraps longitude to `[-180,180]` before calling SPiRaL (`src/meshfem3D/meshfem3D_models.F90:916-925`).
- Mantle radius input is non-dimensional. `read_mantle_spiral()` converts to depth in km with `depth = R_PLANET_KM * (1-r)` and clamps depth to 27-2891 km (`src/meshfem3D/model_spiral.f90:1810-1834`).
- SPiRaL crust uses non-dimensional radius `x_in`; layer depths/thicknesses are read in km and divided by `R_PLANET_KM` (`src/meshfem3D/model_spiral.f90:714-735`).
- 410/660 topography input is read as discontinuity depths in km and converted to perturbations relative to the mesh radii for 400/670 km discontinuities (`src/meshfem3D/model_spiral.f90:2080-2081`, `2186-2187`).

### Interpolation actually implemented

Crust:
- `interpolate_crust = .true.` (`src/meshfem3D/model_spiral.f90:180-182`).
- Crust values are horizontally bilinear in lon/lat within each band; no radial interpolation is needed because the routine selects one of the layer values based on local radius (`src/meshfem3D/model_spiral.f90:992-1061`, `767-855`).
- Optional CAP smoothing is applied before layer selection when `flag_smooth_spiral_crust` is true (`src/meshfem3D/model_spiral.f90:629-697`, `1076-1177`).

Mantle:
- `interpolate_mantle = .true.` (`src/meshfem3D/model_spiral.f90:1213-1215`).
- The code locates 8 lon/lat/depth corners and computes the radial interpolation weight `c` (`src/meshfem3D/model_spiral.f90:1891-1974`).
- Observation: the returned `mtle_rho` and `mtle_coefs` use only the first four corner values, i.e., horizontal bilinear interpolation on the `k_min` depth plane. The computed radial weight `c` and the `k_max` corner values are not used in the final assignment (`src/meshfem3D/model_spiral.f90:1976-1977`). This is reported as an implementation observation only; no fix is proposed here.

Topography:
- `interpolate_topo = .true.` and the comment says it must remain true to avoid mesh collapse/global-indexing failure (`src/meshfem3D/model_spiral.f90:1216-1218`).
- 410/660 topography uses horizontal bilinear interpolation on the 0.5 degree grid (`src/meshfem3D/model_spiral.f90:2122-2182`).

### 410/660 topography and mesh effects

SPiRaL 410/660 discontinuity topography changes the mesh when internal topography is not suppressed. `setup_model()` includes SPiRaL in the list that reports element stretching for 3-D internal surfaces (`src/meshfem3D/setup_model.f90:101-113`). `compute_element_properties.f90` calls `add_topography_mantle_spiral()` for `THREE_D_MODEL_SPIRAL` in the `IFLAG_670_220` or normal mantle region (`src/meshfem3D/compute_element_properties.f90:338-345`). That routine stretches anchor points between 220 and 770 km using the interpolated 410/660 topography (`src/meshfem3D/model_spiral.f90:2034-2070`).

### Radial anisotropy, non-dimensionalization, and tensor rotation

SPiRaL represents radial anisotropy through Love parameters and full tensor storage:
- It derives `vph`, `vpv`, `vsh`, `vsv`, and `eta` from absolute `Cij` and `rho` (`src/meshfem3D/model_spiral.f90:1720-1725`).
- It non-dimensionalizes velocities, density, and elastic coefficients (`src/meshfem3D/model_spiral.f90:1727-1763`).
- It rotates local radial tensor coefficients to the SPECFEM global frame with `rotate_tensor_radial_to_global()` (`src/meshfem3D/model_spiral.f90:1765-1774`).
- The generic dispatcher stores the full anisotropic tensor for `ANISOTROPIC_3D_MANTLE` in `get_model()` (`src/meshfem3D/get_model.F90:276-297`), and the allocation path allocates full `c11...c66` storage for anisotropic mantle elements (`src/meshfem3D/create_regions_mesh.F90:639-666`).

## 4. ULVZ implementation options

### S40RTS

Approach A: modify original external S40RTS/P12 model files.
- Reproducibility: weak unless every edited coefficient file is copied and versioned per run.
- Risk: high risk of corrupting the original background tomography because `DATA/s40rts/S40RTS.dat` and `DATA/s20rts/P12.dat` are shared inputs.
- Geometry/taper support: awkward for arbitrary CMB ULVZ geometry because the model is spherical-harmonic/radial-spline coefficient data.
- Parameter sweeps: poor; each parameter set needs regenerated coefficient files and careful naming.
- Recompilation: not needed if only data files change.
- Background preservation: not guaranteed unless generated files are separate and the original files are never overwritten.

Approach B: keep original tomography files unchanged and apply an analytical ULVZ overlay inside model evaluation.
- Reproducibility: strong if ULVZ parameters are recorded in a machine-readable run file.
- Risk: low; original `DATA/s40rts/` and `DATA/s20rts/P12.dat` remain unchanged.
- Geometry/taper support: strong; arbitrary center, radius, thickness, and smooth taper can be evaluated analytically at each GLL point.
- Parameter sweeps: strong; new cases differ by parameter records and `MODEL=s40rts_ulvz`.
- Recompilation: needed for source-level model variant changes unless the later design reads ULVZ parameters from a runtime file already supported by the compiled code.
- Background preservation: yes outside the ULVZ if the overlay returns zero outside the tapered geometry.

Recommendation for S40RTS: use Approach B. The later overlay should be applied in a new variant path after `mantle_s40rts()` returns relative perturbations and before `vpv/vph/vsv/vsh/rho` are multiplied by those perturbations (`src/meshfem3D/meshfem3D_models.F90:763-770`). This keeps `model_s40rts.f90` and original data unchanged.

### SPiRaL

Approach A: modify original SPiRaL external model files.
- Reproducibility: weak to moderate; many crust/mantle/topography files would need copying and provenance tracking.
- Risk: high because SPiRaL uses many per-band/per-depth-zone files, and local data are currently absent, so regeneration would be hard to audit.
- Geometry/taper support: poor; arbitrary CMB ULVZ geometry would need edits across blocky lon/lat/depth files and could interact with the observed interpolation behavior.
- Parameter sweeps: poor; each sweep member would need a complete modified SPiRaL data set or a carefully managed subset.
- Recompilation: not needed if file formats remain unchanged.
- Background preservation: only if all modified files are separate from the original SPiRaL data tree.

Approach B: keep original SPiRaL files unchanged and apply an analytical ULVZ overlay inside a SPiRaL model-evaluation variant.
- Reproducibility: strong; original SPiRaL data and ULVZ parameters remain separate.
- Risk: low for the background files.
- Geometry/taper support: strong.
- Parameter sweeps: strong.
- Recompilation: needed for the source-level model variant unless parameter reading is designed as runtime input.
- Background preservation: yes outside the ULVZ if the overlay is zero outside the tapered geometry.

Recommendation for SPiRaL: use Approach B, but implement only after deciding the anisotropy convention in Section 5. SPiRaL returns absolute material properties and full tensors, so the overlay is not the same simple relative-perturbation branch used by S40RTS.

## 5. Required parameter convention before implementation

Future ULVZ parameters must explicitly define whether `dVp`, `dVs`, and `dRho` are relative to:

A. the 1-D reference model, or

B. the local tomographic background value.

Combination rules:
- If relative to the 1-D reference model, compute `delta_X = taper * dX_ulvz * X_1D_reference` and add that physical increment to the already-combined background value, or equivalently convert it to an effective relative perturbation before the model-specific multiplication step.
- If relative to the local tomographic background, compute `X_final = X_background * (1 + taper * dX_ulvz)`.

For S40RTS, the local source currently combines relative `dvp`, `dvs`, and `drho` with the background by multiplication (`src/meshfem3D/meshfem3D_models.F90:763-770`). A local-background convention therefore composes naturally by adding an extra relative perturbation at the same point, while a 1-D-reference convention needs access to the pre-tomography `vpv/vph/vsv/vsh/rho` values saved before applying S40RTS.

For SPiRaL, two scientifically distinct options must be evaluated before implementation:

A. Preserve SPiRaL radial anisotropy while applying the same fractional P- and S-wave perturbations to vertical and horizontal velocities.
- Physical consequence: SPiRaL's radial anisotropy ratios are mostly preserved because `vpv` and `vph` receive the same P factor and `vsv` and `vsh` receive the same S factor; `eta` can be recomputed from the updated Love parameters.
- Coding consequence: evaluate SPiRaL normally, convert or use local `vpv/vph/vsv/vsh/rho`, apply tapered fractional changes, rebuild `A,C,L,N,F`, rebuild local `d_ij`, non-dimensionalize consistently, and rotate to global `c_ij` as SPiRaL already does (`src/meshfem3D/model_spiral.f90:1694-1774`).

B. Replace the material inside the ULVZ with an isotropic material.
- Physical consequence: this discards SPiRaL radial anisotropy inside the ULVZ, forcing `vpv=vph`, `vsv=vsh`, and `eta=1`. That is a stronger scientific assumption than a fractional perturbation overlay.
- Coding consequence: build isotropic local tensor coefficients inside the ULVZ, rotate or directly assign rotation-invariant global coefficients, and ensure the transition taper blends consistently between anisotropic SPiRaL outside and isotropic ULVZ inside.

Do not choose between these SPiRaL options silently. The choice changes both physical interpretation and tensor construction.

## 6. Proposed implementation design

Minimal future architecture:
- Add a common ULVZ geometry/taper module for CMB-centered analytical ULVZ definitions. It should expose one routine that takes radius, latitude, longitude and returns taper weight plus inside/outside status. This avoids duplicating geometry logic between S40RTS and SPiRaL.
- Keep `model_s40rts.f90` and `model_spiral.f90` unchanged. Add wrapper/variant logic outside the original readers so original tomography loading and interpolation remain auditable.
- Introduce clear model variants:
  - `MODEL = s40rts_ulvz`
  - `MODEL = spiral_ulvz`
- Extend model selection by adding new `THREE_D_MODEL_*_ULVZ` constants and new `MODEL_NAME` cases.
- For S40RTS, call the original `mantle_s40rts()` and then apply the shared ULVZ overlay to `dvs,dvp,drho` before the existing multiplication into `vpv/vph/vsv/vsh/rho`.
- For SPiRaL, call the original `model_mantle_spiral()` and then apply the chosen anisotropic or isotropic ULVZ rule to the returned absolute velocities/tensor.
- Add a machine-readable ULVZ parameter record per run, preserving original background tomography separately from perturbation parameters.

Source/build files that would eventually need changes:
- `src/shared/get_model_parameters.F90`: add `s40rts_ulvz` and `spiral_ulvz` model-name cases and flags.
- `src/meshfem3D/meshfem3D_par.f90`: add/import new model constants.
- `src/meshfem3D/meshfem3D_models.F90`: add broadcast/evaluation dispatch for the new variants.
- A new ULVZ geometry/taper source file under `src/meshfem3D/`, or a narrowly scoped shared source if later needed by non-meshfem paths.
- `src/meshfem3D/rules.mk`: add the new source object and module dependency. Existing model objects are listed there for S20RTS, S40RTS, and SPiRaL (`src/meshfem3D/rules.mk:115-123`, `184-193`).

The manual's local guidance supports this style: new or replacement 3-D mantle routines should preserve call structure, return required non-dimensionalized or relative output, and broadcast large model data from rank 0 rather than having every rank read files (`doc/USER_MANUAL/12_changing_the_model.tex:112-197`, `200-287`).

## Concise comparison table

| Topic | S20RTS | S40RTS | SPiRaL |
|---|---|---|---|
| Local data installed | Yes | Yes | No; only download note |
| Main `MODEL` string | `s20rts` | `s40rts` | `spiral` |
| Alternative string | `s20rts_paper` | `s40rts_paper` | suffix combinations such as `spiral_crust1.0` |
| Background | Transversely isotropic PREM | Transversely isotropic PREM | 1DREF reference plus absolute SPiRaL mantle/crust |
| Model values | Relative perturbations | Relative perturbations | Absolute `Cij` and density |
| S degree | 20 | 40 | Gridded multiresolution bands, not SH in this reader |
| P handling | P12 file or paper scaling | P12 file or paper scaling | Derived from `C11/C33/rho` |
| Density handling | Scaled from dVs | Scaled from dVs | Absolute density file |
| 410/660 mesh topography | No | No | Yes |
| Best ULVZ strategy | Analytical overlay | Analytical overlay | Analytical overlay after anisotropy convention is chosen |

## Unresolved questions

- Should future ULVZ `dVp`, `dVs`, and `dRho` be relative to the 1-D reference model or to the local tomographic background?
- For SPiRaL, should the ULVZ preserve radial anisotropy with fractional perturbations to vertical/horizontal velocities, or replace the material with an isotropic tensor?
- Should ULVZ parameters be read from a runtime YAML/CSV file, a copied Par_file-style include, or generated Fortran constants?
- Should the ULVZ be clipped strictly to the mantle side of the CMB, or should any mesh/taper logic handle points exactly on the CMB boundary specially?
- Should density perturbations follow user-specified `dRho`, a scaling from `dVs`, or both with explicit precedence?
- Should S40RTS support both `s40rts_ulvz` and `s40rts_paper_ulvz`, or only the default `s40rts` background first?
- SPiRaL data are not installed locally; a future SPiRaL implementation task should first install or stage the required external data before any runtime verification.

## Recommended next task

Task 3B: implement ULVZ overlay for S40RTS only

No files outside `docs/model_reader_comparison_s40rts_spiral.md` were changed.
