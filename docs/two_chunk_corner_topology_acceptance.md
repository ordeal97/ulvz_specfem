# Two-chunk corner topology acceptance — 2026-07-16

本轮新增证据位于
`results/two_chunk_corner_topology_acceptance_20260716T113245Z/`。正式源码、正式构建规则和既有结果均未修改。

## 新的、受控的拓扑证据

以正式 patched mesher 新生成了 canonical 90°、`NPROC_XI=2`、`NPROC_ETA=3`（12 ranks）数据库。该网格必须把 `NEX_XI=NEX_ETA` 提升到 96，因此它是额外所有权/通信拓扑验证，不能与既有 32-element 2/8-rank fixture 声称严格物理网格不变性。

新的 face-role-aware classifier 用 `solver_data_mpi.bin` 的通信条目、`solver_data.bin` 的 `ispec/i/j/k -> ibool` 反查和 `stacey.bin` 的 face `ijk` 记录关联。它把每个 rank-local `ibool` 明确标为本地身份；跨 rank identity 使用 region 和 solver-precision 坐标的独立审计键，未把不同 rank 的 ibool 编号误称为 SPECFEM 全局编号。

| 配置 | C1 owners | C2 owners | 三径向组 reciprocal | 内部 AB–AC Stacey face |
| --- | --- | --- | --- | --- |
| 2×2/chunk 既有数据库重解析 | 0, 5 | 2, 7 | 是 | 0 条 |
| 2×3/chunk 新建数据库 | 0, 7 | 4, 11 | 是 | 0 条 |

两个端点在 shallow、mid-mantle 和 CMB-near 深度组均有节点 occurrence；每组的 reciprocal communication entry 成立。`0↔7` 与 `2↔5` 在 2×2/chunk 的小数量通信条目仍被保留为实际 endpoint/corner connectivity，而不是按数字标签删除。它们必须由完整 face/edge 角色判断，而非被错误地视为一般对角错误。

Stacey 结论也因此收紧：内部 AB–AC **face** 没有 Stacey 条件。端点处仍可共享一个具有外侧 Stacey face 的节点；这是外侧 face 与内部 interface 在物理 edge/corner 相交，不是 internal face 被吸收。机器可读 node occurrence 和分类结果见 `07_topology_analysis/`。

## 源码因果状态

`v8.0.0` 的 `create_chunk_buffers.f90` 仍明确将 `NCHUNKS=2` 设为一个 corner，并保留“only assemble one corner”的 TODO。当前补丁将 two-chunk path 改为两个 two-member endpoint corner messages，并以 `NPROC_ETA` 作为 AB–AC face segmentation 方向，同时避免 rank 0 被当作 sentinel。

不过，精确当前 patch 不能无歧义 apply 到 v8.0.0（见 `02_source_diffs/v8_exact_patch_check.stderr`）；依据约束，没有创建伪装为 exact patch 的 v8 variant。隔离的 current-reversed 配置超过本轮 120 秒命令时限前未完成 configure，因此没有新的 clean-v8/current-reversed runtime 因果复现。故当前证据支持该 patch 的静态机制和 patched topology，但**尚不足以宣称 runtime causal correction 已完全证明或 patch 已被正式接受**。

## 分类

- `current_formal_patched` 的 canonical topology：B（两个端点 topology 和 Stacey face-role 通过）。
- 一般 two-chunk mode：B；只对 90° canonical path 有新 topology 证据。
- canonical production readiness：未提升。仍缺 clean/current-reversed 的受控 runtime 因果对照及新的 C1/C2 对称波形。
- 没有发现新的 C 类 owner、reciprocal、INVALID_RANK 或 internal-Stacey-face 错误。

此前 `two_chunk_runtime_acceptance.md` 的 2/8-rank waveform 与 six-chunk 结果仍是历史证据，未被本报告替代。

## Current-version isolated causality update — 2026-07-16

新的隔离证据根为
`results/two_chunk_causal_waveform_acceptance_20260716T124432Z/`。它保留
先前中断的 `20260716T121714Z` 为非证据 setup，并分别构建了 current
patched、current reversed 和 clean v8.0.0；正式源码和正式构建规则未改动。

在实际旋转的 canonical 90°、NEX=96 网格中，patched 2/8/12-rank 的物理
网格指纹完全相同。DEBUG corner messages 分别是：2 rank 的两个
`(0,1,-1)`，8 rank 的 `(0,5,-1)`/`(2,7,-1)`，12 rank 的
`(0,7,-1)`/`(4,11,-1)`。12-rank 数据库解析确认 C1/C2 在浅部、中幔和
CMB-near 都为 reciprocal two-member 路径，且 internal AB--AC Stacey face
为零。

受控 reversed 和 clean v8.0.0 的 2-rank 运行均重现单一 `(0,1,0)`
three-member/rank-zero historical path；它没有 C1 eta-min two-member path。
因此 `v8_historical_runtime_failure_reproduced=true`，并停止 reversed 的长
波形。

但 canonical C1/C2 波形的固定 0--25 s 窗口尚未通过 1e-5 阈值。把输入
坐标从 4 位提高到 8 位后，最大 NRMS 仍为 `5.605855680791527e-05`，最大
能量差为 `5.015897846986051e-05`（到时无 shift）。该模式与一般 Euler 反射
下的台站单精度坐标读入一致，但尚未独立隔离根因；它不是 corner 通信回归的
证据，仍足以阻止当时的正式接受。故当时状态是：

- `patched_corner_topology_ready=true`
- `current_patch_runtime_causality_demonstrated=false`
- `patch_formally_accepted_for_current_version=false`
- `canonical_90deg_fixture_ready=false`
- 一般 two-chunk mode 仍为 B

完整 acceptance matrix 和未运行的一/六 chunk 门见该结果根的
`14_reports/acceptance_matrix.json`。

## Waveform closure update — 2026-07-16

后续 `results/two_chunk_waveform_symmetry_closure_20260716T144230Z/` 完成 v2
window 审计、符号精确 v3 2/8/12-rank waveform gate、one-chunk clean/patched 和
six-chunk regression。以该闭环为当前状态：
`current_patch_runtime_causality_demonstrated=true`、
`patch_formally_accepted_for_current_version=true`、
`canonical_90deg_fixture_ready=true`。拓扑一般分类仍为 B。
