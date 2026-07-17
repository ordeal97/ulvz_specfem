# SPECFEM3D_GLOBE 两个 chunk 调查

## Executive summary

结论为 **B：参数可接受，mesh/database 与 solver 主路径可运行，但 NCHUNKS=2 的角点 MPI 接口装配不完整且在多 rank 分解中产生错误的跨 chunk 配对**。因此，当前代码不能被称为“原生完整支持、物理上完整连通的 two-chunk 域”。

已实际验证的强度如下：mesh/database **verified**（2 rank 与 8 rank）；solver 静态读库/接口路径 **verified**；隔离构建 **verified**；短时 solver runtime **verified，但只覆盖 NPROC_XI=NPROC_ETA=1 的主共享边**。8-rank 数据库揭示第二角点缺陷，故 runtime 成功并不推翻 B 类结论。没有运行论文的 480-element 生产网格。

本次证据在 `results/two_chunk_mesh_analysis_20260713T111923Z/`，机器可读摘要在该目录的 `07_reports/summary.json`。

## 版本、仓库与参考资料

嵌套源码是 `specfem3d_globe`，commit `9c312cb2c991b47484a7f302775f4f01ed9470f8`，描述为 `v8.1.0-323-g9c312cb2-dirty`。顶层不是 Git 仓库；嵌套仓库在开始时已含用户的修改和未跟踪 ULVZ 文件，均未更改。初末状态见结果目录 `00_inventory/repository_status/`。

只读 reference 目录实际含四个 PDF：`sciadv.adz1962.pdf`（Kim et al., Hawai'i 主文，11 页）、`sciadv.adz1962_sm.pdf`（其补充材料，23 页）、Yuan & Romanowicz 2017 主文和补充材料。提取文本和文件清单在 `00_inventory/reference_files/` 与 `02_paper_evidence/`。

Kim et al. 的方法文字称使用两个 cubed-sphere chunks；每 chunk 地壳/上地幔 480 个横向元素、CMB 约 120、最短周期 6.3 s、边缘吸收边界。Fig. S4 的参考事件是 2012-04-17、Mw 6.9、Eastern New Guinea、208.6 km，背景为 TI PREM。ULVZ 参数系列包括宽 512–1024 km、高 25–100 km、dVs −10% 至 −35%、dVp/dVs 比 1–3、密度 +10%、cosine taper。论文文件不包含原始 Par_file、精确 chunk rotation、CMTSOLUTION、STATIONS 或私有 patch；这些论文陈述不是本代码支持 `NCHUNKS=2` 的证据。

## 参数合法性与最小 smoke 网格

`read_compute_parameters.f90:430-439` 明确允许 `NCHUNKS=1,2,3,6`；2 chunks 要求 xi 宽度 90°，但 eta 90°只在大于 2 时强制。`NCHUNKS=2` 允许 absorbing conditions（同文件 `450-454`），不允许 central cube 的限制只针对非 6 chunk（`520-521`）。因此参数解析确实支持 2，不是仅有无效参数。

不能先验假设任何 NEX 都合法。`rcp_set_mesh_parameters`（`read_compute_parameters.f90:313-349`）按 crust/doubling 分支要求 NEX 分别为 8、16 或 32 的倍数，并要求 `NEX/4`、`NEX/8` 或 `NEX/16` 分别可被对应的 NPROC 方向整除；`define_all_layers.f90:126-147` 显示无 regional cutoff 的默认网格固定启用三个 doubling layers。因此本次 PREM、无 cutoff fixture 落在 32 分支：选择的最小值 `NEX_XI=NEX_ETA=32` 经实际 mesher 成功验证，绝非把 32 的一般错误归因于 two chunks。

本地可复现实验配置为：`NCHUNKS=2`、xi/eta 90°、中心 `(0°,0°)`、gamma `0°`、`1D_isotropic_prem`、无 topography/oceans/attenuation/rotation/gravity、全径向地球、外侧 absorbing，`NEX=32`。2-rank 取 `NPROC_XI=NPROC_ETA=1`；8-rank 取各为 2。总数由 `read_compute_parameters.f90:340-349` 精确给出：`NPROCTOT=NCHUNKS*NPROC_XI*NPROC_ETA`。rank 映射是 `create_addressing.f90:63-76` 的 `(ichunk-1)*NPROC + iproc_eta*NPROC_XI + iproc_xi`。

## 几何、编号与接口

`compute_coordinates_grid.f90:171-229` 给出六个固定 cubed-sphere face 的局部 xi/eta 到笛卡尔映射；AB 与 AC 的共享边是 **AB xi-min = AC xi-max**（`create_chunk_buffers.f90:314-323`）。随后坐标在 `compute_coordinates_grid.f90:236+` 由 latitude、longitude 与 gamma rotation 旋转。故 NCHUNKS=2 的语义是固定相邻面 AB/AC，不是两个独立 regional chunks，也不能任意挑两面。它们的邻接链为 `AB—AC—BC—CD—DE—EF—AB`，另有 cubed-sphere 顶点处三面相会。

| face | 正向相邻 face（按固定环） | NCHUNKS=2 中 |
|---|---|---|
| AB | AC、EF | 有 |
| AC | AB、BC | 有 |
| BC | AC、CD | 无 |
| CD | BC、DE | 无 |
| DE | CD、EF | 无 |
| EF | DE、AB | 无 |

主共享边的 GLL/MPI 逻辑由 `create_chunk_buffers.f90:314-323` 建 buffer，`read_mesh_databases.F90:2358+` 读回，`assemble_MPI_scalar.f90:32-123` 非阻塞交换并加和。它是 MPI buffer 接口，而非把不同 rank 的 global node ID 合并成一个 ID。

## 第二角点 TODO 的可复现影响

核心缺陷不是整条边缺失。`create_chunk_buffers.f90:155-175` 对两 chunks 只设一个 face/message type；`840-857` 却构造三面角点三元组：AB `(xi=0,eta=NPROC_ETA-1)`、AC `(xi=NPROC_XI-1,eta=NPROC_ETA-1)` 和不存在的 BC `(xi=NPROC_XI-1,eta=0)`。数组只复制 `1:NCHUNKS`，所以第三项保持零；紧随的 TODO 说明第二角点未装配，且“formally incorrect”。

对 8-rank (`2×2` 每 chunk)，rank 映射为 AB `0,1,2,3`，AC `4,5,6,7`。真实共享边应为 `0↔5`（eta=0）和 `2↔7`（eta=1）；后者附近需要处理的第二 cubed-sphere corner 不是 BC。实际 MPI 数据库解析结果在 `04_mesh_smoke/interface_checks/mesh_8rank/`：

- 全主边配对仍存在：每 region 的 GLL interface 条目为 `0↔5: 3669/877/81`、`2↔7: 3669/877/81`（regions 1/2/3）；所以缺陷不抹掉整条界面。
- 同时出现不应存在的对角 rank 对 `0↔7` 和 `2↔5`，每对每 region 为 `109/65/9` 条目，即每方向 183、总计 366 个 interface 条目。这与第三成员错误为 rank 0 和遗漏第二角点的索引路径一致。
- `get_MPI_interfaces.f90` 的 warning 路径也在 mesher 8-rank 日志中触发。这些是 MPI 邻居/interface buffer 条目错误；它们可能造成重复/错误配对与角点处 assembly 问题，而不是普通 global numbering 的合并失败。

对于 2-rank，伪第三成员恰与 AB rank 0 重合，数据库只见每 region 一个 `0↔1` interface，故短时 2-rank 测试不能暴露该多-rank 拓扑问题。受影响的是共享面两个端点之一的角点处理及相应 rank 对，而非面中部；动态反射幅度仍未量化。

## 吸收、径向与点定位

`get_absorb.f90:334-406` 在 two-chunk 时只把 AC 的 xmin 和 AB 的 xmax 写为吸收侧边，因而 AB xmin/AC xmax 的内部共享边不进入 Stacey absorbing 数据库。地表、底部和其它外边按其常规分类；CMB/ICB 是物理径向界面，并非此接口。无 cutoff 的本次网格包含全地球（核、CMB、ICB），从径向建模能力看可承载 Pdiff/Sdiff；这不修复角点缺陷。

源与台站都通过 `locate_point.f90` 的 `locate_MPI_slice` 跨 `NPROCTOT` 收集候选 slice，找不到即报错（调用证据在 `01_source_audit/call_paths/solver_and_location_paths.txt`）。短时 fixture 实测 source `(0°,-44°,50 km)` 在 slice 0，station `(0°,-46°)` 在 slice 1，定位误差约 `1e-12 km`，故跨 chunk 定位不是只假定 1/6 chunks。

## 低分辨率验证

2-rank 与 8-rank `xmeshfem3D` 都以 exit 0 完成。8-rank mesher 输出报告正 Jacobian（最小约 0.02062）及 face-message size 正确；数据库头、rank 映射和接口 CSV 在 `04_mesh_smoke/`。首次未授权 sandbox MPI 尝试因 Open MPI/PMIx listener socket 权限而未启动程序；后续独立运行成功，该环境失败未计作 mesh 失败。

为不污染现有 build，源码在结果目录的 `05_solver_build/build_root/` 独立拷贝构建；未 `make clean`，原源码与产物未覆盖。一次缺少独立 obj/bin 的建置基础设施重试后，`xspecfem3D` 成功构建并复制到 `05_solver_build/executables/`。

短时 2-rank solver 用 0.5 min（300 步）运行 exit 0，完成 `End of the simulation`。其 source 和 receiver 位于主接口两侧；三个 `XX.XIFACE` 分量各 300 sample，最大绝对振幅约 `0.229/0.172/0.368`，非零 sample 各 298。它验证主接口的实际 MPI runtime 传播路径、MPI 稳定性和非零台站波形；没有与独立参考做首波/反射幅度比较，不能声称已验证没有角点人工反射。

## Hawai'i 覆盖判断

`03_geometry/candidate_geometry.py` 以 Hawai'i marker `(19.6°,-155.5°)` 和明确标注的示意 Eastern-New-Guinea—North-America 路径绘制 one/two/six-chunk 候选，输出边界最小角距。它是 `locally_constructed_smoke_fixture`，不是 Fig. S4：在“AB 中心对准 Hawai'i”的候选中，示意震源不在 one/two 域，说明 orientation 必须根据完整 source/receiver 集合优化，且不能从论文文本反推精确参数。即使可找到覆盖所有点的 rotation，当前多-rank 角点 defect 若接近 ULVZ、CMB 敏感区或关键路径，就不适合生产 Hawai'i Pdiff/Sdiff；在修复并进行多-rank benchmark 前，推荐 six chunks 或可靠 one-chunk 局部方案。

## 最小可维护修复设计（未实施）

只修改 `create_chunk_buffers.f90` 的 NCHUNKS=2 corner 分支：不要把 BC rank 留为零，也不要复用三面 corner helper。显式枚举 AB–AC 两个共享边端点，分别以两 rank 的方向/索引置换生成二面 corner/edge endpoint buffer；保留现有 1、3、6 chunk 分支不变。随后在 `get_MPI_interfaces.f90` 增加断言：two-chunk 仅允许 AB–AC 相邻 rank 对，禁止 `0↔7`/`2↔5` 这种对角配对。测试应包括 1×1、2×2、非正方但合法 NPROC 分解，检查接口 pair、nibool、坐标/GLL 一一对应、Stacey 不含内部面，以及跨接口短时 solver 与 1-chunk/6-chunk reference 的波形差异。风险集中在端点重复/遗漏、方向翻转与向量分量旋转；不要将整个 six-chunk 三面角逻辑硬套给二面域。

## 证据表

| Question | Verdict | Source file | Routine | Lines | Evidence |
|---|---|---|---|---|---|
| NCHUNKS=2 可解析 | 是 | `src/shared/read_compute_parameters.f90` | `rcp_check_parameters` | 430-439 | 只允许 1/2/3/6；two chunk xi=90° |
| NEX 与 MPI 约束 | 已验证 NEX=32 | 同上 | `rcp_set_mesh_parameters` | 313-349 | doubling 分支和 `NPROCTOT` 公式 |
| rank→chunk 映射 | 完整 | `src/shared/create_addressing.f90` | `create_addressing` | 63-76 | chunk-major xi/eta 映射 |
| two-chunk 几何 | 固定 AB+AC | `src/meshfem3D/compute_coordinates_grid.f90` | `compute_coordinates_grid` | 171-236 | face 映射及整体旋转 |
| 主共享边 | 有 buffer | `src/shared/create_chunk_buffers.f90` | `create_chunk_buffers` | 314-323 | AB xi-min ↔ AC xi-max |
| 第二角点 | 错误/缺失 | 同上 | `create_chunk_buffers` | 840-857 | BC 未复制、rank 0 占位、TODO |
| MPI assembly | 存在 | `src/specfem3D/assemble_MPI_scalar.f90` | `assemble_MPI_scalar` | 32-123 | neighbor/ibool 非阻塞 assembly |
| 内部面吸收 | 否 | `src/meshfem3D/get_absorb.f90` | `get_absorb` | 334-406 | 仅 AC xmin、AB xmax 为外侧 |
| 点定位 | 跨 rank | `src/specfem3D/locate_point.f90` | `locate_MPI_slice` | static path saved | 对所有 slice 搜索，实测两侧定位 |
| 运行时 | 主面通过；角点未通过 | result logs | mesh/solver smoke | runtime | 8-rank database 异常 pair；2-rank solver exit 0 |

## 未决项

- 无法从现有论文文件获得原始 Hawai'i input，故没有 exact reproduction。
- 未测量有缺陷角点对波场反射的大小，也未运行 8-rank solver runtime；二者是修复后的必要验证。
- 现有手册 `doc/USER_MANUAL/manual/05_regional_simulations.tex` 记载 2/3 chunks 曾因未测试而从用户手册移除，这与上述当前实证相符。
