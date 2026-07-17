# Target-region examples

The parser accepts only `circle`, `polygon`, and `corridor`. Every field shown
here is required for its type except the optional top-level `name`; unknown
fields are rejected. Circle radii and corridor half widths are kilometres.

Use the geometry example with one of `circle.yaml`, `polygon.yaml`, or
`corridor.yaml`:

```bash
PYTHONPATH=packages/two_chunk_planner/src "$PY" -m two_chunk_planner plan \
  --cmtsolution packages/two_chunk_planner/examples/geometry_only/DATA/CMTSOLUTION \
  --stations packages/two_chunk_planner/examples/geometry_only/DATA/STATIONS \
  --analysis-window 0 1900 --target-region packages/two_chunk_planner/examples/target_regions/circle.yaml \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output packages/two_chunk_planner/validation/new_circle_output
```

Replace `circle.yaml` and the output path for polygon or corridor. Set `PY` to
the desired Python interpreter; every output path must be new.
