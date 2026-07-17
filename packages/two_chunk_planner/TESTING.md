# Planner test report

Validation performed with the project interpreter:

```bash
PYTHON=${ULVZ_PYTHON:-python3}
PYTHONPATH=packages/two_chunk_planner/src "$PYTHON" \
  -m pytest packages/two_chunk_planner/tests -q
```

Result: **13 passed**.

Covered cases include Cartesian round trip, accepted C1/C2/interface geometry,
chunk-1/chunk-2 fixture classification, outside-domain detection, rotation
distance preservation, strict optional target YAML, deterministic polar search,
canonical-only Par_file fragment, a read-only CLI integration run, real TauP
`prem` geographic Pdiff/Sdiff records, finite Cartesian-chord length and
CMB-near proxy metadata, strict missing-phase aggregation, partial inventory,
and date-line path splitting.

The acceptance environment has Python 3.11.15, NumPy 2.4.6, ObsPy 1.5.0 and
geographiclib 2.1 with `HAS_GEOGRAPHICLIB=True`. Package-local user-guide
smoke evidence is retained in
`validation/user_guide_acceptance_20260717T093847Z/`. It validates all package
examples, standard output creation, and refusal to overwrite every example
output directory. No dependency was installed.

```text
formal_source_modified=false
formal_build_rules_modified=false
accepted_patch_modified=false
large_simulation_run=false
commit_performed=false
push_performed=false
```
