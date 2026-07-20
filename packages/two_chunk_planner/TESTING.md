# Planner test report

<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

Validation performed with the project interpreter:

```bash
PYTHON=${ULVZ_PYTHON:-python3}
PYTHONPATH=packages/two_chunk_planner/src "$PYTHON" \
  -m pytest packages/two_chunk_planner/tests -q
```

Result: **20 passed** in the final third-round Event 1 acceptance.

The v0.2.0 suite additionally validates package-local profile loading,
no-project-root geometry planning, optional arbitrary `--par-file`, parser/CLI
reference consistency, GPL package contents, and isolated wheel installation.

Covered cases include Cartesian round trip, accepted C1/C2/interface geometry,
chunk-1/chunk-2 fixture classification, outside-domain detection, rotation
distance preservation, strict optional target YAML, deterministic polar search,
canonical-only Par_file fragment, a read-only CLI integration run, real TauP
`prem` geographic Pdiff/Sdiff records, finite Cartesian-chord length and
CMB-near proxy metadata, strict missing-phase aggregation, partial inventory,
date-line path splitting, compact-search versus full-scalar reference results,
ordered coarse/local/final keeper sequences, and multi-orientation NumPy batch
path coverage against the scalar reference. These checks keep the candidate
set, rejection reasons, score, sort key and final audit equivalent; they do
not claim waveform accuracy.

The acceptance environment has Python 3.11.15, NumPy 2.4.6, ObsPy 1.5.0 and
geographiclib 2.1 with `HAS_GEOGRAPHICLIB=True`. Package-local user-guide
smoke evidence is retained in
`validation/user_guide_acceptance_20260717T093847Z/`. It validates all package
examples, standard output creation, and refusal to overwrite every example
output directory. No dependency was installed.

The real Event 1 performance/acceptance evidence is intentionally outside this
package under
`results/two_chunk_planner_high_frequency_search_20260720T111204Z_third_round/`.
Its persistent outputs and timing files are not produced by ordinary package
tests or by `two-chunk-planner plan`.

```text
formal_source_modified=false
formal_build_rules_modified=false
accepted_patch_modified=false
large_simulation_run=false
commit_performed=false
push_performed=false
```
