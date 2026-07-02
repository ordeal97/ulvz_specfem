# S40RTS ULVZ Runtime Inputs

This document records the parameters that are actually read by the current
S40RTS ULVZ implementation. It is the runtime contract for the implemented
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

This file is read only when the parsed `MODEL_NAME` is exactly `s40rts`.
`s40rts_paper` does not read or apply this external ULVZ overlay.

## Implemented Keys

The current parser requires exactly these keys:

```text
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

## Current Perturbation Convention

`DVS`, `DVP`, and `DRHO` are fractional perturbations applied relative to the
local native S40RTS background:

```text
d_return = (1 + d_s40rts) * (1 + w * d_ulvz) - 1
```

where `w` is the implemented taper weight. In the current transverse-isotropic
S40RTS database validation, `DVS` is applied consistently to `vsv/vsh`, `DVP`
to `vpv/vph`, and `DRHO` to density.

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
