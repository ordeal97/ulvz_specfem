# Two-chunk waveform-symmetry closure — 2026-07-16

本闭环证据根为 `results/two_chunk_waveform_symmetry_closure_20260716T144230Z/`。
旧的 `two_chunk_causal_waveform_acceptance_20260716T124432Z` 保持不变；本轮没有
修改 formal source、formal build rules，也没有 commit 或 push。

## v2 审计与根因

v2 的 C1/C2 Cartesian 坐标映射在 solver-real (float32) 精度下为零残差，矩张量
满足 `M2 = S M1 S^T`。其 ENZ 变换是各台站不同的 E/N 混合；旧比较器已按矩阵投影，
没有时间平移、台站配对或 source-tensor 规则错误。

源到最近台站约为 7°；即使采用 15 km/s 的保守最高速度，最早直达波也在约 52 s 后。
固定 `[0,25] s` 窗口因此主要比较前到时低能量段，不是严格波形对称性的有效 fixture
window。v2 最大 NRMS 为 `5.6058557e-5`（C1S02/N），最大能量差为 `5.0158978e-5`
（C1S01/N）；全部到时差为零。结论：v2 失败由 fixture/window 设计阻断，而不是
two-chunk 实现不对称；旧证据未被重写。

## v3 canonical fixture and runtime gates

v3 使用既有符号精确 90° 变换：`S=diag(1,-1,1)`、`(lat,lon)->(lat,-lon)`、
ENZ `E->-E, N->N, Z->Z`。C1/C2 source tensor 按 `M2=S M1 S^T` 转换；本例的
各向同性源不变。

为保证 fixed pre-return window 含真实到时，台站距 source 0.6–0.85°，且距接口和
外侧面至少 20°。C1/C2 独立网格化；NEX=96、模型、材料、采样和数值设置相同。冻结
比较窗为 `[0,13] s`，记录长度 13.6 s，外边界最早返回保守下界 272.9 s。无互相关
平移、插值或后验优化。

| ranks | max NRMS | max relative energy difference | symmetry | decomposition vs 2 |
| --- | ---: | ---: | --- | --- |
| 2 | 1.371e-6 | 1.405e-6 | pass | baseline |
| 8 | 2.917e-6 | 2.865e-6 | pass | pass |
| 12 | 1.329e-6 | 1.426e-6 | pass | pass |

所有轨迹无 NaN/Inf、无到时偏移并通过 1e-5 阈值。C1 的 2/8/12 physical mesh
fingerprint 相同：`6121369b52d245bd9f69fb8a213506cbbd13fb8c26e90fb59a830a82e6a56976`。

fresh one-chunk clean/reversed 与 patched sibling 的网格和波形完全一致。既有
six-chunk baseline 的 source manifest 与 current patched 不同，故已重跑；三个 trace
相对 L2 误差均为零。

## Decision

拓扑因果、canonical waveform、2/8/12 symmetry、one-chunk 和 six-chunk gate 均通过。
current patch 对当前版本正式接受，canonical 90° fixture ready。一般 two-chunk mode
仍仅为 **B**；Kim/Song Hawaiʻi production 仍因作者输入缺失而不可重建或生产。
