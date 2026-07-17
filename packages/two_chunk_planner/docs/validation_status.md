# Validation status

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

## Standalone package status (v0.2.0)

The runtime uses only its bundled canonical profile and optional arbitrary
Par_file. It does not read a project root, patch manifest, SPECFEM worktree, or
source hash. Every run reports `planner_mode=standalone`, false source/patch
verification fields, and either `builtin_profile` or `external_file` Par-file
provenance. Package-local standalone acceptance evidence records wheel/sdist,
isolated installation, CLI-reference, PDF, and smoke checks.

The retained package runtime evidence is under `validation/` after the user
guide acceptance. Historical project evidence is not copied into this package.

Current verified planner-runtime facts:

- geographiclib runtime was available; Pdiff and Sdiff `prem` geographic TauP
  paths passed the synthetic AB→AC smoke test;
- date-line path splitting passed;
- the full package test suite reports **17 passed**;
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
