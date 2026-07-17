# Runnable examples

All examples are synthetic planner inputs. They are not Kim/Song inputs and do
not authorize a mesh or solver run. They do not need a project root, SPECFEM
checkout, or patch manifest. Use any Python interpreter with this package and
an output directory that does **not** exist.

- `geometry_only/`: CMTSOLUTION + STATIONS and the default great-circle mode.
- `phase_aware/`: Pdiff/Sdiff TauP `prem` example.
- `station_csv/`: CSV station input with `--source`.
- `external_par_file/`: optional arbitrary-path NEX/NPROC settings example.
- `target_regions/`: strict circle, polygon, and corridor YAML.

The full commands, expected checks, and limits are in
[`../docs/user_guide_en.md`](../docs/user_guide_en.md) and
[`../docs/user_guide_zh.md`](../docs/user_guide_zh.md), plus the full
[`../docs/cli_reference_en.md`](../docs/cli_reference_en.md) and
[`../docs/cli_reference_zh.md`](../docs/cli_reference_zh.md).
