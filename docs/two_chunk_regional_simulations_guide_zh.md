# Two-chunk 区域模拟 — ULVZ 项目使用手册

> **操作权威顺序。** 本手册说明的是当前 SPECFEM3D_GLOBE 源码上的项目本地、
> 已验收扩展，不是上游 SPECFEM3D_GLOBE 的通用承诺。表述冲突时，运行操作以
> 当前源码和已验证项目几何测试为准；官方手册只说明其官方行为；Song/Kim
> 材料只保留为科学来源。

**已验证范围：** NCHUNKS=2；两个相邻的 90° cubed-sphere chunks；chunk 1 为
central chunk；chunk 2 连接于受支持的 left side；整体由 central coordinates 与
GAMMA_ROTATION_AZIMUTH 定位/定向；accepted patch 已应用。canonical topology、
Stacey face role、波形对称/分解不变性以及 one-/six-chunk regression 已在 2、8、
12 MPI ranks 通过。canonical_90deg_fixture_ready=true；
general_two_chunk_mode_classification=B。

**尚未建立：** 非 90° 角宽、不同角宽、其他 attachment side、非相邻 chunk、
独立定向、任意 two-chunk topology，以及 three-/general multi-chunk 配置。

<!-- guide-section:1 -->
## 1. 简介

区域模拟把计算限制在选定 cubed-sphere chunk 内，通常在外边界使用 absorbing
boundary。one-chunk 是上游手册的区域路径；six-chunk 是全球 cubed sphere。本项目
已验证的 two-chunk 模式是特定的双面区域域：当目标 source--receiver geometry
放不进一个 90° 面、但仍位于两个相邻面内时适用。它不是任意形状的区域网格。

项目 patch 修正 AB--AC interface 的两个 endpoint：历史上 eta-min 的 C1 缺失，
eta-max 的 C2 则走了错误的 three-member/rank-zero BC path。accepted change 建立
reciprocal two-member endpoint communication，用 INVALID_RANK 保护未使用成员，
并以 NPROC_ETA 分割 xi-constant interface。（Patch：
patches/specfem3d_globe/two_chunk_endpoints/；源码：
src/meshfem3D/create_chunk_buffers.f90。）

上游第 5 章解释区域模拟概念，但不构成当前官方 two-chunk 支持。（官方来源：
specfem3d_globe/doc/USER_MANUAL/05_regional_simulations.tex。）

<!-- guide-section:2 -->
## 2. 双 chunk 几何

![Canonical two-chunk 示意图](assets/two_chunk_canonical_geometry.svg)

Chunk 1 是 central AB face。Chunk 2 是受支持的 left-attached AC face。两者共同的
AB--AC face 是 internal interface；C1、C2 分别是其 physical eta-min、eta-max
endpoint。每个 chunk 有自己的 local xi/eta。canonical geometry 中，interface 在
chunk 1 是 xi-min、在 chunk 2 是 xi-max，沿 eta 分段，因此 patch 依赖
NPROC_ETA。

其余横向 face 都是 external boundary。endpoint 可以与带 external Stacey face 的
node 共用，但这不表示内部 AB--AC face 被吸收：condition 的角色属于 face，而不是
只属于 node。拓扑审计在 shallow、mid-mantle、CMB-near group 均发现 internal
AB--AC Stacey face 为零。（项目证据：
docs/two_chunk_corner_topology_acceptance.md。）

90° 限制是操作限制。当前源码在 NCHUNKS>1 且
ANGULAR_WIDTH_XI_IN_DEGREES 非 90 时停止；只在多于 two chunks 时强制 eta=90。
这一源码宽松性**不会**扩大本项目已验收范围：这里两个角宽必须都是 90°。（来源：
src/shared/read_compute_parameters.f90。）

<!-- guide-section:3 -->
## 3. 坐标系统与旋转

CENTER_LATITUDE_IN_DEGREES、CENTER_LONGITUDE_IN_DEGREES 定位 chunk 1。
GAMMA_ROTATION_AZIMUTH 围绕该 central placement 旋转完整 two-chunk system；
chunk 2 没有独立 orientation。官方 regional manual 将 gamma 描述为绕 chunk
center、从正北逆时针量起的角度。当前 Euler 源码在 ELLIPTICITY=.true. 时将中心
转为 geocentric colatitude，再建立 rotation matrix。（来源：
05_regional_simulations.tex；src/shared/euler_angles.f90。）

对一个 geographic point，审计工具先形成 Cartesian unit vector，施加转置 Euler
matrix，再使用当前 chunk_map：chunk 1 使用 xi=atan(y/z)、eta=atan(-x/z)，且 z
为正；chunk 2 使用 xi=atan(-z/y)、eta=atan(x/y)，且 y 为负。有效 local
coordinate 位于 angular half-width 内。（来源：
src/auxiliaries/write_profile.f90 的 get_latlon_chunk_location、chunk_map。）

1. gamma 为零时，系统保持给定中心处的 reference orientation。
2. 改变 gamma 会整体移动两个 chunk，不会单独旋转 chunk 2。
3. 通过改变 center/gamma 可以整体移动 source--station geometry；meshing 前必须
   再次审计每一个 point。

使用 cases/two_chunk_canonical_90deg/audit_geometry.py 做 pre-mesh 检查。它输出
membership 及到 interface、C1/C2、outer face 的 angular margin。它只适用于
canonical teaching case 的前置审计，不能替代 mesher location output。

<!-- guide-section:4 -->
## 4. 必需补丁

项目本地 package 位于 patches/specfem3d_globe/two_chunk_endpoints/。其中 JSON
manifest 是唯一 hash authority。对于 nested revision
9c312cb2c991b47484a7f302775f4f01ed9470f8，baseline target hash 是
fd4137713e55e14ec664a9d55487b64c2b9bf73499c1f82780f1f5a6e63b088f；应用后
create_chunk_buffers.f90 必须是
8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857。Patch file
hash 是 4496cea542d26f38575ec1fa9ae28635ec2a201958eb898702331c7db5fe4a60。

~~~bash
PATCH=patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch
patches/specfem3d_globe/two_chunk_endpoints/verify_patch.sh specfem3d_globe
git -C specfem3d_globe apply --check "$PATCH"
git -C specfem3d_globe apply "$PATCH"
sha256sum specfem3d_globe/src/meshfem3D/create_chunk_buffers.f90
git -C specfem3d_globe apply --reverse --check "$PATCH"
git -C specfem3d_globe apply --reverse "$PATCH"
~~~

hash 或 context 不匹配时必须停止；任一 source transition 后都要从 clean objects
重建。该 patch 对 clean v8.0.0 不能 clean apply（6/10 hunks failed），也未提供
backport。（权威：patch manifest；操作说明：
docs/two_chunk_project_patch.md。）

<!-- guide-section:5 -->
## 5. Par_file 设置

只使用当前 specfem3d_globe/DATA/Par_file 中的精确名称。教学案例的完整 current
template copy 位于 cases/two_chunk_canonical_90deg/DATA/Par_file。

| 参数 | 作用、约束和检查 |
| --- | --- |
| NCHUNKS | 设置为 2。确认 audit 输出 total_mpi_ranks=8。 |
| ANGULAR_WIDTH_XI_IN_DEGREES, ANGULAR_WIDTH_ETA_IN_DEGREES | 都设置 90.d0。不要从 exactly-two-chunk 的较宽松 eta 源码检查推断支持。 |
| CENTER_LATITUDE_IN_DEGREES, CENTER_LONGITUDE_IN_DEGREES, GAMMA_ROTATION_AZIMUTH | 定位/定向完整系统；每次改动均重新 audit。 |
| NEX_XI, NEX_ETA | central chunk 每方向的 surface elements。canonical validated 值为 96；当前 template 要求 16 的倍数且为相关 process count 的 8 倍。 |
| NPROC_XI, NPROC_ETA | 每 chunk 分解；total=NCHUNKS*NPROC_XI*NPROC_ETA。validated 1x1/chunk=2、2x2/chunk=8、2x3/chunk=12；教学案例为 2x2/chunk。 |
| MODEL, OCEANS, ELLIPTICITY, TOPOGRAPHY, GRAVITY, ROTATION, ATTENUATION | 有意识选择物理项。教学 fixture 使用 1D_isotropic_prem 且所列开关均为 false；这不是科学模型处方。 |
| RECORD_LENGTH_IN_MINUTES, NTSTEP_BETWEEN_OUTPUT_SEISMOS, NTSTEP_BETWEEN_OUTPUT_SAMPLE | 设置长度/采样；比较窗必须早于最早 external return。 |
| ABSORBING_CONDITIONS, ABSORB_USING_GLOBAL_SPONGE | Fixture 使用 Stacey absorption。Global sponge 只允许 NCHUNKS=6；绝不适用于 internal AB--AC。 |
| REGIONAL_MESH_CUTOFF, REGIONAL_MESH_CUTOFF_DEPTH, REGIONAL_MESH_ADD_2ND_DOUBLING | 可选 radial cutoff/doubling；修改前保留 current template 的允许深度值。 |
| LOCAL_PATH, LOCAL_TMP_PATH, SAVE_MESH_FILES, OUTPUT_SEISMOS_* | database、mesh diagnostic、waveform output 控制；事先规划新 run storage。 |

NEX 必须与 decomposition 兼容，因为源码会依 mesh/doubling configuration 走不同
divisibility branch。NEX=96 兼容每 chunk 1x1、2x2、2x3。不可降低它后仍声称
同等 waveform accuracy。（来源：DATA/Par_file；
src/shared/read_compute_parameters.f90。）

<!-- guide-section:6 -->
## 6. 网格分辨率

NEX_XI/NEX_ETA 控制 lateral spectral-element count；每个 element 使用 GLL point。
Radial layer、doubling/coarsening 依 model 与 regional cutoff 而定，因此 lateral NEX
不是完整 resolution 信息。增加 chunks/NEX 会增加 mesh/database cost；增加 ranks
会重新分配工作并增加 communication。

先确定 target period、model complexity、source time function、output cadence；再检查
Jacobian、实际 timestep/CFL output 与 target waveform。官方 manual 的 regional
resolution discussion 只能作为 estimate，不是 universal accuracy formula。Canonical
NEX=96 只验证了本 patch fixture。（来源：05_regional_simulations.tex；
docs/two_chunk_waveform_symmetry_closure.md。）

<!-- guide-section:7 -->
## 7. 震源放置

CMTSOLUTION 是 PDE header，随后是 event name、time shift、half duration、
latitude、longitude、depth、Mrr Mtt Mpp Mrt Mrp Mtp。当前 get_cmt.f90 读取这些
labels；示例坐标为 geographic degree、depth 为 km。（来源：
specfem3d_globe/DATA/CMTSOLUTION；src/specfem3D/get_cmt.f90。）

工作流：定义 event；绘制/audit boundary；判定所属 chunk；检查 interface、C1/C2、
external margin；检查 depth 与 model/radial layer；生成并 audit CMTSOLUTION。
source 可在任意一个 chunk。Internal interface 不是 physical boundary，但敏感模拟
应避免 source 精确落在 interface/corner/element face/edge。需在 output 中确认
requested 与 located source。

<!-- guide-section:8 -->
## 8. 台站放置

每一条非注释 STATIONS record 格式为 station network latitude longitude elevation
burial；坐标为 degree，elevation/burial 为 metre。reader 检查 latitude，并对重复
network/station pair 改名。（来源：specfem3d_globe/DATA/STATIONS；
src/specfem3D/locate_receivers.f90。）

审计每个 station 的 membership、duplicate、outer margin。Station 可以跨 internal
interface，但敏感比较应避免精确位于 interface/endpoint/element。建议绘制 source、
stations、chunk outline、C1/C2、great-circle path、classification 与 outer margin。

不能规定固定 angular safety distance。应估计 target arrival 与 earliest external-boundary
return，选择包含 target phase 且早于 return 的窗口；必要时增大 margin 或缩短 window。
更多 station 增加 output/storage。meshing 后检查 receiver list，因为当前代码可能
排除域外 receiver。

<!-- guide-section:9 -->
## 9. 完整流程

1. 验证/应用 patch 与 candidate hash。
2. 用 current-template Par_file 设置 canonical two-chunk 值。
3. 准备/audit CMTSOLUTION、STATIONS。
4. 检查 total rank 与 NEX compatibility。
5. 运行 xmeshfem3D；检查 mesh、Jacobian。
6. 按当前 executable workflow 创建/读取 database。
7. Patch validation 时检查 C1/C2 reciprocity 与 internal AB--AC Stacey face=0。
8. 运行 xspecfem3D；检查 finite output、physical arrival。
9. 复现 patch 时先用 accepted 2-rank diagnostic，再用 canonical 8/12-rank decomposition。
10. 比较 fingerprint/trace，不做 post-hoc time shift。

~~~bash
bash cases/two_chunk_canonical_90deg/run_canonical.sh \
  --specfem-root specfem3d_globe \
  --run-dir results/two_chunk_canonical_run_<UTC> --dry-run
~~~

<!-- guide-section:10 -->
## 10. 验收清单

- [ ] Patch manifest、source hash、apply check 一致。
- [ ] 两个角宽均为 90；chunk 1 central、chunk 2 left-attached。
- [ ] Total rank 与 NEX compatibility 正确。
- [ ] source/station 在 pre-mesh audit 中均 in-domain。
- [ ] 有记录的 travel-time assessment 覆盖 window 与 return risk。
- [ ] Mesher 报告预期 mesh、可接受 Jacobian。
- [ ] C1/C2 是 reciprocal two-member path；internal AB--AC Stacey face=0。
- [ ] 比较 canonical fixture run 时 2/8/12 fingerprint 一致。
- [ ] Trace finite、含 physical signal、无 endpoint anomaly。
- [ ] Window 包含 arrival；不可重复无效的 pre-arrival v2 [0,25] s。

Accepted v3 使用 [0,13] s、close receiver，且 conservative outer-return lower bound
为 272.9 s。这是 fixture evidence，不是 universal window。（证据：
docs/two_chunk_waveform_symmetry_closure.md。）

<!-- guide-section:11 -->
## 11. 故障排查

| 症状 | 可能原因 | 检查 | 处理 |
| --- | --- | --- | --- |
| Mesher 停止 | 参数/geometry 无效 | Stop text；audit | 改正 current-template value。 |
| Rank 数错误 | per-chunk/total 混淆 | 2*NPROC_XI*NPROC_ETA | 用该数量启动。 |
| NEX 停止 | decomposition 不兼容 | Source divisibility branch | 选择兼容 NEX/decomposition。 |
| Point 域外 | 不在 two faces | Audit/location output | 移点或整体系统。 |
| Corner/invalid rank | Patch 缺失/拓扑不支持 | Candidate hash；topology report | 停止并验证 canonical context。 |
| Internal Stacey 声称 | node/face 混淆 | Face-role report | 要求 AB--AC face record=0。 |
| Zero trace | receiver/source/input 问题 | Output list/log | 修改 input 后新建 run。 |
| Pre-arrival window | 仅凭方便选择 | Travel-time estimate | 重设 window；不 shift trace。 |
| Rank 不一致 | mesh/settings 不同或 defect | Fingerprint/raw trace | 重现 canonical input；不明原因即停止。 |
| Patch 失败 | Source 已改变 | Manifest/verify script | 不强行应用；重新验证 update。 |

<!-- guide-section:12 -->
## 12. 完整示例

cases/two_chunk_canonical_90deg/ 含完整 teaching fixture：

- DATA/Par_file：NCHUNKS=2、两角宽 90、center (90,90)、gamma=0、NEX=96、
  2x2/chunk、13.6 s；
- DATA/CMTSOLUTION：位于 chunk 1、50 km deep 的 isotropic teaching source；
- DATA/STATIONS：three chunk-1 与 three chunk-2 receiver；
- audit_geometry.py：pre-mesh JSON/CSV/Markdown audit；
- generate_geometry_figure.py：本手册示意图；
- run_canonical.sh：显式 8-rank runner。

先在 results/ 写 audit report，审阅 --dry-run，随后只在新的 run directory 运行。
预期 static result：7 个 in-domain point，source/C1 station 属于 central，C2 station
属于 left-attached，total ranks=8，candidate hash match。它不是 Kim/Song Hawaiʻi
input，也不单独建立 production science readiness。

## 证据与溯源

- Official：specfem3d_globe/doc/USER_MANUAL/05_regional_simulations.tex。
- Current source：DATA/Par_file、read_compute_parameters.f90、euler_angles.f90、
  get_cmt.f90、locate_receivers.f90、create_chunk_buffers.f90。
- Patch/hash authority：patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints_manifest.json。
- Topology：docs/two_chunk_corner_topology_acceptance.md。
- Causal/waveform closure：docs/two_chunk_waveform_symmetry_closure.md 与
  results/two_chunk_waveform_symmetry_closure_20260716T144230Z/07_reports/acceptance_matrix.json。
- Song/Kim 的 production provenance 仍不完整；见
  results/two_chunk_corner_topology_acceptance_20260716T113245Z/11_hawaii_provenance/。
