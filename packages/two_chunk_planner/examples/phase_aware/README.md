# Phase-aware Pdiff/Sdiff example

This synthetic, non-Kim/Song fixture is selected because current ObsPy TauP
`prem` returns geographic Pdiff and Sdiff paths at 125°. It is only a planner
input; do not run it with mesher or solver programs.

```bash
PYTHONPATH=packages/two_chunk_planner/src "$PY" -m two_chunk_planner plan \
  --cmtsolution packages/two_chunk_planner/examples/phase_aware/DATA/CMTSOLUTION \
  --stations packages/two_chunk_planner/examples/phase_aware/DATA/STATIONS \
  --path-mode phase-aware --phases Pdiff,Sdiff --taup-model prem --taup-resample \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output packages/two_chunk_planner/validation/new_phase_output
```

Set `PY` to the desired Python interpreter and choose a nonexistent output path.
