# Canonical two-chunk regional simulations / Canonical two-chunk 区域模拟

This index links the content-equivalent project manuals:

- [English guide](two_chunk_regional_simulations_guide_en.md)
- [中文版手册](two_chunk_regional_simulations_guide_zh.md)

## Applicability / 适用范围

This is a project-local accepted extension, not an upstream SPECFEM3D_GLOBE
submission. It is validated only for NCHUNKS=2, two adjacent 90-degree
cubed-sphere chunks, central chunk first, supported left-side attachment,
whole-system orientation by central coordinates plus GAMMA_ROTATION_AZIMUTH,
and 2-, 8-, or 12-rank fixtures. canonical_90deg_fixture_ready=true;
general_two_chunk_mode_classification=B.

本手册是项目本地已验收扩展，不是上游 SPECFEM3D_GLOBE 提交。它只验证
NCHUNKS=2、两个相邻 90° cubed-sphere chunks、第一块为 central chunk、第二块为
受支持 left-side attachment、central coordinates 加 GAMMA_ROTATION_AZIMUTH 控制
整体定向，以及 2/8/12-rank fixture。canonical_90deg_fixture_ready=true；
general_two_chunk_mode_classification=B。

Do not claim support for non-90-degree or unequal widths, other attachment
sides, nonadjacent/independently oriented chunks, arbitrary two-chunk topology,
or three-/general multi-chunk configurations.

不得声称支持非 90° 或不同角宽、其他 attachment side、非相邻/独立定向 chunk、
任意 two-chunk topology 或 three-/general multi-chunk configuration。

## Patch requirement / 补丁要求

Apply the accepted project-local package only after its manifest-based hash and
context check:

~~~bash
patches/specfem3d_globe/two_chunk_endpoints/verify_patch.sh specfem3d_globe
git -C specfem3d_globe apply --check \
  patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch
~~~

See [project patch instructions](two_chunk_project_patch.md). Stop when the
source hash or patch context differs; an updated SPECFEM source requires new
review and targeted validation.

详见[项目补丁说明](two_chunk_project_patch.md)。source hash 或 patch context
不匹配时必须停止；更新 SPECFEM 源码后必须重新审查并做 targeted validation。

## Quick start / 快速开始

1. Read the selected language guide and verify/apply the project patch.
2. Audit the teaching inputs without databases or input modification:

   ~~~bash
   ${ULVZ_PYTHON:-python3} \
     cases/two_chunk_canonical_90deg/audit_geometry.py --validate-only \
     --specfem-root specfem3d_globe
   ~~~

3. Review the deliberate 8-rank runner before executing it:

   ~~~bash
   bash cases/two_chunk_canonical_90deg/run_canonical.sh \
     --specfem-root specfem3d_globe \
     --run-dir results/two_chunk_canonical_run_<UTC> --dry-run
   ~~~

The teaching case is not Kim/Song Hawaiʻi input and does not substitute for a
science-specific travel-time/boundary assessment.

教学案例不是 Kim/Song Hawaiʻi input，不能替代针对科学问题的
travel-time/boundary assessment。
