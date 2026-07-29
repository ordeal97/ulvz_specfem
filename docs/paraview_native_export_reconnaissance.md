# SPECFEM 原生 ParaView 导出调查

日期：2026-07-21；SPECFEM commit：`9c312cb2c991b47484a7f302775f4f01ed9470f8`。

## 结论：B

**原生 volume combiner 可复用其 GLL-subcell 体几何和单标量 VTU
写出；多字段、enabled/disabled ratio 与材料不连续界面仍必须保留自定义
导出。** 因此没有删除或改变
`scripts/ulvz_mesh_viz/export_paraview_model.py` 或
`EXPORT_PARAVIEW_MODEL_DATA` 的既有语义。

这不是“文件能被 ParaView 打开”即得出的结论。真实两 rank S40RTS+ULVZ
fixture 证明：`xcombine_vol_data_vtu` 的 `resolution=1` 确实是有效三维
GLL 线性子单元，但其按 rank-local `iglob` 合并点、默认保留首次碰到的
材料值。fixture 中同一 `iglob` 的两个谱元侧已有明显的 TISO 不连续；该
行为会静默抹去其中一侧，故不满足本项目 final-model 的 field-aware
split 要求。

完整命令、stdout/stderr、所有输出及 SHA256 在
[`results/paraview_native_export_reconnaissance_20260721T142243Z/README.md`](../results/paraview_native_export_reconnaissance_20260721T142243Z/README.md)。

## 三条原生链路

| 链路 | 程序、源码和构建目标 | 实际输入/输出 | 本分支与 fixture 结论 |
| --- | --- | --- | --- |
| A. AVS/OpenDX | `src/meshfem3D/write_AVS_DX_output.f90`; `src/meshfem3D/write_AVS_DX_global_*.f90`; `src/auxiliaries/combine_AVS_DX.f90` → `bin/xcombine_AVS_DX` | 编译期开关生成 rank-local `AVS_DXpoints*.txt`、`elements*.txt`；交互式合并为 `.inp` 或 `.dx`，并写 source/receiver 文件 | 标准体几何是每谱元 8 角点；faces/chunks/surface 是相应表面/边。没有 final-model scalar。fixture 的 faces/chunks 合并因工具错误尝试读取不存在的 reg4 失败；surface 成功。AVS `.inp` 可由 VTK 9.1 读取为 1122 points、1024 quads。 |
| B. volume scalar/VTU | `src/auxiliaries/combine_vol_data.F90` → `xcombine_vol_data`, `_vtk`, `_vtu` | `mesh_parameters.bin` + 每 rank/region `solver_data.bin`（`nspec,nglob,x/y/z,ibool`）+ `proc*_regN_<field>.bin` → `.mesh`/`.vtk`/单一 `.vtu` | 是真正的体网格和 PointData。`resolution=1` 是全 GLL 点构成的线性 hexahedral subcells；可读取 native `SAVE_MESH_FILES` 的 final fields，也可读取布局兼容的测试 ratio 文件。 |
| C. legacy 转换 | `utils/Visualization/VTK_ParaView/mesh2vtu/`：`mesh2vtu.cxx`、`Makefile` | generic `.mesh`（points + 一个 scalar + 8-node cells）→ `.vtu` | 与 volume combiner 的 `.mesh` 文件格式相容；但当前环境只有 VTK Python runtime、无 VTK C++ headers，`make` 失败，未安装依赖。不是 SPECFEM database/多字段工具。 |

`xcombine_AVS_DX` 的交互输入以本次可复现的 surface AVS 为例：

```bash
printf '2\n3\n2\n2\n0\n-1\n' | "$SPECFEM/bin/xcombine_AVS_DX"
# 2=AVS, 3=surface, 2=颜色 slice, 2=材料 slice, rank 0..-1
```

对应 OpenDX 仅把第一行改为 `1`。faces/chunks 的表示选择分别为 `1`、`2`；
均在此小 fixture 停在 `proc000000_reg4_AVS_DX...` 缺失，日志保留为一个
当前版本限制，而非将 AVS/OpenDX 按名字直接判为过时。

## `SAVE_MESH_FILES`：writer、时机和字段

`DATA/Par_file` 的 `SAVE_MESH_FILES=.true.` 经
`src/shared/read_parameter_file.F90` 读入。在
`src/meshfem3D/create_regions_mesh.F90` 约 425--448 行，某 region 已完成
模型/网格构建后，先调用 `save_model_meshfiles()`，再（仅当编译期常量
`SAVE_MESHFILES_AVS_DX_FORMAT=.true.`）调用 AVS writer。换言之，两者是
相关但独立的输出路径。

`save_model_meshfiles.f90` 直接读取最终的
`rhostore,kappavstore,kappahstore,muvstore,muhstore,eta_anisostore`。
TISO 时它将这些 solver 数组按同一缩放关系写成每 rank/region 的 Fortran
sequential unformatted GLL 数组：

```text
procXXXXXX_regN_rho.bin
procXXXXXX_regN_vpv.bin  procXXXXXX_regN_vph.bin
procXXXXXX_regN_vsv.bin  procXXXXXX_regN_vsh.bin
procXXXXXX_regN_eta.bin
```

各文件为 fixture 中的 2,160,008 bytes；本例没有独立 `vp.bin`/`vs.bin`，
它们分别对应 `vpv`/`vsv`。非 TISO 分支才写 `vp.bin` 和 `vs.bin`。因此：

- `SAVE_MESH_FILES` **确实**原生写出 final rho 与 TISO 派生速度/eta，
  但不写 `rhostore`、kappa/mu 原数组，也不写 ratio；
- writer 位于模型构建后的 region 保存阶段，数据源就是 solver 使用的
  material stores，而不是根据文件名推测；
- `solver_data.bin` 同时含坐标、`ibool`、`nspec/nglob` 与最终 stores；
  scalar `.bin` 本身不含坐标、rank、region 或 connectivity；
- 本次正式和隔离 build 的两 rank `solver_data.bin` 与 `vsv.bin` 都逐字节
  相同，大小分别为 48,073,704 与 2,160,008 bytes。该比较是控制检查，
  不把“隔离 build 必然等价”当作前提。

## AVS/OpenDX 实际内容

原分支默认 `SAVE_MESHFILES_AVS_DX_FORMAT=.false.`。受控隔离 source
snapshot 与当前嵌套 SPECFEM 同一 commit、同一 configure/编译器/MPI、同一
fixture 和 Par_file；保存了 commit、configure、build log 和 diff。唯一的
**有效 mesher** 源码差异是把该 constants 参数改为 `.true.`。该隔离副本也
带有当前 worktree 的既有未提交测试文件；本次额外的 test inspector 不被
`xmeshfem3D` 链接，不影响物理模型。启用 AVS 后没有改变上述 database
字节检查结果。

标准 `write_AVS_DX_global_data` 以 `ibool(1/NGLL,1/NGLL,1/NGLL,ispec)`
写 8 corners 与 hex connectivity；faces/chunks/surface writer 使用同样的
corner 编号和边界选择。它们服务于 slice edge、chunk edge、surface、MPI
partition/color 与 source/receiver 叠加，不是全 GLL final-field 体导出。
虽存在 `write_AVS_DX_global_data_gll`，但在
`write_AVS_DX_output.f90` 的调用是注释；它不是本分支启用开关后的行为，
且其材料输出只涉及 rho/vp/vs/qmu 的历史检查路径，不含完整 TISO/ratio。

## 手册 10.3 volume 工作流的真实语义

本分支实际命令为：

```bash
bin/xcombine_vol_data_vtu all vsv DATABASES_MPI DATABASES_MPI OUTDIR 1 1
# 参数：slice_list, filename, mesh/database dir, scalar dir, output dir,
#       resolution 0/1/2, region=1
```

程序用 `mesh_parameters.bin` 取得全局参数、用每 rank
`proc*_reg1_solver_data.bin` 读取 `nspec,nglob,x/y/z,ibool`，再把
`proc*_reg1_<filename>.bin` 作为
`real(CUSTOM_REAL)::data(NGLLX,NGLLY,NGLLZ,NSPEC)` 读入。名称不限定 kernel：
kernel 与 final model scalar 只要满足该 layout 都可用。输出由
`write_VTU_movie_data_binary` 写为 **single VTU、single PointData array**
`<filename>`；它不是每 rank VTU，也不写 PVTU。每个字段都须单独运行。

对 `NGLL=5`、2 rank、reg1 共 8640 谱元 fixture 的实测：

| resolution | 源码含义 | points / cells | cell 类型 |
| --- | --- | ---: | --- |
| 0 (`low`) | 每谱元一个 8-corner hex，stride=4 | 10,620 / 8,640 | VTK_HEXAHEDRON (12) |
| 1 (`high`) | stride=1 的全部 GLL 节点，`4^3=64` 线性 subcells/谱元 | 583,242 / 552,960 | VTK_HEXAHEDRON (12) |
| 2 (`mid`) | stride=2，8 subcells/谱元 | 76,806 / 69,120 | VTK_HEXAHEDRON (12) |

所以这里的 high-resolution 确实是有效 GLL-subcell volume mesh，不是
point cloud 或 surface；不能把它与 custom 的 field-aware split 表示混为
一谈。它在各 rank 内按 `iglob` 去重，跨 rank 并不全局焊接；NCHUNKS 和
region 由 `mesh_parameters`/slice list 驱动。本次只验证 NCHUNKS=1、reg1，
没有声称 one/two/six chunk 的全面验收，也没有原生“只 ULVZ 邻域”筛选器。

`vsv.vtu`、legacy `vsv.vtk` 和 `.mesh` 均成功生成。Python VTK 9.1 读取
high VTU 为 583,242 points/552,960 cells、`vsv` range
`[1.0043757, 7.4116812]`；`vsv_ratio.vtu` range
`[0.79999995,1.0]`。Slice、Clip、Threshold、Extract Surface 全部可执行
（审计记录各过滤器产生的 cell count）。该服务器的 Qt/ParaView GUI 无
display，offscreen `paraview --version` 仍因 xcb abort；故结论是“VTK
read/filter 已验证”，不把 GUI 渲染说成已验收。

VTK `MeshQuality` 的 signed-volume 审计也给出 native res=0 的 8,640
cells 全为正（`[4.09e-6,3.59e-4]`，normalized-volume units），res=1 的
552,960 cells 全为正（`[2.06e-8,1.30e-5]`）；custom ULVZ-window 的 256
km-cells 亦全为正。详见 `audit/vtk_cell_volume_audit.json`。这些是相同
cell 表示内的 orientation 检查，不将 native 全域和 custom window 的 cell
count 直接比较。

## Final-field 逐点核对、ratio 与不连续性

启用 ULVZ case 的原生 high-res `vsv` 和测试 `vsv_ratio` VTU，与 inspector
从 `solver_data.bin` 的 element-local records 对照了四类点：ULVZ core、
taper、外部、CMB 背景。最大所列 `vsv` 相对差为 `8.86e-8`（VTK float
舍入）；ratio 绝对差最大 `2.18e-8`。每条记录（rank/ispec/i/j/k/iglob、
坐标、native、solver、abs/relative difference）在
`audit/native_vsv_solver_samples.json`。这只证明同一侧的 native scalar 是
final model，不以 min/max 代替逐点检查。

ratio 的能力分级：

| 等级 | 结果 | 证据 |
| --- | --- | --- |
| Level 1：原生计算 enabled/disabled | 否 | `xcombine_vol_data_vtu` 只读一个 `filename.bin`，没有第二 case 或 ratio 运算。 |
| Level 2：读取外部布局兼容 ratio scalar | 是 | opt-in **项目测试功能** inspector 以 element-local paired records 写 `proc*_reg1_{rho,vp,vs,vpv,vph,vsv,vsh}_ratio.bin`；combiner 成功读完 7 个并写 7 个 VTU。它不是 `SAVE_MESH_FILES` 功能。 |
| Level 3 | 不适用 | 已达到 Level 2。 |

关键限制来自 `combine_vol_data.F90` 的
`AVERAGE_GLOBALPOINTS=.false.`：对每个 `iglob` 只保存首次访问的
`data(i,j,k,ispec)`。本 fixture 的 1,080,000 element-side GLL records
归到 583,242 rank-local iglob；重复点的最大差异为 rho 0.4785、vpv 1.4275、
vph 1.6008、vsv 0.7917、vsh 0.9960、eta 0.1033（完整两侧坐标在
`audit/shared_iglob_field_audit.json`）。这直接验证它既不 split、也不
平均（若改开关才平均），而是静默选择一侧。custom exporter 则依据字段和
ratio 保留 coincident split points。

## 与当前 exporter 的等价/非等价比较

| 维度 | native `xcombine_vol_data_vtu` | current custom exporter |
| --- | --- | --- |
| 几何坐标 | solver database 的实际无量纲坐标 | solver-data records 转 km 坐标 |
| 体表示 | res=0 8-corner；res=1 GLL subcells | GLL subcells；可选的 ULVZ window/full guard |
| MPI | 单 VTU 拼接选择的 ranks，但跨 rank duplicates 保留 | rank VTU pieces + PVTU |
| 多字段 | 每次一个 PointData scalar / 一个 VTU | 一个 PVTU 同载 vp/vs/rho、TISO、全部 ratio |
| final fields | 原生 SAVE files 的 rho/vpv/vph/vsv/vsh/eta 已验证 | 从最终 solver stores 导出，已验证 |
| ratio | Level 2，需项目 writer，每字段一个 VTU | 原生支持 element-local enabled/disabled pairing，单文件多数组 |
| 材料界面 | 合并同 `iglob`，首次值胜出，不安全 | field-aware split，保留不连续 |
| ParaView filters | 对每单场 VTU 可用 | 同样可用，且可对多个字段 Threshold |
| 局部 ULVZ 输出 | 无原生 field-aware selection | 已有 `ulvz-window`/`--full-mesh` 保护 |

只有节点集合、去重规则、子单元化、cell type 和 data association 都等价时，
才可比较 count/connectivity/signed volume。本次 native res=1 与 custom
window 的 scope、单位、分裂规则不同，故没有把 `583242/552960` 与
`450/256` 的正常差异误报为错误；已比较的等价项是外角覆盖/范围、原生
GLL 体单元与 final-field 同侧数值。

## 最小 hybrid architecture（推荐）

保留：

```text
test inspector (solver_data final records; element-local ratios)
  -> export_paraview_model.py
  -> rank VTU + PVTU, multi-array, field-aware split
```

可选的独立验证/辅助路径：

```text
SAVE_MESH_FILES -> native rho/vpv/vph/vsv/vsh/eta bins
solver_data + one scalar bin -> xcombine_vol_data_vtu (res=1) -> one-field VTU
```

如果未来需要 native VTU 作为部分产物，最薄的附加层只能负责把**完全相同
且安全的** native geometry 合并多字段；它不能重新焊接不连续点。对于本
项目，比保留现有 custom exporter 更复杂且仍不能解决界面问题，因此不建议
替换。

## 可重复测试和限制

- formal disabled/enabled 均以 `SAVE_MESH_FILES=.true.` 成功 meshed；MPI
  在该主机需 `mpirun --mca btl self,tcp --mca btl_tcp_if_include lo -np 2`。
- isolated AVS experiment 保存了 constants diff、configure、build/run logs。
  其串行构建曾遇工作树已有 module build race 的残留，最终所需
  `xmeshfem3D`/`xcombine_AVS_DX` 可运行；没有把该问题隐去。
- `mesh2vtu make` 状态为 2，原因是没有 VTK development headers；没有安装
  新依赖。
- AVS/OpenDX surface 是可用的独立几何检查路径，不是 full volume/final
  field 替代品；faces/chunks 的 reg4 失败仍待 upstream/fixture兼容性修复。
- 当前覆盖为 NCHUNKS=1、reg1、two MPI ranks；尚未给出 multi-chunk、ADIOS/
  HDF5 或生产尺度性能保证。
