<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# 双 chunk planner 使用指南

版本 0.2.1。`two_chunk_planner` 是完全独立、只读的 canonical two-chunk 规划工具。
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
python -m pip install two_chunk_planner-0.2.1-py3-none-any.whl
```

从 source distribution 或 source directory 安装：

```bash
python -m pip install two_chunk_planner-0.2.1.tar.gz
python -m pip install .
python -m pip install -e '.[phase-aware]'
```

可选 `phase-aware` extra 提供 ObsPy。应检查 geographic TauP 支持：

```bash
python -c 'from obspy.geodetics.base import HAS_GEOGRAPHICLIB; print(HAS_GEOGRAPHICLIB)'
two-chunk-planner --help
python -m two_chunk_planner --help
```

仅开发 package 时可从仓库根目录不安装运行：

```bash
PYTHONPATH=packages/two_chunk_planner/src /usr/bin/python3 -m two_chunk_planner --help
```

已安装的 `two-chunk-planner` 与零安装形式 `python -m two_chunk_planner` 调用同一个
planner；后者仅适合本仓库开发，不是另一种规划模式。

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
完整、权威的 35 项参数选择手册。每项均说明作用、必需性、取值、默认、使用场景、关系、
输出影响、示例和注意事项。TauP、target、search、scoring、NEX/MPI 与 output 的细节应查
reference；本指南只解释常用工作流。

## 5. phase-aware 命令示例

每次运行必须使用不存在的新 output 目录。下面是与 Event 1 验收参数等价、但使用可移植
占位路径的示例：

```bash
D=/path/to/DATA
OUT=/path/to/planner_output

PYTHONPATH=packages/two_chunk_planner/src \
/usr/bin/python3 -m two_chunk_planner plan \
  --cmtsolution "$D/CMTSOLUTION" \
  --stations "$D/STATIONS" \
  --par-file "$D/Par_file" \
  --path-mode phase-aware \
  --phases S,Sdiff \
  --allow-partial-phase-coverage \
  --taup-model prem \
  --taup-resample \
  --analysis-window 0 1600 \
  --output "$OUT"
```

shell 的续行反斜杠后面不能有空格。`--par-file` 可省略且只读：它提供资源建议所需的
NEX/NPROC 与兼容性上下文，不改变 geometry search、不定位 SPECFEM checkout、不验证
patch、也不修改该文件。`--analysis-window` 的终点用于 advisory boundary-time 比较，
不是生产级边界安全证明。

`--taup-resample` 请求程序定义的 TauP 路径重采样，并将选择写入路径元数据；它不建立
波形精度。使用 `--allow-partial-phase-coverage` 时，缺少的请求 station-phase pair 会被
记录且绝不替换。例如 Sdiff 没有 TauP arrival 时，它仍是缺失；若 S 可用，则 planner 可
继续使用 S 路径，并输出 requested/provided/missing inventory。不使用该参数时，strict
模式汇总所有缺失 pair 后停止。

## 6. 程序如何工作

`geometry-only` 默认使用采样地表大圆。`phase-aware` 对每个请求的 phase×station 调用
TauP；Pdiff/Sdiff geographic path 已验证。默认 strict coverage；partial 必须显式给
`--allow-partial-phase-coverage`，且绝不替换 phase。TauP 长度为
`taup_raypath_polyline_estimate`，CMB-near 是 sampled proxy；TauP 禁止用于
boundary-return timing。

planner 读取 source、stations、可选 target 与 phase paths 后，以确定性的 coarse、local、
final 三阶段搜索 canonical two-chunk 的位置和方向。每个 candidate 检查 source、station、
target 和 path coverage；external boundary 与 C1/C2 endpoint margin 进入透明 score。最后
才根据 NEX/NPROC 兼容性生成资源建议。

TauP path 在 orientation search 前准备：每个 source/station/phase/model/resample 组合每次
运行只计算一次。路径的全球单位向量连续存入 NumPy array；程序按小批 orientation 旋转固定
chunk 几何，并用分块数值计算评估 path coverage 与有限大圆弧距离。搜索阶段只保留三阶段
所需的紧凑 feasibility、rejection、score 与排序数据。保守数值 guard 必要时对 keeper
candidate 作精确 scalar 复核；最终选中 candidate 一律生成 JSON 所用的完整 scalar
`GeometryCandidate` audit。这些实现自动启用：没有减少 candidate、station、phase 或
path point，也不改变 score、稳定排序或 tie-breaking。

NEX 不是 orientation search 的控制量。NEX/NPROC 只影响后续 compatibility/resource
recommendation。NEX=96、总 ranks 2/8/12 标为 `project_validated`；其他兼容选项未获项目
验证。

## 7. planner output 目录

每次成功的 `plan` 均写出下列共同文件。它们是普通 planner 输出，不是性能验收产物。

| 文件 | 格式与用途 | 通常检查 |
| --- | --- | --- |
| `report.md` | 简短的人类可读规划结果。 | 返回 candidate 数、推荐 center/gamma、score、phase inventory。 |
| `candidates.json` | 结构化搜索结果：至多五个按序可行 candidate、搜索计数、rejection summary、phase inventory、path records。 | `search`、`candidates`、`phase_inventory`、`phase_paths`。 |
| `candidates.csv` | 返回 candidate 的扁平摘要。 | 坐标、score、feasibility。 |
| `geometry_audit.json` | 选中 candidate 的完整 scalar audit；无可行解时 `chosen_candidate: null`。 | source/station classification、`path_audits`、target audit、margin、score、warning、rejection。 |
| `boundary_time_audit.json` | advisory surface-arc boundary-time proxy。 | `global_status`、records、与 `analysis_end_s` 的 margin；绝不能当作 hard safety proof。 |
| `recommended_Par_file.inc` | 仅供审阅的 canonical geometry 与资源参数片段。 | 手工写入 Par_file 前检查 NCHUNKS、宽度、center、gamma 和任何 NEX/NPROC 建议。 |
| `run_manifest.json` | 输入/运行 provenance 与 mode metadata。 | source、stations、path mode、TauP setting、profile、Par_file provenance。 |
| `map.png` | 经纬度平面图。 | source、station、path、target、outer arcs、AB--AC interface。 |
| `globe.png` | 三维地球图。 | source、station、path 和两个 chunk 的球面闭合关系。 |

geometry-only 和 phase-aware 的文件集合相同。geometry-only 时，`run_manifest.json` 中
TauP setting 为 null，`phase_inventory` 没有请求的 TauP pair，`phase_paths` 是采样地表
geometry paths。phase-aware 时，manifest 写入 TauP model/resample，`phase_inventory` 记录
requested/provided/missing pair，`phase_paths` 是返回的 geographic TauP paths，且 `report.md`
增加 phase-inventory 段落。

最终几何由 `center_latitude_deg`、`center_longitude_deg` 与
`gamma_rotation_azimuth_deg` 描述；加上固定 canonical 90° 宽度即唯一确定两个 chunk。AB
为 central，AC 为 supported-left；AC 没有独立位置或 rotation。`source`、`stations` 与
`path_audits` 报告 chunk classification、coverage 和最小 external/C1/C2 distance。
`score_components` 公开 coverage、external/endpoint margin、cost proxy、normalized value
与 weight。必须审阅 `warnings` 和 `rejection_reasons`。

`map.png` 是经纬度投影。穿过 ±180° 的球面闭合 outer arc 会在该经线被故意断开，以避免
错误的横跨全图 chord；高纬度和大圆弧在此投影中也可能显得明显弯曲或变形。应使用
`globe.png` 查看同一边界的球面闭合关系。

所有 audit 记录 `planner_mode=standalone`、`compatibility_profile_version`、
`specfem_source_verified=false`、`accepted_patch_verified=false`、
`production_configuration_verified=false`、`par_file_source`、
`configuration_status` 和 `verification_warnings`。这些 false 不是 planner 失败：独立
planner 有意不检查用户 SPECFEM source、已安装 patch、mesh 或 runtime validation。

`recommended_Par_file.inc` 只是建议参数片段，不是完整或可直接运行的 Par_file。复制前
应审阅 candidates、geometry audit、boundary-time audit、report 与 fragment。诸如
`summary.json`、`performance_matrix.csv`、profile 与 persistent shell log 只属于专门的
性能验收目录；`plan` 从不生成这些文件。

## 8. 如何快速阅读结果

1. 先读 `report.md` 与 `candidates.json`。返回数大于零且第一个 candidate 为 feasible，
   表示找到了布局。
2. 检查 `geometry_audit.json`：source 和所需 station 应在域内，每条所需 path 应达到
   coverage threshold，external boundary 与 C1/C2 margin 应适合科学审阅。
3. 阅读 `phase_inventory` 与 `warnings`。partial coverage 是显式记录；缺少 Sdiff 不会
   被 S 静默替换。
4. 对照原始 `Par_file` 审阅 `recommended_Par_file.inc`：确认 NEX/NPROC 的倍数与整除要求，
   并区分外部 Par_file 读入值和 planner 建议。
5. 查看两张图，再在独立 SPECFEM workflow 中完成 mesh、topology、Stacey、solver、
   waveform 与 boundary-return 验证。

## 9. 完整工作流

1. 安装 package，准备 source 与 stations。
2. 选择 geometry-only 初筛或 phase-aware 复核。
3. 可选准备严格 target YAML 和/或 external Par_file。
4. 向新 output 目录运行 `plan`。
5. 审阅 candidate 排名、classification、margin、warning 和 resource label。
6. 在外部 SPECFEM workflow 中自行应用/验证 accepted patch，再验证 mesh/topology、
   Stacey、solver、waveform 和 external returns。

## 10. 验证、性能与科学状态

boundary seconds 始终是 advisory `heuristic_not_conservative` surface-arc proxy；
`boundary_time_production_safe=false`。sampling stability 为 `indeterminate`
（Pdiff 0.130094%，Sdiff 0.076131% resample-length difference）。Kim/Song 精确复现
仍缺作者原始输入。

本 package 使用 [GPL-3.0-or-later](../LICENSE)；见
[third-party notices](../THIRD_PARTY_NOTICES.md) 与
[validation status](validation_status.md)。

保留的 Event 1 phase-aware 验收两次分别完成于 12:31.62 与 12:28.80，输出严格一致，
package pytest 为 20 项通过。相对上一轮约 18.5 分钟的运行快约 32%；旧版只有 >1800 s
timeout 下界。10 分钟目标尚未达到。实际耗时主要取决于 orientation candidate、有效
phase path 与 path sampling point，而非 NEX 单独决定。详见
[Event 1 性能记录](../../../docs/two_chunk_planner_high_frequency_search.md)。
