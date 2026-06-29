# ULVZ Parameter Conventions

This document defines the coordinate conventions and units for YAML ULVZ case files in `config/`.

The configuration files are model records. They do not modify SPECFEM source code, `DATA/Par_file`, or `DATABASES_MPI` by themselves.

## Coordinates

Latitude and longitude locate the horizontal center of the ULVZ footprint at the CMB.

- `latitude`: degrees north. Positive is north of the equator; negative is south.
- `longitude`: degrees east. The project default is `-180_to_180`, so west longitudes are negative.
- `latitude_type`: either `geographic` or `geocentric`. Use `geographic` unless a workflow explicitly converts to geocentric latitude before model injection.
- `angular_units`: always `degrees`.

The test configuration uses geographic latitude and longitude in the `-180_to_180` range.

## Radius and Depth

All length values in the YAML files are in kilometers.

- `cmb_radius`: radius of the core-mantle boundary measured from the planet center.
- `radius_reference`: `planet_center`.
- `cmb_reference`: `top_of_outer_core`.
- `thickness`: vertical ULVZ thickness measured upward from the CMB into the mantle.

For Earth PREM-style models, a commonly used CMB radius is about `3480.0 km`. A point is inside the vertical extent of a non-tilted ULVZ when its radius is between:

```text
cmb_radius <= radius <= cmb_radius + thickness
```

Equivalently, the ULVZ occupies the lowermost mantle directly above the CMB. The CMB itself is treated as the bottom boundary; by default the taper is not applied below the CMB.

## Lateral Geometry

`shape` controls the horizontal footprint at the CMB.

- `circular_cap`: `lateral_radius` is the horizontal radius in kilometers.
- `elliptical_cap`: `lateral_radius` is the semi-major radius in kilometers, and `ellipticity.minor_radius` is the semi-minor radius.

Horizontal distances are measured on the local tangent plane at the ULVZ center unless a later implementation states otherwise. For small ULVZs this is equivalent to a local east-north coordinate system:

- local east is positive toward increasing longitude;
- local north is positive toward increasing latitude;
- local up is positive radially outward from the planet center.

`major_axis_azimuth` is measured clockwise from geographic north. For example:

- `0.0` points north-south;
- `90.0` points east-west.

## Perturbations

Perturbations are fractional changes relative to the background model sampled at the same point.

- `d_vp`: fractional P-wave speed perturbation.
- `d_vs`: fractional S-wave speed perturbation.
- `d_rho`: fractional density perturbation.

Examples:

```text
d_vp: -0.10   means Vp is reduced by 10 percent
d_vs: -0.30   means Vs is reduced by 30 percent
d_rho: 0.10   means density is increased by 10 percent
```

An implementation should apply these as:

```text
Vp_new  = Vp_background  * (1 + taper_weight * d_vp)
Vs_new  = Vs_background  * (1 + taper_weight * d_vs)
rho_new = rho_background * (1 + taper_weight * d_rho)
```

The `applies_to` field documents how perturbations should be mapped:

- `isotropic`: apply `d_vp` to isotropic Vp, `d_vs` to isotropic Vs, and `d_rho` to density.
- `transverse_isotropic_components`: apply the velocity perturbations consistently to the relevant TI components, such as `vpv/vph` and `vsv/vsh`, while preserving the intended anisotropy convention. The exact mapping must be documented by the injection workflow before use.

## Smooth Boundary Taper

The taper controls the transition from full ULVZ perturbation to the background model.

- `taper.enabled`: enables or disables smoothing.
- `taper.style`: one of `cosine`, `raised_cosine`, or `smoothstep`.
- `taper.lateral_width`: horizontal transition width in kilometers at the footprint boundary.
- `taper.vertical_width`: vertical transition width in kilometers near the ULVZ top.
- `apply_to_top`: normally `true`.
- `apply_to_bottom_cmb`: normally `false`, because the CMB is the physical lower boundary of the ULVZ.

The taper weight should be `1.0` in the interior, `0.0` outside the ULVZ, and smoothly vary between `0.0` and `1.0` across the taper widths.

For a raised-cosine boundary transition over normalized distance `s` from 0 to 1:

```text
weight = 0.5 * (1 + cos(pi * s))
```

where `s = 0` is the inner edge of the taper and `s = 1` is the outer edge.

## Rotation and Tilt

Rotation and tilt are optional.

`orientation.rotation` rotates the horizontal anomaly footprint around the local radial axis:

- `azimuth` is degrees clockwise from north.
- For circular caps, rotation has no geometric effect but may still be recorded for reproducibility.
- For elliptical caps, rotation controls the major-axis direction.

`orientation.tilt` tilts the ULVZ vertical axis away from the local radial direction:

- `plunge` is the tilt angle in degrees.
- `plunge = 0.0` means no tilt.
- Positive or negative plunge conventions must be handled consistently by the implementation; the project default is to use the sign as written and document the resulting axis vector.
- `azimuth` is the direction toward which the axis tilts, measured clockwise from north.

Tilt changes how vertical distance from the CMB-centered anomaly axis is computed. It should not change the definition of `cmb_radius`; the CMB remains the reference lower boundary.

## Validation Expectations

Before running SPECFEM with a generated ULVZ model, the workflow should verify:

- the background model/database remains unchanged;
- all generated files are written to a new case directory;
- requested `d_vp`, `d_vs`, and `d_rho` extrema are reached inside the full-strength ULVZ interior;
- taper weights are bounded between `0.0` and `1.0`;
- no velocity or density becomes non-positive;
- the ULVZ center and perturbed points fall inside the intended SPECFEM mesh/chunk;
- the YAML model record is copied into the run directory.
