# PREM + S40RTS ULVZ Runtime Inputs

This document records the parameters that are actually read by the current
PREM and S40RTS ULVZ implementation. It is the runtime contract for the implemented
path, not a design proposal.

## Runtime File

The implementation reads:

```text
specfem3d_globe/DATA/ulvz_s40rts.par
```

The tracked template is:

```text
specfem3d_globe/DATA/ulvz_s40rts.par.example
```

When this file is present it is parsed for every model family and then audited
against parsed `MODEL_NAME`. Native PREM may omit the file entirely.
`s40rts_paper` and every unsupported background fail if the file is present.

## Input Formats

The implementation accepts both formats below. It rejects unknown and duplicate
keys, incomplete body definitions, non-contiguous body indices, invalid
geometry/perturbations, and a mismatch between `BACKGROUND_MODEL` and
`Par_file: MODEL`.

### Legacy single body

When `N_ULVZ` is absent, the parser requires exactly these keys:

```text
BACKGROUND_MODEL
ENABLED
CENTER_LATITUDE_DEGREES
CENTER_LONGITUDE_DEGREES
THICKNESS_KM
LATERAL_RADIUS_KM
LATERAL_TAPER_KM
TOP_TAPER_KM
DVS
DVP
DRHO
```

Unknown keys, duplicate keys, malformed lines, and missing keys are errors.
Extra YAML-style fields are not ignored.

`ENABLED = .true.` becomes one active body. `ENABLED = .false.` still reads
and validates all nine body fields, then creates no active body; its resulting
PREM or S40RTS material is unchanged from the former implementation.

### New multi-body format

~~~text
BACKGROUND_MODEL = S40RTS
N_ULVZ = 3
ULVZ_1_CENTER_LATITUDE_DEGREES = ...
ULVZ_1_CENTER_LONGITUDE_DEGREES = ...
ULVZ_1_THICKNESS_KM = ...
ULVZ_1_LATERAL_RADIUS_KM = ...
ULVZ_1_LATERAL_TAPER_KM = ...
ULVZ_1_TOP_TAPER_KM = ...
ULVZ_1_DVS = ...
ULVZ_1_DVP = ...
ULVZ_1_DRHO = ...
~~~

Each index from `1` through `N_ULVZ` must provide all nine fields. `N_ULVZ=0`
is an explicit baseline: it accepts no body fields, creates no dummy body, and
does not apply an overlay. `N_ULVZ=1` is physically equivalent to the legacy
enabled single-body format. `ENABLED` is optional in the new format; when
present it must equal `(N_ULVZ > 0)`.

`BACKGROUND_MODEL` is required and accepts only `PREM` or `S40RTS`. It must
match the parsed `MODEL_NAME`: the supported PREM forms are
`1d_isotropic_prem` and `1d_transversely_isotropic_prem`; S40RTS is parsed
`s40rts` (including its existing suffix reduction). This audit runs even when
`ENABLED = .false.`.

## Current Geometry And Taper

The implemented model is a circular-cap ULVZ attached to the mantle side of
the CMB:

- `CENTER_LATITUDE_DEGREES`: geographic latitude in degrees, valid range
  `[-90, 90]`.
- `CENTER_LONGITUDE_DEGREES`: geographic longitude in degrees, normalized by
  the code to `[-180, 180)`.
- `THICKNESS_KM`: vertical thickness above the CMB into the lowermost mantle.
- `LATERAL_RADIUS_KM`: circular footprint radius measured as great-circle arc
  distance on the CMB.
- `LATERAL_TAPER_KM`: cosine lateral taper width at the footprint edge.
- `TOP_TAPER_KM`: cosine vertical taper width near the ULVZ top.

The CMB radius is fixed in the implementation as `3480 km`. There is no bottom
taper below the CMB; points below the CMB receive zero ULVZ weight.

The lateral taper is entirely inside `LATERAL_RADIUS_KM`: the code first
returns zero beyond R, then applies the cosine taper over `[R-taper,R]`.
Therefore each body's nonzero lateral support has outer radius R. Active bodies
are rejected when their closed CMB circular-cap supports overlap or touch; this
also rejects exact tangency. Since all bodies extend upward from the same CMB,
this spherical-cap test is the actual three-dimensional overlap guard. The
implementation deliberately defines no superposition rule for overlapping
ULVZs. At runtime it applies at most one body at each model point and returns
after the first positive-weight match.

## Normalized provenance

At mesher initialization rank 0 prints `N_ULVZ`, background, and a normalized
summary for every active body. It also creates
`OUTPUT_FILES/ulvz_normalized.csv` with:

~~~text
background,n_ulvz,body_index,center_latitude_degrees,center_longitude_degrees,
lateral_radius_km,thickness_km,lateral_taper_km,top_taper_km,dvs,dvp,drho
~~~

Every active body is one row. The `N_ULVZ=0` baseline writes one row with only
background and zero count populated; no dummy-body values are written. The file
is created with `status='new'`, so an existing provenance record is not silently
replaced.

## Current Perturbation Convention

For S40RTS, `DVS`, `DVP`, and `DRHO` are fractional perturbations applied
relative to the local native S40RTS background:

```text
d_return = (1 + d_s40rts) * (1 + w * d_ulvz) - 1
```

where `w` is the implemented taper weight. In the current transverse-isotropic
S40RTS database validation, `DVS` is applied consistently to `vsv/vsh`, `DVP`
to `vpv/vph`, and `DRHO` to density.

For PREM, the base `rho/vpv/vph/vsv/vsh/eta` is first generated unchanged.
At mantle-side points with `w > 0`, the overlay applies
`rho *= 1+w*DRHO`, `vpv/vph *= 1+w*DVP`, and `vsv/vsh *= 1+w*DVS`; `eta`
is not changed.

## Not Implemented From YAML Design

The broader YAML design files in `config/` and
`docs/ulvz_parameter_conventions.md` mention fields that are not runtime inputs
today. The current Fortran implementation does not support:

- reading `config/*.yaml`;
- elliptical caps or `minor_radius`;
- `major_axis_azimuth`, rotation, tilt, or plunge;
- selectable taper styles such as `smoothstep`;
- explicit `cmb_radius`, `radius_reference`, or coordinate convention fields;
- output case metadata, `case_id`, `model_record`, or `preserve_background`;
- choosing `applies_to` from the runtime file.

Those fields are design/record fields only until a validator/converter and
matching implementation support are added.
