# Canonical two-chunk planner

Read-only planner for this project's accepted SPECFEM3D_GLOBE two-chunk mode:
two adjacent 90° chunks, AB central and AC supported-left. It verifies the
accepted patch hash but never applies a patch, changes a `Par_file`, or runs
mesher/database/solver programs.

```bash
PYTHON=${ULVZ_PYTHON:-python3}
PYTHONPATH=packages/two_chunk_planner/src "$PYTHON" \
  -m two_chunk_planner plan \
  --cmtsolution packages/two_chunk_planner/examples/geometry_only/DATA/CMTSOLUTION \
  --stations packages/two_chunk_planner/examples/geometry_only/DATA/STATIONS \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output packages/two_chunk_planner/validation/example_output_<UTC>
```

Read the complete [English guide](docs/user_guide_en.md),
[中文指南](docs/user_guide_zh.md), [bilingual index](docs/user_guide.md), and
[examples](examples/README.md). Current test and runtime evidence is recorded
in [TESTING.md](TESTING.md) and [validation status](docs/validation_status.md).
