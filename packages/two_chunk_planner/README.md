# Canonical two-chunk planner

Standalone, read-only GPL-3.0-or-later planner for this project's accepted
SPECFEM3D_GLOBE two-chunk mode: two adjacent 90° chunks, AB central and AC
supported-left. It neither needs nor inspects a SPECFEM checkout, project
manifest, or accepted-patch source hash. It never applies a patch, changes a
`Par_file`, or runs mesher/database/solver programs.

```bash
python -m pip install two_chunk_planner-0.2.0-py3-none-any.whl
two-chunk-planner --help
```

Read the complete [English guide](docs/user_guide_en.md),
[中文指南](docs/user_guide_zh.md), [bilingual index](docs/user_guide.md),
[English CLI reference](docs/cli_reference_en.md), [中文 CLI 参考](docs/cli_reference_zh.md),
and [examples](examples/README.md). The bundled values are planning defaults
only: separately apply and verify the accepted patch before production work.
See [LICENSE](LICENSE), [third-party notices](THIRD_PARTY_NOTICES.md),
[TESTING.md](TESTING.md), and [validation status](docs/validation_status.md).
