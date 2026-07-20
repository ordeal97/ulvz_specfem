<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# `two-chunk-planner plan` CLI 参考

版本 0.2.0，许可证 GPL-3.0-or-later。本参考描述独立运行的 canonical 90°×90°、
AB central/AC supported-left 规划器。它没有项目根目录、manifest、SPECFEM 源码或
patch 验证模式。参数清单由 parser 生成于
[`generated/cli_options.json`](generated/cli_options.json)，并自动与本页核对。

## 运行方式

**完全独立：** 提供 source、stations 以及 phases 或时间终点；内置 profile 只提供
planning defaults。**独立并读取 Par_file：** 添加 `--par-file /任意路径/Par_file`，
只读取与资源有关的值。两种方式都不验证用户的 SPECFEM 源码或 accepted patch；生产
模拟前必须用独立 patch package 完成该工作。

~~~bash
two-chunk-planner plan --source 0 0 50 --stations-csv stations.csv \
  --analysis-window 0 1900 --output plan_out
~~~

所有参数均无短参数。`--output` 必需；其余默认值均为 parser 默认值。source 形式
必须二选一，station 形式必须二选一；phases、analysis window、target-energy end 至少
给出一个。已存在的 output 目录始终拒绝覆盖。

已安装的 `two-chunk-planner` 与
`PYTHONPATH=packages/two_chunk_planner/src /usr/bin/python3 -m two_chunk_planner`
使用同一 parser；后者只是仓库开发调用，不是另一种 CLI 模式。

## 1. Source 与 station 输入

### `--cmtsolution`
短参数：无。类型：路径。可选，但与 `--source` 互斥，二者必须有一个。读取 SPECFEM
CMTSOLUTION（PDE header 与 labelled records）。例：`--cmtsolution DATA/CMTSOLUTION`。
字段缺失、数值错误或全零矩张量都会停止规划。

### `--source`
短参数：无。类型：三个浮点数 `LAT LON DEPTH_KM`；无默认值。与 `--cmtsolution`
互斥，二者必须有一个。例：`--source 0 -125 50`。纬度、深度须有限且深度非负；它只
绕过 CMTSOLUTION 解析，不会创建输入文件。

### `--stations`
短参数：无。类型：路径。与 `--stations-csv` 互斥，二者必须有一个。例：
`--stations DATA/STATIONS`。每台站须为六个空白分隔字段；重复 network/station 或
坏坐标会失败。

### `--stations-csv`
短参数：无。类型：路径。与 `--stations` 互斥，二者必须有一个。例：
`--stations-csv stations.csv`。必需列为 `network,station,latitude_deg,longitude_deg`；
elevation/burial 可选。

## 2. Phase、analysis window 与 target end

### `--phases`
短参数：无。类型：逗号分隔相名；默认无。仅 `phase-aware` 使用；例：
`--phases Pdiff,Sdiff`。只请求这些 TauP phase，不自动替换；仅在给出 window/end 时可省略。

### `--analysis-window`
短参数：无。类型：两个浮点数 `START_S END_S`；默认无。例：`--analysis-window 0 1900`。
除非给出 `--target-energy-end-s`，其终点用于 advisory boundary-time 比较。

### `--target-energy-end-s`
短参数：无。类型：浮点秒；默认无。例：`--target-energy-end-s 1900`。它覆盖 window end
用于 advisory margin；不是生产级边界安全约束。

## 3. 路径模式

### `--path-mode`
短参数：无。choices：`geometry-only`、`phase-aware`；默认 `geometry-only`。
前者采样地表大圆，后者请求 TauP geographic ray path。例：`--path-mode phase-aware`。

### `--path-samples`
短参数：无。类型：整数；默认 `121`。只用于 geometry-only 大圆采样。例：
`--path-samples 241`。不会重采样 TauP，也不保证波形精度。

## 4. TauP、resample 与 partial coverage

### `--taup-model`
短参数：无。类型：TauP model 名；默认 `prem`；只用于 phase-aware。例：
`--taup-model prem`。model/phase 不可用时 strict coverage 报错。

### `--taup-resample`
短参数：无。布尔 flag；默认 false；只用于 phase-aware。例：`--taup-resample`。
选择会写入 path metadata；长度仍是 `taup_raypath_polyline_estimate`。

### `--ray-param-tol`
短参数：无。类型：浮点；默认 `1e-06`；只用于 phase-aware。例：`--ray-param-tol 1e-6`。
传给 TauP request 并记录。

### `--cmb-near-depth-tolerance-km`
短参数：无。类型：浮点 km；默认 `25.0`；只用于 phase-aware。例：
`--cmb-near-depth-tolerance-km 20`。控制 sampled CMB-near proxy，不是物理界面交点。

### `--allow-partial-phase-coverage`
短参数：无。布尔 flag；默认 false（strict）。例：`--allow-partial-phase-coverage`。
strict 会汇总所有缺失 phase×station 后失败；partial 只保留返回的原请求 phase，并写入
no-substitution warning/inventory。

## 5. Target region

### `--target-region`
短参数：无。类型：严格 YAML 路径；默认无。例：`--target-region target_circle.yaml`。
仅支持 circle、polygon、corridor schema；未知/缺失字段失败，并影响 coverage 约束。

## 6. Boundary time

### `--boundary-speed-upper-km-s`
短参数：无。类型：正浮点 km/s；默认无。例：`--boundary-speed-upper-km-s 14`。输出
`heuristic_not_conservative` surface-arc proxy；仅 advisory，且 TauP 禁止用于此计算。

## 7. Center/gamma 搜索与细化

### `--latitude-range`
短参数：无。格式：`MIN,MAX`；默认 `-90,90`。例：`--latitude-range -20,20`。定义中心纬度范围。

### `--longitude-range`
短参数：无。格式：`MIN,MAX`；默认 `-180,180`。例：`--longitude-range 120,180`。定义中心
经度范围；极点等价表示会稳定去重。

### `--gamma-range`
短参数：无。格式：`MIN,MAX`；默认 `0,360`。例：`--gamma-range 0,90`。定义整体 gamma 范围。

### `--coarse-latitude-step`
短参数：无。类型：浮点度；默认 `10.0`。例：`--coarse-latitude-step 5`。粗搜索纬度步长。

### `--coarse-longitude-step`
短参数：无。类型：浮点度；默认 `10.0`。例：`--coarse-longitude-step 5`。粗搜索经度步长。

### `--coarse-gamma-step`
短参数：无。类型：浮点度；默认 `15.0`。例：`--coarse-gamma-step 10`。粗搜索 gamma 步长。

### `--local-latitude-step`
短参数：无。类型：浮点度；默认 `2.0`。例：`--local-latitude-step 1`。局部纬度细化。

### `--local-longitude-step`
短参数：无。类型：浮点度；默认 `2.0`。例：`--local-longitude-step 1`。局部经度细化。

### `--local-gamma-step`
短参数：无。类型：浮点度；默认 `3.0`。例：`--local-gamma-step 1`。局部 gamma 细化。

### `--final-latitude-step`
短参数：无。类型：浮点度；默认 `0.5`。例：`--final-latitude-step 0.25`。最终纬度步长。

### `--final-longitude-step`
短参数：无。类型：浮点度；默认 `0.5`。例：`--final-longitude-step 0.25`。最终经度步长。

### `--final-gamma-step`
短参数：无。类型：浮点度；默认 `0.5`。例：`--final-gamma-step 0.25`。最终 gamma 步长。

## 8. Scoring 与 coverage

### `--weights`
短参数：无。类型：严格 YAML 路径；默认无。例：`--weights weights.yaml`。仅允许
`coverage`、`external_margin`、`endpoint_margin`、`cost`；都非负且至少一个正值。它替换
score weight，不替换 hard constraint。

### `--minimum-path-coverage`
短参数：无。类型：`(0,1]` 浮点；默认 `1.0`。例：`--minimum-path-coverage 0.9`。低值允许
部分 coverage；范围外失败。

## 9. NEX、MPI 与 cost

### `--available-ranks`
短参数：无。格式：逗号分隔 total ranks；默认是 external Par_file 的 NPROC（若有），否则
profile `2,8,12`。例：`--available-ranks 8,12`。只有 canonical NEX=96 的 2/8/12 标为
`project_validated`。

### `--nex`
短参数：无。格式 `XIxETA`；可重复；默认 external Par_file NEX（若有），否则 profile
`96x96`。例：`--nex 96x96 --nex 192x96`。每项按所选 planning physics branch 检查。

### `--max-compute-cost`
短参数：无。类型：浮点；默认无。例：`--max-compute-cost 2304`。按 lateral-work-per-rank
proxy 过滤建议；不是运行时间预测。

## 10. 可选 Par_file

### `--par-file`
短参数：无。类型：任意可读 Par_file 路径；默认无。例：`--par-file /work/case/DATA/Par_file`。
只读 NEX/NPROC 与兼容性 flag；不寻找 SPECFEM，也不验证源码/patch。省略时使用标为
`builtin_profile` 的 planning defaults。

## 11. Output 与安全性

没有 `--log` 参数。面向用户的错误写到 standard error；正常规划除生成文件外保持安静。
外部工作流若需要持久日志，应由 shell 捕获 stdout/stderr。

### `--output`
短参数：无。类型：目录路径；必需。例：`--output plan_out`。目录必须不存在；成功后写入
`candidates.json`、`candidates.csv`、`geometry_audit.json`、
`boundary_time_audit.json`、`run_manifest.json`、`recommended_Par_file.inc`、
`report.md`、`map.png` 与 `globe.png`。geometry-only 和 phase-aware 写出相同文件名；
phase-aware 在结构化输出中额外写入 requested/provided/missing TauP inventory 与 TauP
path metadata。重复目录是刻意错误。`summary.json`、`performance_matrix.csv`、profile、
persistent log 等性能验收文件不是 planner output。

## 许可证与限制

本 package 使用 GPL-3.0-or-later；见 [LICENSE](../LICENSE) 与
[third-party notices](../THIRD_PARTY_NOTICES.md)。仅支持 canonical 90°×90°，general
classification 为 B。Pdiff/Sdiff phase-aware 已验证，sampling stability 为
`indeterminate`，`boundary_time_production_safe=false`。它不验证用户 patch，也不替代
mesher/database/solver、Stacey、topology 或 waveform 验收。
Event 1 的简短运行结论和完整证据见项目级
[性能记录](../../../docs/two_chunk_planner_high_frequency_search.md)。
