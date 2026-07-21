<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# `two-chunk-planner plan` CLI 参考

版本 0.2.1，许可证 GPL-3.0-or-later。这是独立 canonical two-chunk planner 的完整参数
选择手册，说明当前 parser 的真实行为，而不是另一套 SPECFEM 工作流。planner 不修改或
验证 SPECFEM 源码、patch、网格、数据库、Stacey 边界或波形。参数清单生成于
[`generated/cli_options.json`](generated/cli_options.json)，并自动与两个语言版本核对。

使用 `two-chunk-planner --help` 查看顶层命令，使用
`two-chunk-planner plan --help` 查看 parser 摘要。所有下列参数都没有短形式。安装后的
命令和下面的仓库调用使用完全相同的 parser。

~~~bash
PYTHONPATH=packages/two_chunk_planner/src /usr/bin/python3 -m two_chunk_planner plan --help
~~~

## 先读这一节

`plan` 有 35 个生成式元数据覆盖的长参数。`--output` 是唯一 argparse 必填参数；运行时
还要求 source 二选一（`--cmtsolution` 或 `--source`）、station 二选一（`--stations` 或
`--stations-csv`），并且 `--phases`、`--analysis-window`、`--target-energy-end-s` 至少
出现一个。

**没有**用于 chunk 宽度、chunk 拓扑、绘图开关、公开诊断开关或 NumPy batch 大小的 CLI
参数。几何始终是两个 90°×90° chunk（AB central、AC supported-left）；`map.png` 和
`globe.png` 总会自动输出；内部 NumPy 批处理也无需用户开启。

同样没有用户可设置的 outer-boundary 或 C1/C2 硬安全距离阈值。这些距离会作为 containment
audit 与 score component 计算；`--weights` 只能改变其 ranking 权重，不能把它们变成新的硬约束。

### 最小可运行命令

下例是低成本 geometry-only 检查，使用采样的地表大圆路径。它适合验证输入格式和输出目录，
不适合相位科学问题。

~~~bash
D=/path/to/DATA
OUT=/path/to/new_geometry_plan

two-chunk-planner plan \
  --cmtsolution "$D/CMTSOLUTION" \
  --stations "$D/STATIONS" \
  --analysis-window 0 600 \
  --output "$OUT"
~~~

### 推荐的 phase-aware 命令

当科学问题需要覆盖真实请求的相位路径时使用。shell 续行反斜杠后面不能有空格。

~~~bash
D=/path/to/DATA
OUT=/path/to/new_phase_plan

PYTHONPATH=packages/two_chunk_planner/src \
/usr/bin/python3 -m two_chunk_planner plan \
  --cmtsolution "$D/CMTSOLUTION" \
  --stations "$D/STATIONS" \
  --par-file "$D/Par_file" \
  --path-mode phase-aware \
  --phases S,Sdiff \
  --taup-model prem \
  --taup-resample \
  --analysis-window 0 1600 \
  --output "$OUT"
~~~

### 常见参数组合

- 只有在科学上允许“明确记录缺失 station–phase pair 后，继续使用已返回子集”时，才加
  `--allow-partial-phase-coverage`；它绝不会用 S 替换缺失的 Sdiff。
- 当两个 chunk 还必须覆盖指定 circle、polygon 或 corridor 时，加
  `--target-region target.yaml`。
- 当资源建议需要使用实际 case 的上下文时，加 `--par-file "$D/Par_file"`；只有比较
  替代网格或 rank 时才加 `--nex`、`--available-ranks`。
- 应先缩小有科学依据的纬度、经度、gamma 范围，再考虑减小搜索步长；更宽范围和更小步长
  会明显增加运行时间。

### 通常保持默认值的参数

多数用户应保持 `prem`、完整路径覆盖（`1.0`）、默认评分权重、canonical 几何及
coarse/local/final 默认步长。只有在有明确科学或计算理由时才改动。NEX/NPROC 不决定
orientation 候选数。

## 1. 输入文件

source 两种形式必须二选一，station 两种形式必须二选一。

### `--cmtsolution`

- **作用：** 从 SPECFEM CMTSOLUTION 读取震源，并把震源位置/深度用于路径构造和全部
  candidate 审计。
- **是否必需：** 条件必需；给它或 `--source` 之一，不能同时给。
- **取值：** 可读 CMTSOLUTION 路径，须含 PDE header 和 12 条 labelled record；位置是
  度，深度是 km。
- **默认：** 无；两种 source 都未给时规划失败。
- **何时使用：** 已有 SPECFEM event 时使用；若只是合成震源测试且直接给坐标更方便，使用
  `--source`。
- **关系：** 与 `--source` 互斥；在 phase-aware 时影响 TauP 路径，在 geometry-only 时
  影响大圆路径。
- **输出影响：** 写入 `run_manifest.json` 的 source provenance，并改变可行性、score、
  path、图件和全部 audit。
- **示例：** `--cmtsolution "$D/CMTSOLUTION"`。
- **注意：** 字段错误、坐标无效、深度为负或零矩张量会停止运行；它不验证 event file 与
  solver 设置是否匹配。

### `--source`

- **作用：** 不解析 CMTSOLUTION，直接给出震源。
- **是否必需：** 条件必需；给它或 `--cmtsolution` 之一，不能同时给。
- **取值：** 三个有限数 `LAT LON DEPTH_KM`；纬度/经度是地理度，深度为非负 km。
- **默认：** 无；两种 source 都未给时规划失败。
- **何时使用：** 小型合成或敏感性测试时使用；若输出必须保留 CMTSOLUTION provenance，
  不应使用它。
- **关系：** 与 `--cmtsolution` 互斥；其余路径和几何处理相同。
- **输出影响：** 改变 source 相关 coverage、score、图件，并把所给值写入 manifest。
- **示例：** `--source 0 -125 50`。
- **注意：** 它不会创建 CMTSOLUTION，也不会推断矩张量或发震时刻。

### `--stations`

- **作用：** 从 SPECFEM 空白分隔的 STATIONS 文件读取接收台站。
- **是否必需：** 条件必需；给它或 `--stations-csv` 之一，不能同时给。
- **取值：** 可读 STATIONS 路径；每行六个空白分隔字段，台站坐标为地理度。
- **默认：** 无；两种 station 输入均未给时规划失败。
- **何时使用：** 用于真实 simulation case 的 SPECFEM-ready 台站表；不要与
  `--stations-csv` 同时使用。
- **关系：** 与 `--stations-csv` 互斥；台站数会乘上请求相位数和路径评估量。
- **输出影响：** 改变台站包含判断、路径、score、图件、candidate 可行性和 manifest 中的
  台站 provenance。
- **示例：** `--stations "$D/STATIONS"`。
- **注意：** 重复 network/station ID、坏坐标、格式错误或空文件会停止规划。

### `--stations-csv`

- **作用：** 从可移植 CSV 读取台站，而非从 SPECFEM STATIONS 读取。
- **是否必需：** 条件必需；给它或 `--stations` 之一，不能同时给。
- **取值：** 包含 `network,station,latitude_deg,longitude_deg` 的 CSV；可额外有 elevation
  和 burial 列。
- **默认：** 无；两种 station 输入均未给时规划失败。
- **何时使用：** SPECFEM 之前的筛选或外部维护的台站表时使用；不要与 `--stations` 同时
  使用。
- **关系：** 与 `--stations` 互斥；向后续程序提供相同的 station 对象。
- **输出影响：** 改变路径、包含判断、score、图件和 manifest 中保存的台站表。
- **示例：** `--stations-csv stations.csv`。
- **注意：** 缺少必需列或有重复 network/station pair 会停止运行；CSV 不会更新 SPECFEM
  STATIONS 文件。

## 2. 路径与相位

`geometry-only` 为每个台站采样一条地表大圆；`phase-aware` 对每个 station–phase pair
单独请求 TauP。只给 `--phases` 不会自动切换模式，必须同时给 `--path-mode phase-aware`。

### `--path-mode`

- **作用：** 选择用于 coverage 评估的路径构造方式。
- **是否必需：** 可选。
- **取值：** 只能是 `geometry-only` 或 `phase-aware`。
- **默认：** `geometry-only`。
- **何时使用：** 快速几何筛选用 geometry-only；需要覆盖请求的 TauP 相位路径时用
  phase-aware。
- **关系：** `--path-samples` 只用于 geometry-only；TauP 参数只影响 phase-aware；
  `--phases` 不会自行改变模式。
- **输出影响：** 两种模式均输出相同九个文件；phase-aware 增加 TauP path/phase inventory，
  geometry-only 写入采样地表路径和 null TauP setting。
- **示例：** `--path-mode phase-aware`。
- **注意：** phase-aware 需要可选的 ObsPy/TauP 依赖，并会在 orientation 搜索前对每个 pair
  请求路径，可能显著变慢。

### `--phases`

- **作用：** 指定 phase-aware 模式中请求的 TauP 相位名。
- **是否必需：** argparse 中可选；运行时 `--phases`、`--analysis-window`、
  `--target-energy-end-s` 至少给一个。
- **取值：** 逗号分隔的相位名，例如 `S,Sdiff` 或 `Pdiff,Sdiff`。
- **默认：** 不请求相位。
- **何时使用：** 与 `--path-mode phase-aware` 一起使用；仅 geometry-only 且已给时间终点时
  可省略。
- **关系：** 每个相位都会对每个台站请求；strict/partial 行为由
  `--allow-partial-phase-coverage` 控制。
- **输出影响：** phase-aware 会把 requested/provided/missing pair 与返回 TauP path 写入 JSON，
  并改变 coverage、score 和运行时间。
- **示例：** `--phases S,Sdiff`。
- **注意：** 语义上需要逗号；`S, Sdiff` 会去除空格后接受，但不常见名称最好 shell quote。
  程序绝不自动用另一种 phase 替代请求 phase。

### `--path-samples`

- **作用：** 设置每条 geometry-only 地表大圆路径的采样点数。
- **是否必需：** 可选；仅 geometry-only 有意义。
- **取值：** 整数点数；默认 `121`。
- **默认：** 每台站路径 121 点。
- **何时使用：** 只有 geometry-only containment screen 需要更细路径采样时才增加；phase-aware
  不应使用它控制 TauP 路径。
- **关系：** TauP path 生成时忽略；与 `--taup-resample` 独立。
- **输出影响：** 改变 geometry-only 的 `phase_paths`、离散 coverage、两幅图及每个 candidate
  的计算量。
- **示例：** `--path-samples 241`。
- **注意：** 它不提高物理波形精度，也不改变 TauP 路径；更多点会增大 geometry-only 搜索
  工作量。

### `--taup-model`

- **作用：** 选择传给 `TauPyModel` 的 TauP 速度模型。
- **是否必需：** 可选；仅 phase-aware 有意义。
- **取值：** 当前 ObsPy 环境可用的 TauP model 名。
- **默认：** `prem`。
- **何时使用：** 文档化工作流保持 `prem`；只有确实要以另一模型的相位预测作为规划依据时才
  更改。
- **关系：** 与 `--phases`、source/stations、`--taup-resample`、`--ray-param-tol` 共同决定
  TauP 请求；只在 phase-aware manifest 中记录。
- **输出影响：** 可改变返回/缺失相位、路径几何、coverage、score、phase inventory、图件和
  运行时间。
- **示例：** `--taup-model prem`。
- **注意：** model 不可用或请求 arrival 缺失时，strict 模式报错；只有显式 partial 才会继续。

### `--taup-resample`

- **作用：** 请求 TauP 返回重采样后的地理 ray-path polyline。
- **是否必需：** 可选布尔 flag；仅 phase-aware 有意义。
- **取值：** 出现即 true；不出现即 false。
- **默认：** false。
- **何时使用：** 需要程序定义的 TauP 重采样以获得更密或更规则的返回路径表示时使用；否则
  保持 TauP 未重采样输出。
- **关系：** 与 `--taup-model`、`--phases`、`--ray-param-tol` 一起传给 TauP；与
  geometry-only 的 `--path-samples` 无关。
- **输出影响：** 写入 `resample` 和 path-point metadata；可能改变离散路径 coverage、图件和
  TauP/预搜索时间。
- **示例：** `--taup-resample`。
- **注意：** 它不选择不同请求 phase，也不替换物理 model；它改变 planner 使用的路径离散表示，
  不是波形精度认证。

### `--ray-param-tol`

- **作用：** 将 ray-parameter tolerance 传递给 TauP 地理路径请求。
- **是否必需：** 可选；仅 phase-aware 有意义。
- **取值：** 浮点 tolerance；默认 `1e-06`。
- **默认：** `1e-06`。
- **何时使用：** 除非有明确数值研究理由，应保持默认。
- **关系：** 与 `--taup-model`、`--phases`、`--taup-resample` 一起使用。
- **输出影响：** 记录在 path metadata；只有当 TauP 结果改变时才可能改变路径和 coverage。
- **示例：** `--ray-param-tol 1e-6`。
- **注意：** 它不是几何边界 tolerance，也不应被调节为“强行得到”某个 arrival。

### `--cmb-near-depth-tolerance-km`

- **作用：** 设置 TauP 路径最大采样深度附近的深度带，用来生成每条路径保存的 CMB-near
  proxy。
- **是否必需：** 可选；仅 phase-aware 有意义。
- **取值：** 非负浮点 km；默认 `25.0`。
- **默认：** 最大采样深度参考附近 25 km。
- **何时使用：** 只有在审查描述性 CMB-near segment 应取多宽时才改变。
- **关系：** 在 TauP path 返回后运行；不改变请求 phase、TauP model 或 boundary-time 计算。
- **输出影响：** 改变结构化 path 中的 `cmb_near_proxy` metadata；不改变 path point、可行性、
  score 或搜索范围。
- **示例：** `--cmb-near-depth-tolerance-km 20`。
- **注意：** 它是最大采样深度 proxy，不是物理 CMB 交点，也不是 ULVZ 穿越计算。

### `--allow-partial-phase-coverage`

- **作用：** 当 TauP 无法返回部分请求 station–phase pair 时，允许 phase-aware 继续。
- **是否必需：** 可选布尔 flag；只对 phase-aware 路径有意义。
- **取值：** 出现即 partial；不出现即 strict。
- **默认：** false（strict）。
- **何时使用：** 只有当科学上允许由“已返回的请求路径子集”规划，并单独审查缺失 pair 时使用。
- **关系：** 处理 `--phases`/`--taup-model` 请求失败；不降低 `--minimum-path-coverage`，也不
  改变 target 检查。
- **输出影响：** partial 会写入 missing-pair inventory 和 warning，然后仅评估返回的请求 path；
  strict 在输出前停止。
- **示例：** `--allow-partial-phase-coverage`。
- **注意：** 缺失的 Sdiff 仍是缺失；绝不会替换成 S。partial 不表示未返回 path 已被覆盖。

## 3. 时间、目标区域与覆盖约束

### `--analysis-window`

- **作用：** 提供分析起止时间标签，并把终点用于 advisory boundary-time 比较。
- **是否必需：** 可选，但可满足“至少提供一个时间或相位输入”的运行时要求。
- **取值：** 两个浮点秒 `START_S END_S`。
- **默认：** 无。
- **何时使用：** 普通规划运行都应给出信号分析窗，包括 phase-aware Event 类案例。
- **关系：** 若给 `--target-energy-end-s`，后者只覆盖 advisory 比较的终点；它与 `--phases`、
  path sampling 独立。
- **输出影响：** 在 `boundary_time_audit.json` 写入 `analysis_window`、`analysis_end_s`；不改变
  candidate 生成或 score。
- **示例：** `--analysis-window 0 1600`。
- **注意：** 单位为秒。它**不会**截取 TauP 或 geometry path、过滤 arrival，亦不能证明 1600 s
  内没有边界返回。

### `--target-energy-end-s`

- **作用：** 为 advisory boundary-time 输出单独提供目标能量终点。
- **是否必需：** 可选，但可满足“至少提供一个时间或相位输入”的运行时要求。
- **取值：** 一个浮点秒数。
- **默认：** 无。
- **何时使用：** 当科学上关心的信号能量结束时间不同于 `--analysis-window` 终点时使用。
- **关系：** 只覆盖 boundary-time 输出中的 analysis-window end；不改变 path、coverage、score
  或搜索。
- **输出影响：** 改变 `boundary_time_audit.json` 中的 `analysis_end_s` 与 advisory margin。
- **示例：** `--target-energy-end-s 1850`。
- **注意：** 它不是硬边界安全约束，也不裁切波形或 path 数据。

### `--target-region`

- **作用：** 增加一个必须完全包含在所选 two-chunk domain 内的地理 target。
- **是否必需：** 可选。
- **取值：** 定义 `circle`、`polygon` 或 `corridor` 的严格 YAML 路径；坐标为度，半径/宽度为 km。
- **默认：** 没有 target-region containment 约束。
- **何时使用：** 当 ULVZ、研究区域或必需 corridor 必须放入两个 chunk 时使用；只关心
  source/stations/path 时省略。
- **关系：** 与全部 candidate geometry check 组合；target 需独立达到 1.0 coverage，不受
  `--minimum-path-coverage` 放宽。
- **输出影响：** 可拒绝 candidate、改变 score/margin、增加 target audit，并在两幅图中绘出
  target。
- **示例：** `--target-region target_circle.yaml`。
- **注意：** YAML 未知字段、无效几何或不完整 containment 会导致失败/拒绝；target sampling 是
  文档化的 heuristic audit，也会增加每 candidate 工作量。

### `--weights`

- **作用：** 替换 coverage、external margin、endpoint margin、cost 的默认 score 权重。
- **是否必需：** 可选。
- **取值：** 严格 YAML mapping，只允许 `coverage`、`external_margin`、`endpoint_margin`、
  `cost`；数值非负且至少一个为正。
- **默认：** 内置权重依次为 0.35、0.30、0.20、0.15。
- **何时使用：** 只有在透明、可记录地改变 ranking 优先级，并确认 hard feasibility 仍合适时才用。
- **关系：** 替换 score weight，但不替换 source/station containment、target containment 或
  `--minimum-path-coverage`。
- **输出影响：** 可改变可行 candidate 排名和 JSON/CSV score component；不改变生成的 orientation
  点集合。
- **示例：** `--weights weights.yaml`。
- **注意：** 它不能把不可行 candidate 变为可行；非默认权重应记录科学理由。

### `--minimum-path-coverage`

- **作用：** 设置每条被评估 path 必须在域内的最小比例。
- **是否必需：** 可选。
- **取值：** 严格位于 `(0,1]` 的浮点；默认 `1.0`。
- **默认：** 每条被评估 path 的全部采样点必须在域内。
- **何时使用：** 完整路径 containment 保持 1.0；只有明确论证部分路径标准时才降低。
- **关系：** 适用于 geometry-only 和返回的 phase-aware path；与处理缺失 path 的
  `--allow-partial-phase-coverage` 不同。
- **输出影响：** 改变 candidate 可行性、rejection reason、score 和 path audit；不会删除 path 点。
- **示例：** `--minimum-path-coverage 0.9`。
- **注意：** 范围外会停止运行。较低阈值不放宽 target-region 全覆盖，也不能替代缺失 TauP
  arrival。

### `--boundary-speed-upper-km-s`

- **作用：** 为 advisory 的地表弧长边界返回时间 proxy 提供速度上界。
- **是否必需：** 可选。
- **取值：** 正浮点 km/s。
- **默认：** 无；不计算 earliest-return seconds。
- **何时使用：** 只有在明确标为 preliminary 的分析终点比较中使用。
- **关系：** 使用 `--analysis-window` 或 `--target-energy-end-s` 的终点比较；本计算刻意不使用
  TauP path。
- **输出影响：** 在 `boundary_time_audit.json` 填入 heuristic return 秒数/margin；不影响搜索、
  score、path 或图。
- **示例：** `--boundary-speed-upper-km-s 14`。
- **注意：** 结果为 `heuristic_not_conservative`，不是三维吸收边界证明，也不是生产级安全判据。

## 4. 固定几何与 orientation 搜索

chunk 宽度和拓扑固定：两个 90°×90° chunk，AB central 加 AC supported-left。搜索只控制
地理 center 与 gamma rotation。程序执行确定性的 coarse、local、final 三阶段，稳定去重和
tie-breaking。范围更窄会减少候选；步长更小会增加候选，尤其是 coarse 阶段。

### `--latitude-range`

- **作用：** 限制 candidate center 纬度。
- **是否必需：** 可选。
- **取值：** 逗号分隔度数 `MIN,MAX`；默认 `-90,90`。
- **默认：** 搜索完整纬度范围。
- **何时使用：** 有科学依据的地理带可限制此范围以减少搜索量。
- **关系：** 与 longitude/gamma range 和三阶段步长共同决定候选；每个 range 均须恰有两个值。
- **输出影响：** 改变 candidate 集合、运行时间、可行排名和所选 center；不改变 chunk 宽度。
- **示例：** `--latitude-range -20,20`。
- **注意：** 极区等价坐标会稳定 canonicalize；不能为了方便而排除缺少物理依据的区域。

### `--longitude-range`

- **作用：** 限制 candidate center 经度。
- **是否必需：** 可选。
- **取值：** 逗号分隔度数 `MIN,MAX`；默认 `-180,180`。
- **默认：** 搜索完整经度范围。
- **何时使用：** 有依据地限制在研究区附近时使用。
- **关系：** 与 latitude/gamma range、阶段步长组合；经度会在确定性 canonicalization 时归一化。
- **输出影响：** 改变 candidate 数、运行时间、所选 orientation 和全部几何输出。
- **示例：** `--longitude-range 120,180`。
- **注意：** 此范围不改变输入文件中的经度约定，也不改变固定 90° chunk 宽度。

### `--gamma-range`

- **作用：** 限制固定 two-chunk arrangement 的整体 gamma rotation。
- **是否必需：** 可选。
- **取值：** 逗号分隔度数 `MIN,MAX`；默认 `0,360`。
- **默认：** 搜索全部 gamma orientation。
- **何时使用：** 只有存在物理 orientation prior 时才限制。
- **关系：** 与 center range 组合；完整 360° interval 在 canonicalization 中按周期处理。
- **输出影响：** 改变 candidate 数、布局方向、path margin、candidate rank 和图件。
- **示例：** `--gamma-range 0,90`。
- **注意：** gamma 不是第二个 chunk 的独立位置；AC 没有独立平移或旋转。

### `--coarse-latitude-step`

- **作用：** 设置第一阶段纬度网格间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `10.0`。
- **默认：** coarse 纬度间距 10°。
- **何时使用：** coarse global search 需要更密时才减小；增大时须谨慎，因为可能在 refinement 前
  漏掉更优区域。
- **关系：** 与 coarse longitude/gamma step 相乘决定 coarse 候选；local/final 是细化 keeper，
  不取代 coarse 覆盖。
- **输出影响：** 强烈改变生成 orientation 数、搜索时间和可能的最终 candidate。
- **示例：** `--coarse-latitude-step 5`。
- **注意：** 比较 run 时应维持相同科学搜索范围；这是分辨率控制，不是图形设置。

### `--coarse-longitude-step`

- **作用：** 设置第一阶段经度网格间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `10.0`。
- **默认：** coarse 经度间距 10°。
- **何时使用：** 只有需要更密或更廉价的 first-stage orientation grid 时，与其它 coarse step 一起
  改动。
- **关系：** 与 coarse latitude/gamma 数量相乘；后续阶段只围绕保留的 coarse keeper。
- **输出影响：** 改变 coarse candidate 数、运行时间和可能的最终 orientation。
- **示例：** `--coarse-longitude-step 5`。
- **注意：** 在很宽经度范围内减小它会造成很大的运行时间增长。

### `--coarse-gamma-step`

- **作用：** 设置第一阶段 gamma 网格间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `15.0`。
- **默认：** coarse gamma 间距 15°。
- **何时使用：** 只有确需在有依据的 gamma range 内更密 coarse sampling 时才减小。
- **关系：** 与另外两个 coarse 维度相乘；gamma 仍为周期/规范化 orientation。
- **输出影响：** 改变 coarse candidate 数、运行时间及得到 local refinement 的区域。
- **示例：** `--coarse-gamma-step 10`。
- **注意：** 它不会独立旋转单个 chunk。

### `--local-latitude-step`

- **作用：** 设置 coarse keeper 周围 local refinement 的纬度间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `2.0`。
- **默认：** local 纬度间距 2°。
- **何时使用：** 在保持预期 coarse search 的前提下，确有局部精度/成本权衡时改动。
- **关系：** 与 local longitude/gamma step 一起在保留 coarse candidate 周围固定邻域使用。
- **输出影响：** 改变 local candidate、运行时间和可能的最终 rank；不扩展初始全局范围。
- **示例：** `--local-latitude-step 1`。
- **注意：** 减小会增加 local 成本，并应确保 coarse coverage 足以找到相应 basin。

### `--local-longitude-step`

- **作用：** 设置 coarse keeper 周围 local refinement 的经度间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `2.0`。
- **默认：** local 经度间距 2°。
- **何时使用：** 只有需要局部 orientation 分辨率研究时才改变。
- **关系：** 与 local latitude/gamma step 一起使用，并受三项搜索范围约束。
- **输出影响：** 改变 local candidate 数、运行时间和传入 final 的 candidate。
- **示例：** `--local-longitude-step 1`。
- **注意：** 它不是 station 或 map 的经度分辨率设置。

### `--local-gamma-step`

- **作用：** 设置 coarse keeper 周围 local refinement 的 gamma 间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `3.0`。
- **默认：** local gamma 间距 3°。
- **何时使用：** 只有需要更细局部布局方向时才改动。
- **关系：** 与 local latitude/longitude step 配合；若 `--gamma-range` 不是完整圆，则受其限制。
- **输出影响：** 改变 local orientation 评估、运行时间和可能的 final candidate。
- **示例：** `--local-gamma-step 1`。
- **注意：** 它控制搜索分辨率，不改变 chunk 的物理宽度或拓扑。

### `--final-latitude-step`

- **作用：** 设置 top local keeper 周围最终阶段最细纬度间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `0.5`。
- **默认：** final 纬度间距 0.5°。
- **何时使用：** 只有需要更细最终 orientation 精度且接受运行成本时才减小。
- **关系：** 与 final longitude/gamma step 在 top local candidate 周围固定小邻域共同使用。
- **输出影响：** 改变 final candidate 评估、排名和所选 center，不改变全局搜索范围。
- **示例：** `--final-latitude-step 0.25`。
- **注意：** 当每个 orientation 有很多 path 时，更小步长仍可能增加大量工作。

### `--final-longitude-step`

- **作用：** 设置 top local keeper 周围最终阶段最细经度间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `0.5`。
- **默认：** final 经度间距 0.5°。
- **何时使用：** 只有需要有依据的最终 center 精度时才改变。
- **关系：** 与 final latitude/gamma step 一起使用，并受请求搜索范围约束。
- **输出影响：** 改变 final candidate、运行时间和可能的所选 longitude。
- **示例：** `--final-longitude-step 0.25`。
- **注意：** 它不改变 map projection 精度或 station 坐标。

### `--final-gamma-step`

- **作用：** 设置 top local keeper 周围最终阶段最细 gamma 间距。
- **是否必需：** 可选。
- **取值：** 浮点度；默认 `0.5`。
- **默认：** final gamma 间距 0.5°。
- **何时使用：** 只有最终 layout orientation 需要更细分辨率时才改动。
- **关系：** 与 final latitude/longitude step 共同使用；gamma 仍为周期性的 canonical orientation。
- **输出影响：** 改变 final 评估、运行时间和可能的所选 gamma/图件。
- **示例：** `--final-gamma-step 0.25`。
- **注意：** 更小步长不是近似模式；它会扩展 exact enumerated final candidate set。

## 5. SPECFEM 资源建议

这些参数在 orientation search 后才运行。它们改变资源标签和生成的 Par_file fragment，不改变
orientation candidate 集或 phase-path 数。`--par-file` 还可通过 ELLIPTICITY 影响地理到
全局坐标的几何转换。

### `--par-file`

- **作用：** 以只读方式读取任意外部 Par_file，作为规划上下文。
- **是否必需：** 可选。
- **取值：** 可读 `KEY = VALUE` 文本文件路径；重复 key 会失败。
- **默认：** 使用内置 planning defaults，provenance 标记为 `builtin_profile`。
- **何时使用：** 资源建议需反映实际 case 的 NEX/NPROC 和 compatibility branch 时使用；独立
  screen 可省略。
- **关系：** 若存在，读取 `ELLIPTICITY`、`NEX_XI`、`NEX_ETA`、`NPROC_XI`、
  `NPROC_ETA`、`SUPPRESS_CRUSTAL_MESH`、`ADD_4TH_DOUBLING`；`--nex`、
  `--available-ranks` 覆盖其 candidate 来源。
- **输出影响：** 记录 Par_file provenance，可改变 ellipticity-aware 几何转换，并改变资源
  建议/fragment compatibility。
- **示例：** `--par-file "$D/Par_file"`。
- **注意：** 它不寻找 SPECFEM checkout、不应用 patch、不修改该文件、不验证 mesh/solver
  readiness，也不使 NEX 控制 orientation runtime。

### `--available-ranks`

- **作用：** 提供 total MPI rank 数，用于枚举兼容的 two-chunk decomposition。
- **是否必需：** 可选。
- **取值：** 逗号分隔正整数，例如 `8,12,128`。
- **默认：** 若 Par_file 有 NPROC，则用 `2*NPROC_XI*NPROC_ETA`；否则用 profile 的
  `2,8,12`。
- **何时使用：** 比较目标机器真正可用的 total rank 数时使用；否则继承已记录上下文。
- **关系：** 与 `--nex`、Par_file compatibility flag、`--max-compute-cost` 组合；它覆盖
  Par_file 的 rank-total 默认来源。
- **输出影响：** 改变 `resource_suggestions` 和 `recommended_Par_file.inc`，绝不改变
  orientation candidate 或 path。
- **示例：** `--available-ranks 64,128`。
- **注意：** 数值是两个 chunk 合计的 total rank，而不是每 chunk rank；数学兼容不等于项目已
  验证。

### `--nex`

- **作用：** 增加一个 `NEX_XI×NEX_ETA` 网格分辨率 candidate，用于资源兼容性建议。
- **是否必需：** 可选且可重复。
- **取值：** `XIxETA` 整数，`x` 大小写均可，例如 `96x96`；多个 candidate 重复写该参数。
- **默认：** 若 Par_file 有 NEX，则用 `NEX_XI,NEX_ETA`；否则 profile 用 `96x96`。
- **何时使用：** 想比较合法网格分辨率且不改变已选 orientation 时使用。
- **关系：** 给出后覆盖默认 NEX 来源；与 `--available-ranks`、Par_file physics flag、
  `--max-compute-cost` 组合。
- **输出影响：** 改变资源建议及可能的 recommended fragment；不改变 source/station/path geometry
  或 orientation search time。
- **示例：** `--nex 96x96 --nex 192x96`。
- **注意：** NEX 不增加 orientation candidate 或 path point；每项必须通过所选 branch 的
  multiple/divisibility 检查。

### `--max-compute-cost`

- **作用：** 用 planner 的 relative lateral-work-per-rank proxy 过滤资源建议。
- **是否必需：** 可选。
- **取值：** 浮点阈值。
- **默认：** 不做 post-search cost filter。
- **何时使用：** 需要隐藏超过明确规划 proxy 阈值的资源组合时使用；不要把它当 runtime 预测。
- **关系：** 在 `--nex`、`--available-ranks` 枚举之后应用；不影响 score weight 或 orientation
  search。
- **输出影响：** 移除部分 resource suggestion，并可能改变写入 `recommended_Par_file.inc` 的
  第一项；全部 geometry 输出不变。
- **示例：** `--max-compute-cost 2304`。
- **注意：** 即使过滤后 suggestion 为空，也不会令 geometry candidate 不可行，更不预测 wall
  time 或 memory。

## 6. 输出、绘图与高级行为

### `--output`

- **作用：** 指定接收 planner 产物的新目录。
- **是否必需：** 必需。
- **取值：** 尚不存在的目录路径。
- **默认：** 无。
- **何时使用：** 每次调用都提供唯一 run directory。
- **关系：** 与所有科学控制独立；只有输入和路径准备成功后才创建目录。
- **输出影响：** 写入 `candidates.json`、`candidates.csv`、`geometry_audit.json`、
  `boundary_time_audit.json`、`run_manifest.json`、`recommended_Par_file.inc`、`report.md`、
  `map.png`、`globe.png`。
- **示例：** `--output plans/event1_phase_aware`。
- **注意：** 已存在目录会被刻意拒绝，不会覆盖。planner 没有 `--plot`、`--no-plot`、`--log`
  或公开 diagnostic 参数；需要日志时从外部捕获 stdout/stderr。

## 常见错误与排查

- **“CMTSOLUTION or --source … is required” 或 station-form error：** source 与 station
  各给一种且只给一种。
- **“provide phases, analysis window, or target energy end time”：** geometry-only screen 加
  analysis window，或使用 phase-aware 参数。
- **TauP 找不到 Sdiff：** 先检查 source–station distance 与 model/phase 的适用性。只有接受
  省略该 pair 时才用 partial；输出仍会明确标它为 missing。
- **没有可行 candidate：** 查看 `candidates.json` 的 rejection summary 和
  `geometry_audit.json`；不能改 chunk size，因为它固定。应复核有科学依据的 range、target
  constraint、station coverage 和 phase availability。
- **运行异常长：** 先检查 search range/coarse step、station 数、返回 phase path、path point
  数和 target sampling。改变 NEX/NPROC 不会降低 orientation-search 工作量。
- **boundary-time 看起来安全：** 它只是标为 `heuristic_not_conservative` 的地表弧长 proxy；
  实际边界仍必须在独立 SPECFEM workflow 中验证。

## 限制

planner 仅支持 canonical 90°×90° two-chunk geometry，不能替代生产级 mesh、topology、
boundary-return、solver 或 waveform validation。另见[英文用户指南](user_guide_en.md)、
[中文用户指南](user_guide_zh.md)和[验证状态](validation_status.md)。
