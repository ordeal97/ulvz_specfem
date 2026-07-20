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
- the full package test suite reports **20 passed**, including compact/full
  scalar-reference, ordered keeper, and multi-orientation batch comparisons;
- resample=false/true sampling is `indeterminate`, not a convergence claim:
  Pdiff length difference is 14.7813 km (0.130094%) and Sdiff difference is
  8.6426 km (0.076131%);
- `boundary_time_production_safe=false`; TauP is forbidden for boundary return
  timing;
- the synthetic fixture is not Kim/Song input;
- classification is
  `canonical_geometry_planning_validated__waveform_and_boundary_production_validation_required`.

## Event 1 runtime acceptance

The preserved real Event 1 phase-aware case was completed twice by the current
planner in the project's third-round acceptance. The runs finished in 12:31.62
and 12:28.80 with exit status zero and strictly identical planner outputs.
This is an end-to-end planning-runtime and reproducibility result only: it is
about 32% faster than the prior approximately 18.5-minute run, does not reach
the 10-minute target, and does not establish production waveform or boundary
return validity. The old implementation has only a >1800 s timeout lower
bound. See the project-level
[performance record](../../../docs/two_chunk_planner_high_frequency_search.md).

No statement above establishes production waveform accuracy, full 3-D boundary
return safety, or support outside canonical 90°×90° AB+AC geometry.
