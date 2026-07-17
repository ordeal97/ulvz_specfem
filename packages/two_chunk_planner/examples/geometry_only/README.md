# Geometry-only example

This small synthetic input is a canonical AB-to-AC planning example, not a
Kim/Song data set and not a solver case. Use the command in `../README.md`.
The fixed center/gamma range makes it a quick, deterministic CLI smoke test.

```bash
PYTHONPATH=packages/two_chunk_planner/src "$PY" -m two_chunk_planner plan \
  --cmtsolution packages/two_chunk_planner/examples/geometry_only/DATA/CMTSOLUTION \
  --stations packages/two_chunk_planner/examples/geometry_only/DATA/STATIONS \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output packages/two_chunk_planner/validation/new_geometry_output
```

Set `PY` to the desired Python interpreter and choose a nonexistent output path.
