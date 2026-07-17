# Validation status

The retained package runtime evidence is under `validation/` after the user
guide acceptance. Historical project evidence is not copied into this package.

Current verified planner-runtime facts:

- geographiclib runtime was available; Pdiff and Sdiff `prem` geographic TauP
  paths passed the synthetic AB→AC smoke test;
- date-line path splitting passed;
- the full package test suite reports **13 passed**;
- resample=false/true sampling is `indeterminate`, not a convergence claim:
  Pdiff length difference is 14.7813 km (0.130094%) and Sdiff difference is
  8.6426 km (0.076131%);
- `boundary_time_production_safe=false`; TauP is forbidden for boundary return
  timing;
- the synthetic fixture is not Kim/Song input;
- classification is
  `canonical_geometry_planning_validated__waveform_and_boundary_production_validation_required`.

No statement above establishes production waveform accuracy, full 3-D boundary
return safety, or support outside canonical 90°×90° AB+AC geometry.
