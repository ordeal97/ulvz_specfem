# Two-chunk planner / 双 chunk planner

Version: package `0.2.0`; operational scope: the project's accepted canonical
two-chunk geometry only.

- [English user guide](user_guide_en.md)
- [中文使用指南](user_guide_zh.md)
- [English CLI reference](cli_reference_en.md)
- [中文 CLI 参考](cli_reference_zh.md)
- [Design and scope](design_and_scope.md)
- [Validation status](validation_status.md)
- [Runnable examples](../examples/README.md)

The planner is standalone and read-only. It plans canonical AB+AC geometry
before a SPECFEM run; it does not verify a user's patch/source, nor prove mesh,
database, Stacey, solver, waveform, or production boundary-return correctness.
It is GPL-3.0-or-later; see [LICENSE](../LICENSE).
