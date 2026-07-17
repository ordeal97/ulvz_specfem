# Canonical two-chunk 区域模拟 — ULVZ 项目使用手册

> **先读这一页。** 本项目本地手册只覆盖已接受的 canonical 模式：NCHUNKS=2、
> 两个相邻 90°×90° 面、AB 为 central chunk、AC 连到指定局部边、整个系统只有一个
> center/gamma orientation，且已应用 accepted patch。它不是上游
> SPECFEM3D_GLOBE 的通用承诺。canonical_90deg_fixture_ready=true；
> general_two_chunk_mode_classification=B。

> **不得外推。** 非 90° 或不等角宽、其他 attachment side、非相邻面、独立定向、
> 任意 two-chunk topology 和 three-/general multi-chunk 模式均未验证。planner 是
> 只读工具，不替代 mesher、Stacey 或波形验收。Kim/Song 精确复现仍需要作者输入。

<!-- guide-section:1 -->
## 1. 此模式是什么，以及下文术语

区域模拟只计算 cubed sphere 的部分面。one-chunk 是通常 regional case；six-chunk
构成完整球面。本 two-chunk 模式只适用于 source、stations 和目标路径放不进一个
90° 面、但能放进这两个相邻面时；它不是任意形状网格。

| 术语 | 直观含义与位置 | 用户为何需要关心 / 出错现象 |
| --- | --- | --- |
| **AB / AC** | 这里使用的两个 cubed-sphere 面。AB 是 central 的 chunk 1；AC 是 attached 的 chunk 2。 | 它们决定 source/station 所属面；调换它们会改变受支持 topology。 |
| **AB–AC interface** | 公共内部面：AB xi-min 接 AC xi-max。 | 它交换 wavefield，不是外墙，绝不能吸收。 |
| **C1 / C2** | interface 两端：C1 是 eta-min；C2 是 eta-max。eta 是面局部坐标，不是地理南北。 | endpoint 错误会缺失或错误连接 corner data，并可能随 MPI layout 改变。 |
| **MPI rank / rank zero** | rank 是一个 MPI process；rank 0 是有效 process。 | rank 0 不能被当作 unused slot。 |
| **buffer / two-member path** | buffer 在 C1/C2 两侧的两个 ranks 之间传送 endpoint data。 | 此模式每个 endpoint 都必须有恰好两个 reciprocal members。 |
| **three-member / BC path** | 历史通用 corner logic 包含本 two-face domain 不存在的 BC participant。 | 它可能建立 false connection 或隐藏 missing endpoint。 |
| **Stacey face / sponge** | Stacey 在暴露 mesh face 上吸收；global sponge 是 six-chunk global model 的高衰减区域。 | 两者都不能放在 AB–AC。 |

**实现背景。** accepted patch 之前，C1 没有 eta-min two-member record，C2 保留了
BC/rank-zero three-member path。补丁建立两个 endpoint records，只对 unused slots
使用 INVALID_RANK，并以 NPROC_ETA 分割 xi-constant interface。

<!-- guide-section:2 -->
## 2. 几何：局部 attachment 不是地图方向

![Canonical topology and rotation convention](assets/two_chunk_canonical_geometry.svg)

图左是**局部 topology 图**，不是地图。“supported-left”表示 AC 接到 AB 的指定
局部边：AB xi-min 与 AC xi-max 相接。系统经过 center latitude/longitude 和 gamma
整体旋转后，AC 在地图上可出现在西、东、北或南。应说“接到指定局部边”，不要说
“地理上的左侧”。

虚线 AB–AC 是 internal interface。C1 是 eta-min，C2 是 eta-max；其余 lateral
faces 才是 exposed faces。endpoint 可以和 external Stacey face **共用 node**，
但不会使 internal face 吸收：face roles 不同。已接受 topology evidence 在
shallow、mid-mantle 和 CMB-near 都发现 internal AB–AC Stacey face 为零。

当前源码在 NCHUNKS > 1 且 ANGULAR_WIDTH_XI_IN_DEGREES 不为 90 时停止。它只在
exactly two chunks 时允许非 90 eta width，但本项目未验证此情形：两个宽度都设 90。

<!-- guide-section:3 -->
## 3. Center coordinates 与 GAMMA_ROTATION_AZIMUTH

CENTER_LATITUDE_IN_DEGREES 和 CENTER_LONGITUDE_IN_DEGREES 放置 AB 的中心。
GAMMA_ROTATION_AZIMUTH 旋转**完整 AB+AC system**；AC 没有独立 orientation。
官方 regional manual 规定 gamma 从正北逆时针量起；当前 euler_angles.f90 与
project planner 使用同一符号。

**本手册观察视角：** 从地球外部朝 selected center 俯视，tangent plane 中 north 向上、
east 向右。正 gamma 为逆时针。ELLIPTICITY=.false. 且 center=(0°,0°) 时：

| Gamma | +eta | +xi | 含义 |
| ---: | --- | --- | --- |
| 0° | north | east | reference orientation |
| 90° | west | north | 完整系统逆时针旋转 |
| 180° | south | west | 半周旋转 |

启用 ellipticity 时，源码先把 geographic latitude 转为 geocentric colatitude；
gamma 符号不变。每次改变 center/gamma 后必须 audit source 和全部 stations，绝不
单独旋转 AC。

### 输入参数后如何确定 AC 的真实地理位置

AC 没有独立的 latitude、longitude 或 gamma 参数。对 canonical 几何，
`NCHUNKS=2`、两个 90° 宽度、AB 的 center latitude/longitude 和 gamma 四类输入会唯一
确定所有 AB/AC boundary points：SPECFEM 先定义固定的 local AB--AC pair，再对整个 pair
施加同一个 Euler transform。因此 AC 不是用户再单独放置的第二个区域。

对一组已选 center/lon/gamma，用三个相同的搜索上下界运行
`two_chunk_planner plan`。其 `map.png` 显示转换后的 AB/AC outline 和 interface；
`geometry_audit.json` 与 `candidates.json` 给出 source/station 的 chunk label、local
xi/eta、interface、C1/C2 和 exposed-boundary margins。这是判断目标地理区域属于 AB、AC、
shared interface 或 domain 外的实际操作方式。它是 pre-mesh geometry check，不能替代后续
mesh/Stacey/waveform validation。

在 geographic pole，longitude 与 gamma 不是唯一 parameterization。planner 会有意把 polar
center 归一化为 longitude 0°，并调整 gamma 以保持同一个 physical AB+AC orientation。检查
polar case 时应比较图上的 outline，而不只比较打印出的三个数字。

<!-- guide-section:4 -->
## 4. 安全安装 accepted patch

package 位于 patches/specfem3d_globe/two_chunk_endpoints/，其 JSON manifest 是
hash authority。它针对 nested revision
9c312cb2c991b47484a7f302775f4f01ed9470f8 验证。baseline target SHA-256 为
fd4137713e55e14ec664a9d55487b64c2b9bf73499c1f82780f1f5a6e63b088f；应用后 target
SHA-256 必须为
8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857。

### 最少安装步骤

在 project root 执行。hash 或 context 不匹配时必须停止。

~~~bash
PATCH="$(pwd)/patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch"
patches/specfem3d_globe/two_chunk_endpoints/verify_patch.sh specfem3d_globe
git -C specfem3d_globe apply --check $PATCH
git -C specfem3d_globe apply $PATCH
sha256sum specfem3d_globe/src/meshfem3D/create_chunk_buffers.f90
git -C specfem3d_globe apply --reverse --check $PATCH
~~~

verifier 必须报告 baseline hash、single-file scope、无 DEBUG 变化与 clean apply
check。若 target 已是 candidate hash，reverse dry-run 会说明它已应用；不要重复 apply。
要有意识地撤销，执行 git -C specfem3d_globe apply --reverse $PATCH，然后从 clean
objects rebuild。

### 严格可追溯安装与手工替换警告

记录 nested revision、baseline hash、patch SHA-256
4496cea542d26f38575ec1fa9ae28635ec2a201958eb898702331c7db5fe4a60、forward check、
applied hash 与 reverse check。推荐 git apply，因为它检查 context 并保留可审计 diff。
不要把完整 create_chunk_buffers.f90 直接覆盖为正常流程。若站点政策必须手工替换，
先保留原文件、核对 baseline hash、比较 patch diff、核对 candidate hash，并保留测试过
的 restore path。复制一个文件不等于完成 two-chunk runtime acceptance。该 patch 对
v8.0.0 不能 clean apply。

<!-- guide-section:5 -->
## 5. 输入、外部吸收、source 与 stations

从当前 specfem3d_globe/DATA/Par_file 开始；教学副本位于
cases/two_chunk_canonical_90deg/DATA/Par_file。

| 设置 | Canonical two-chunk 指令 |
| --- | --- |
| NCHUNKS | 设为 2。total ranks = 2*NPROC_XI*NPROC_ETA。已接受 fixtures 是 2、8、12 ranks。 |
| ANGULAR_WIDTH_XI_IN_DEGREES, ANGULAR_WIDTH_ETA_IN_DEGREES | 两者均设为 90.d0。 |
| CENTER_LATITUDE_IN_DEGREES, CENTER_LONGITUDE_IN_DEGREES, GAMMA_ROTATION_AZIMUTH | 放置/旋转完整 domain；每次改动都做固定几何的 planner 检查。 |
| NEX_XI, NEX_ETA, NPROC_XI, NPROC_ETA | NEX=96、2×2/chunk 是 accepted teaching fixture，不是通用廉价 production accuracy。保持 source divisibility constraints。 |
| MODEL, OCEANS, ELLIPTICITY, TOPOGRAPHY, GRAVITY, ROTATION, ATTENUATION | 有意识选择 physics；teaching switches 不是科学处方。 |
| RECORD_LENGTH_IN_MINUTES, NTSTEP_BETWEEN_OUTPUT_SEISMOS, NTSTEP_BETWEEN_OUTPUT_SAMPLE | 按 target signal 和已记录 external-return assessment 选择长度/cadence。 |
| ABSORBING_CONDITIONS | canonical two chunks 设 .true.；mesher 只为 exposed faces 建立 Stacey arrays。 |
| ABSORB_USING_GLOBAL_SPONGE, SPONGE_LATITUDE_IN_DEGREES, SPONGE_LONGITUDE_IN_DEGREES, SPONGE_RADIUS_IN_DEGREES | sponge flag 设 .false.；当前源码在 NCHUNKS=2 时会停止。 |
| REGIONAL_MESH_CUTOFF, REGIONAL_MESH_CUTOFF_DEPTH, REGIONAL_MESH_ADD_2ND_DOUBLING | 可选 radial controls；保持当前 template 的允许值并重查 mesh/Jacobians。 |
| LOCAL_PATH, LOCAL_TMP_PATH, SAVE_MESH_FILES, OUTPUT_SEISMOS_* | 预先规划 new-run database、diagnostic 和 waveform storage。 |

### Two chunks 实际采用什么吸收

Global sponge 是 six-chunk global-model option。read_parameter_file.F90 只在 flag 为真
时读取 SPONGE_*；read_compute_parameters.f90 会停止任何 non-six-chunk request，报错为
“Please set NCHUNKS to 6 in Par_file to use ABSORB_USING_GLOBAL_SPONGE”。其 Qmu 修改
经 ATTENUATION model path 到达，不是 local side-face condition。

NCHUNKS=2 时，create_regions_mesh.F90 在 ABSORBING_CONDITIONS=.true. 时调用 Stacey
setup。get_absorb.f90 纳入 AC xi-min、AB xi-max 和 exposed eta faces；它排除 AB xi-min
和 AC xi-max，即 shared interface。radial bottom face 只在 source logic 需要时加入
（outer core 或 regional cut-off）。因此 **AB–AC 永远不是 sponge、Stacey 或其他
absorbing face**。若结果声称相反，必须停止并做 face-role audit。
准确的 parameter guards 与调用路径见
[吸收边界源码审计](two_chunk_absorbing_boundary_audit.md)。

CMTSOLUTION 包含 PDE、event name、time shift、half duration、latitude、longitude、
depth 和 Mrr Mtt Mpp Mrt Mrp Mtp。STATIONS record 是 station network latitude
longitude elevation burial。source/stations 可在任一面，但不要精确放在 interface、
endpoint、element face/edge 或 exterior face。不能规定固定 angular safety distance；
应估计 target arrival 与 earliest external return。

<!-- guide-section:6 -->
## 6. 自定义模拟流程与教学 fixture

不要混合以下两条流程。第一条针对**用户自己准备的 input**；第二条只检查或运行项目固定的
teaching case。两者都不等于 formal patch acceptance。任何会写文件的命令都使用新的
output directory。

### A. 规划并运行自己的 canonical configuration

1. 检查 source 与 patch（第 4 节）。准备自己的 `DATA/Par_file`、`CMTSOLUTION`、
   `STATIONS`；设置两个 90° widths、`ABSORBING_CONDITIONS=.true.` 和
   `ABSORB_USING_GLOBAL_SPONGE=.false.`。
2. 若还未选定 geometry，先参照 package planner guide 做有界的 center/lon/gamma search。
   选定 candidate 后，用以下固定范围命令显示并分类该**精确** geometry。替换所有需要替换的
   值；output directory 必须不存在。

~~~bash
export ULVZ_PYTHON=/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python
SPECFEM_ROOT="$(pwd)/specfem3d_globe"
INPUT_DATA="/absolute/path/to/YOUR_CASE/DATA"
CENTER_LAT=20.0
CENTER_LON=160.0
GAMMA=30.0
ANALYSIS_END_S=1900
PLAN_DIR="results/two_chunk_geometry_$(date -u +%Y%m%dT%H%M%SZ)"
PYTHONPATH=packages/two_chunk_planner/src $ULVZ_PYTHON -m two_chunk_planner plan \
  --cmtsolution "$INPUT_DATA/CMTSOLUTION" --stations "$INPUT_DATA/STATIONS" \
  --par-file "$INPUT_DATA/Par_file" --target-energy-end-s "$ANALYSIS_END_S" \
  --latitude-range "$CENTER_LAT,$CENTER_LAT" --longitude-range "$CENTER_LON,$CENTER_LON" \
  --gamma-range "$GAMMA,$GAMMA" --output "$PLAN_DIR"
~~~

3. 打开 `PLAN_DIR/map.png` 查看真实地理 AB/AC boundaries。继续前先读取 chosen candidate
   的 point classifications。若没有 feasible candidate，或任一 required point 在 domain 外/
   endpoint/external boundary 上，必须停止并修改 geometry。review—not blindly copy—
   `recommended_Par_file.inc`，再把其中 center/lon/gamma 和经过有意识选择的 mesh settings
   转写到自己的 `Par_file`。
4. 仅在上述 review 后运行自己的 input。`NPROCS=8` 是经过验证的 2×2-per-chunk example；
   只有选择 compatible layout 时才改变它。

~~~bash
NPROCS=8
SPECFEM_ROOT="$(pwd)/specfem3d_globe"
INPUT_DATA="/absolute/path/to/YOUR_CASE/DATA"
RUN_DIR="results/my_two_chunk_run_$(date -u +%Y%m%dT%H%M%SZ)"
test ! -e "$RUN_DIR" || { echo "refusing to overwrite $RUN_DIR" >&2; exit 2; }
mkdir -p "$RUN_DIR/DATA" "$RUN_DIR/DATABASES_MPI" "$RUN_DIR/OUTPUT_FILES"
cp -R "$INPUT_DATA/." "$RUN_DIR/DATA/"
(cd "$RUN_DIR" && mpirun -np "$NPROCS" "$SPECFEM_ROOT/bin/xmeshfem3D")
(cd "$RUN_DIR" && mpirun -np "$NPROCS" "$SPECFEM_ROOT/bin/xspecfem3D")
~~~

`xmeshfem3D` 产生 mesh 与 `DATABASES_MPI`；`xspecfem3D` 读取这些 databases。本 source tree
没有独立的 `xgenerate_databases` 命令。

### B. 检查或运行固定教学 fixture

`audit_geometry.py` 被有意限制为 `cases/two_chunk_canonical_90deg/DATA`
（center 90°、longitude 90°、gamma 0°）。`run_canonical.sh` 复制相同的 teaching `DATA`；
它不是 reviewer，不能用于启动用户自己的 inputs。其 dry-run 只预览 teaching fixture 的命令。

~~~bash
SPECFEM_ROOT="$(pwd)/specfem3d_globe"
$ULVZ_PYTHON cases/two_chunk_canonical_90deg/audit_geometry.py --validate-only --specfem-root "$SPECFEM_ROOT"
bash cases/two_chunk_canonical_90deg/run_canonical.sh --specfem-root "$SPECFEM_ROOT" \
  --run-dir "results/two_chunk_canonical_run_$(date -u +%Y%m%dT%H%M%SZ)" --dry-run
~~~

预期结果：teaching audit 输出 status pass 和 total MPI ranks 8；其 dry-run 打印 8-rank
`xmeshfem3D`，随后是 `xspecfem3D` 命令，但不会建立 run directory。只有要复现该 teaching
fixture 时才去掉 `--dry-run`，不能用它运行 custom study。

<!-- guide-section:7 -->
## 7. 完整 production 或 release acceptance

这些检查不要混入第一次 smoke run。

![User workflow and stop conditions](assets/two_chunk_user_workflow.svg)

图中的 pre-mesh step 指第 6A 节 custom input 的 planner workflow。第 6B 节的 teaching
audit 与 teaching runner 是独立的 fixture tools。

| 层级 | 必需 evidence | 停止条件 |
| --- | --- | --- |
| 必须 | Patch context；canonical widths；in-domain points；finite mesher/solver output | mismatch、非 90° geometry、outside point 或 mesher failure |
| changed patch/source | C1/C2 reciprocal two-member paths；无 INVALID_RANK member；internal AB–AC Stacey=0 | missing endpoint、BC/three-member path 或 internal absorbing face |
| decomposition claim | 等价 2/8/12 physical fingerprints、connectivity、materials、buffers、face roles | 不能解释的 rank difference |
| waveform claim | valid fixed physical window；无 shift；无 NaN/Inf；NRMS 和 relative energy <=1e-5 | endpoint anomaly、invalid window、arrival shift、threshold failure |
| 推荐 science | target-arrival/external-return assessment；margins/path coverage | boundary contamination risk |
| developer evidence | one-/six-chunk regression 与 controlled reversed reproduction | 无此证据不可作 broad causal claim |

accepted v3 在 2/8/12 ranks 的 max NRMS 是 2.92e-6、relative energy difference 是
2.86e-6。早期 v2 [0,25] s window 在约 52 s 的 first arrival 之前；它无效，不是
放宽 gates 的理由。

<!-- guide-section:8 -->
## 8. Resolution 与 MPI 选择

NEX_XI/NEX_ETA 是 lateral spectral-element counts；GLL points 位于 elements 内。
radial layers/doubling、model complexity、source bandwidth、timestep 和 output cadence
也影响成本与 accuracy。NEX=96 是 accepted canonical geometry fixture，不能自动称为
low-cost smoke mesh 或 production prescription。

每个 chunk 的 decomposition 是 NPROC_XI × NPROC_ETA；total ranks 是
2*NPROC_XI*NPROC_ETA。accepted fixtures 为 1×1/chunk=2、2×2/chunk=8、
2×3/chunk=12。其他 compatible layouts 未经 project validation。若 mesher 停止，
选择 compatible NEX/ranks，绝不绕过 source checks。

<!-- guide-section:9 -->
## 9. 每个 audit 实际检查什么

| Tool 或 record | 输入 | 输出 / pass 含义 | 它不证明什么 |
| --- | --- | --- | --- |
| verify_patch.sh | worktree 与 patch | source SHA、one-file scope、无 DEBUG、clean apply context | topology 或 waveform |
| audit_geometry.py | 仅 fixed teaching `DATA/` | static teaching-fixture input/hash/membership check | arbitrary user center/gamma、databases、Jacobians、Stacey、waveforms |
| two_chunk_planner plan | 用户 source/stations、candidate geometry 与可选 path/window | deterministic center/gamma candidates；真实 AB/AC map 与 point classification | mesher、solver 或 production-safe return time |
| stacey.bin analysis | generated databases | face roles；internal AB–AC count 必须为零 | science window |
| acceptance reports | controlled diagnostic runs | ownership、reciprocity、fingerprints、fixed-window metrics | general two-chunk support |

项目没有一个“运行 audit tool”就能检查所有层次；顺序应为 source integrity → geometry
→ mesh/database face roles → solver/waveforms。

<!-- guide-section:10 -->
## 10. 一页式 checklist

- [ ] Patch hash/context 与 git apply --check 一致。
- [ ] NCHUNKS=2；两个 widths=90；AB central，AC 接到指定 local edge。
- [ ] ABSORBING_CONDITIONS=.true.；ABSORB_USING_GLOBAL_SPONGE=.false.。
- [ ] total ranks = 2*NPROC_XI*NPROC_ETA；NEX compatible。
- [ ] source/stations in-domain，且不精确位于 interface/C1/C2/faces。
- [ ] window 含 target arrival 并记录 return risk；它不是 universal window。
- [ ] mesher 完成且 dimensions/Jacobians 可接受。
- [ ] new DATABASES_MPI/stacey.bin 存在；required face-role audit 的 internal AB–AC Stacey=0。
- [ ] solver traces finite 且有 physical signal。
- [ ] 任何 symmetry claim 均有 fingerprints 与不 shift 的 fixed-window metrics。

<!-- guide-section:11 -->
## 11. 故障排查

| 症状 | 可能原因 | 检查 | 安全处理 |
| --- | --- | --- | --- |
| “Please set NCHUNKS to 6 ... GLOBAL_SPONGE” | two chunks 启用了 sponge | ABSORB_USING_GLOBAL_SPONGE | 设 .false.；使用 external Stacey |
| 声称有 Stacey interface | node/face 混淆或 defect | face-role record | 要求 AB–AC **face** records=0；否则停止 |
| patch verifier 失败 | source 不匹配或已应用 | baseline/candidate SHA、reverse check | 不 force/overwrite；重新验证 version |
| mesher 拒绝 ranks/NEX | decomposition 不兼容 | Par_file 与 stop text | 改用 compatible layout |
| point outside | center/gamma 或 coordinates 错误 | custom input 用 planner；fixture 用 teaching audit | 移 point 或完整 system，再运行适用的检查 |
| zero/invalid trace | excluded receiver/input/solver failure | receiver list/log | 在 new run 修正 inputs |
| pre-arrival comparison 差 | invalid window | travel-time assessment | 重设 window；不得 shift traces |
| rank disagreement | settings/mesh defect | fingerprint/raw traces | 复现 canonical inputs；不明即停止 |

<!-- guide-section:12 -->
## 12. Teaching case、术语与 evidence

cases/two_chunk_canonical_90deg/ 是 teaching fixture，不是 Kim/Song Hawaiʻi input
或 production model。它含 NEX=96、2×2/chunk、50 km isotropic source、两个面内的
stations、audit_geometry.py、figure source 与 deliberate runner。static audit 应报告
7 个 in-domain points 和 total ranks=8。其 audit 与 runner 不能审计或启动 custom input case。

**术语简表。** external boundary 是暴露面，可有 Stacey。internal interface 交换
wavefield，永远不能有 sponge/Stacey。C1/C2 是 interface endpoints；shared nodes
不合并 face roles。fingerprint 是 physical mesh summary，不是 MPI file count。

**证据。** official regional behavior 位于
specfem3d_globe/doc/USER_MANUAL/05_regional_simulations.tex。current geometry 位于
euler_angles.f90、write_profile.f90、read_compute_parameters.f90。absorption 位于
read_parameter_file.F90、create_regions_mesh.F90、get_absorb.f90、get_model.F90、
meshfem3D_models.F90。patch hashes 位于
patches/specfem3d_globe/two_chunk_endpoints/。accepted topology/waveform closure 位于
docs/two_chunk_corner_topology_acceptance.md 与
docs/two_chunk_waveform_symmetry_closure.md。文档改动记录见
[revision report](two_chunk_regional_simulations_guide_revision_report.md)。
