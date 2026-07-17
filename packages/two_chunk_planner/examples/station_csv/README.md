# Station CSV example

The CSV reader requires `network`, `station`, `latitude_deg`, and
`longitude_deg`. `elevation_m` and `burial_m` are optional. Use it with
`--source LAT LON DEPTH_KM`, not `--cmtsolution`.

```bash
PYTHONPATH=packages/two_chunk_planner/src "$PY" -m two_chunk_planner plan \
  --source 0 0 50 --stations-csv packages/two_chunk_planner/examples/station_csv/stations.csv \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output packages/two_chunk_planner/validation/new_csv_output
```

Set `PY` to the desired Python interpreter and choose a nonexistent output path.
