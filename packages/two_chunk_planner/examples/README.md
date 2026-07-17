# Runnable examples

All examples are synthetic planner inputs. They are not Kim/Song inputs and do
not authorize a mesh or solver run. Run from the repository root with the
project Python interpreter and an output directory that does **not** exist.

- `geometry_only/`: CMTSOLUTION + STATIONS and the default great-circle mode.
- `phase_aware/`: Pdiff/Sdiff TauP `prem` example.
- `station_csv/`: CSV station input with `--source`.
- `target_regions/`: strict circle, polygon, and corridor YAML.

The full commands, expected checks, and limits are in
[`../docs/user_guide_en.md`](../docs/user_guide_en.md) and
[`../docs/user_guide_zh.md`](../docs/user_guide_zh.md).
