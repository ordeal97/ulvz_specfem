# Kim/Song paper-constrained Hawaiʻi two-chunk production gate — 2026-07-16

结果目录：`results/two_chunk_corner_topology_acceptance_20260716T113245Z/11_hawaii_provenance/` 和 `12_hawaii_geometry/`。

## Provenance

本 gate 的 provenance class 是 `song_paper_constrained_reconstruction`，不是 `song_original_input`。本地 reference bundle 含 Kim et al. Science Advances 主文和补充材料，且可直接支持：two cubed-sphere chunks、regional edge absorption、TI PREM、每 chunk crust/upper mantle 480 lateral elements、CMB coarsening 至约 120、约 45.6 km spacing、约 6.3 s 最短周期，以及 Fig. S4 的 2012-04-17 Eastern New Guinea Mw 6.9 / 208.6 km reference-event constraint。

Song 的说明还锁定：第一 chunk 为中央 chunk，第二 chunk 在其左侧，两个 chunk 都是 90°，整个系统仅以中央 chunk coordinates 和 `GAMMA_ROTATION_AZIMUTH` 旋转。

本地资料没有 author-provided `Par_file`、`CMTSOLUTION`、`STATIONS`、ULVZ insertion source/config 或 exact central latitude/longitude/gamma。论文/补充材料还不足以从本地记录恢复 event latitude/longitude/moment tensor、station list 或 exact Hawaiʻi ULVZ center。因此 JSON inventory 将它们保留为 null，而非用既有 Yuan/135° proxy 填补。

## Gate decision

| Gate | Status |
| --- | --- |
| reference bundle found | true |
| paper constraints available | true, partial |
| original runtime files found | false |
| numerical reconstruction | false |
| geometry-audit workflow | ready |
| geometry numeric margin audit | partial / not assessed for missing coordinates |
| short numerical gate | blocked missing inputs |
| full Kim/Song Hawaiʻi production | false |

该状态不否定 canonical 90° code-path evidence；它仅表示没有充分证据把本地 fixture 写成 Kim/Song unpublished runtime 的 exact reproduction。生产 gate 需要最少补齐：CMT coordinate/moment tensor、完整 station coordinates、central chunk latitude/longitude/gamma、ULVZ center/shape/code path，并将它们写入可审计 input bundle 后重算 corner/external-boundary/CMB-path margins。
