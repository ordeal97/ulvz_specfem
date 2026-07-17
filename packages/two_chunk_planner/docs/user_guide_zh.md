<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# 双 chunk planner 使用指南

版本 0.2.0。`two_chunk_planner` 是完全独立、只读的 canonical two-chunk 规划工具。
安装后可从任意目录运行，不需要 ULVZ 项目、SPECFEM 工作树或 patch manifest。

## 1. 范围与限制

它只规划 `NCHUNKS=2` 的 canonical 90°×90° 几何：AB 是 central first chunk，AC 是
supported-left second chunk。不支持其他角宽、attachment side、独立定向、任意 two-chunk
或 multi-chunk topology。`general_two_chunk_mode_classification=B`。

工具搜索 center latitude/longitude 与 `GAMMA_ROTATION_AZIMUTH`，分类 source/receiver，
审计路径并输出可审阅参数片段。它不运行、也不替代 topology、mesher、database、Stacey、
solver、waveform 或生产级 boundary-return 验收。

## 2. 安装与启动

从任意目录安装提供的 wheel：

```bash
python -m pip install two_chunk_planner-0.2.0-py3-none-any.whl
```

从 source distribution 或 source directory 安装：

```bash
python -m pip install two_chunk_planner-0.2.0.tar.gz
python -m pip install .
python -m pip install -e '.[phase-aware]'
```

可选 `phase-aware` extra 提供 ObsPy。应检查 geographic TauP 支持：

```bash
python -c 'from obspy.geodetics.base import HAS_GEOGRAPHICLIB; print(HAS_GEOGRAPHICLIB)'
two-chunk-planner --help
python -m two_chunk_planner --help
```

仅开发 package 时可不安装运行：

```bash
PYTHONPATH=src python -m two_chunk_planner --help
```

## 3. 三个独立案例

以下 fixture 都是 synthetic，不是 Kim/Song 输入。令 `P` 为 package examples 的副本；
每个 output 目录必须不存在。

```bash
P=/path/to/two_chunk_planner/examples
two-chunk-planner plan --cmtsolution "$P/geometry_only/DATA/CMTSOLUTION" \
  --stations "$P/geometry_only/DATA/STATIONS" --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 --output geometry_plan
```

```bash
two-chunk-planner plan --cmtsolution "$P/phase_aware/DATA/CMTSOLUTION" \
  --stations "$P/phase_aware/DATA/STATIONS" --path-mode phase-aware \
  --phases Pdiff,Sdiff --taup-model prem --taup-resample --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 --output phase_plan
```

```bash
two-chunk-planner plan --cmtsolution "$P/geometry_only/DATA/CMTSOLUTION" \
  --stations "$P/geometry_only/DATA/STATIONS" --par-file "$P/external_par_file/Par_file" \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output external_par_plan
```

## 4. 输入与 profile

必须二选一：`--cmtsolution` 或 `--source LAT LON DEPTH_KM`；也必须二选一：
`--stations` 或 `--stations-csv`。source、station、target YAML 都可在任意可读路径。
circle/polygon/corridor target 为可选。

`--par-file` 是唯一可选外部配置上下文，可在任意路径；它只读取 NEX/NPROC 和相关
compatibility flag，不通过 SPECFEM 定位，也不会修改文件。省略时，planning defaults 来自
`src/two_chunk_planner/resources/canonical_profile_v1.json`：NEX=96、canonical geometry
与 provenance reference。这些是规划默认值，不是用户生产配置。profile 不访问用户的
SPECFEM tree、patch manifest 或 source hash。

[英文 CLI reference](cli_reference_en.md) 与 [中文 CLI 参考](cli_reference_zh.md) 是
完整、权威的 35 项 option 列表。TauP、target、search、scoring、NEX/MPI 与 output 细节
应查 reference；本指南只解释常用工作流。

## 5. 路径模式与规划

`geometry-only` 默认使用采样地表大圆。`phase-aware` 对每个请求的 phase×station 调用
TauP；Pdiff/Sdiff geographic path 已验证。默认 strict coverage；partial 必须显式给
`--allow-partial-phase-coverage`，且绝不替换 phase。TauP 长度为
`taup_raypath_polyline_estimate`，CMB-near 是 sampled proxy；TauP 禁止用于
boundary-return timing。

搜索是确定性的 coarse/local/final center-gamma refinement。candidate geometry 始终
canonical；target coverage、external margin 和 endpoint margin 是透明检查。NEX=96、总
ranks 2/8/12 标为 `project_validated`；其他兼容选项未获项目验证。

## 6. 输出与验证边界

每次成功运行写出 `candidates.json`、`candidates.csv`、`geometry_audit.json`、
`boundary_time_audit.json`、`report.md`、`map.png`、`run_manifest.json` 与
`recommended_Par_file.inc`。

所有 audit 记录 `planner_mode=standalone`、`compatibility_profile_version`、
`specfem_source_verified=false`、`accepted_patch_verified=false`、
`production_configuration_verified=false`、`par_file_source`、
`configuration_status` 和 `verification_warnings`。这些 false 不是 planner 失败：独立
planner 有意不检查用户 SPECFEM source、已安装 patch、mesh 或 runtime validation。

`recommended_Par_file.inc` 只是建议参数片段，不是完整或可直接运行的 Par_file。复制前
应审阅 candidates、geometry audit、boundary-time audit、report 与 fragment。

## 7. 完整工作流

1. 安装 package，准备 source 与 stations。
2. 选择 geometry-only 初筛或 phase-aware 复核。
3. 可选准备严格 target YAML 和/或 external Par_file。
4. 向新 output 目录运行 `plan`。
5. 审阅 candidate 排名、classification、margin、warning 和 resource label。
6. 在外部 SPECFEM workflow 中自行应用/验证 accepted patch，再验证 mesh/topology、
   Stacey、solver、waveform 和 external returns。

## 8. Boundary time、许可证与科学状态

boundary seconds 始终是 advisory `heuristic_not_conservative` surface-arc proxy；
`boundary_time_production_safe=false`。sampling stability 为 `indeterminate`
（Pdiff 0.130094%，Sdiff 0.076131% resample-length difference）。Kim/Song 精确复现
仍缺作者原始输入。

本 package 使用 [GPL-3.0-or-later](../LICENSE)；见
[third-party notices](../THIRD_PARTY_NOTICES.md) 与
[validation status](validation_status.md)。
