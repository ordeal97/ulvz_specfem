# Package-local user-guide acceptance

All six documented smoke examples completed using independent, initially absent
output directories. Each produced the eight standard planner files:
`candidates.json`, `candidates.csv`, `recommended_Par_file.inc`,
`geometry_audit.json`, `boundary_time_audit.json`, `report.md`, `map.png`, and
`run_manifest.json`.

Repeating each exact command with the same output directory exited 2 and
refused overwrite. The phase-aware Pdiff/Sdiff smoke completed with the package
synthetic input. The complete package test suite reports 13 passed. Markdown
links were checked locally. No mesher, database generator, solver, dependency
installation, SPECFEM-source change, build-rule change, patch change, commit,
or push occurred.
