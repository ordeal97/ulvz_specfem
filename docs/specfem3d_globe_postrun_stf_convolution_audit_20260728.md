# SPECFEM3D_GLOBE 模拟后震源时间函数卷积核查

核查日期：2026-07-28（只读审计；未运行 mesher 或 solver，未对正式波形卷积）

## 结论摘要

| 问题 | 结论 | 证据状态 |
| --- | --- | --- |
| `half duration = 0` 后能否事后卷积？ | 可以。这是手册对**点源**明确推荐的工作流：零半持续时间的合成波形代表阶跃矩（Heaviside）响应，其 moment-rate 理想化为 delta；之后可施加目标 STF。 | 手册与源码已核查；未做 A/B 数值等价性试验。 |
| 手册所列三种工具是否都能完成？ | 手册确实列出 `process_syn.pl -h`、`convolve_source_timefunction.f90`/`convolve_source_timefunction.csh` 和 SAC。但当前树中“核心 Fortran 程序”可编译；两个脚本均有直接使用限制。 | 编译/入口链已核查。 |
| 工具等级 | **B：基本可用，但需要调整。** 直接 Fortran 程序可对两列 ASCII 使用内置 Gaussian（或 triangle）卷积；包装 csh 脚本路径脆弱，`process_syn.pl` 依赖当前环境不存在的 SAC 工具与 `convolve_stf`。 | 不是 A；也不是因核心程序缺失而为 C。 |
| 内置 Gaussian 是否与 solver 一致？ | 连续函数的参数化一致：两者均使用 `SOURCE_DECAY_MIMIC_TRIANGLE = 1.628`。但事后程序以有限窗口离散求和、零填充并删去结尾样点，故不能声称离散结果与一次 solver 运行严格完全等价。 | 源码公式已核对；数值等价性未验证。 |
| 是否支持任意自定义 moment-rate？ | 否。Fortran 程序只接受一个布尔开关选择内置 Gaussian/triangle；csh 固定为 Gaussian；`process_syn.pl -h` 固定调用 `convolve_stf t`（triangle）。 | 源码已核查。 |
| 现有 `half duration = 3.1 s` 波形能否作为未卷积基础波形？ | 不能。该波形已在 solver 内含非零 STF；再次卷积是重复卷积。 | 实际 `CMTSOLUTION`、`Par_file`、`output_solver.txt` 已核查。 |

本报告的源码根目录为
`/import/freenas-m-01-seismology/xjiang/ulvz_specfem/specfem3d_globe`（下文简称 `S`）；
被核查模拟为
`/import/freenas-m-01-seismology/xjiang/ulvz_database/simulations/event1_2chunk`（下文简称 `R`）。
源码提交为 `9c312cb2c991b47484a7f302775f4f01ed9470f8`，`git describe` 为
`v8.1.0-323-g9c312cb2-dirty`。工作树已有与本审计无关的修改，未被改动。

## 1. 手册规定的流程

### 手册明确说明的事项

- 对点源，`half duration = 0` 表示阶跃 source-time function（Heaviside），其 moment-rate 是 delta；非零值使用平滑伪 Heaviside，其对应 moment-rate 是 Gaussian，且该参数被称为 triangle 的 half-width/half duration：[`S/doc/USER_MANUAL/04_running_the_solver.tex:57-64`](../specfem3d_globe/doc/USER_MANUAL/04_running_the_solver.tex#L57) 。
- 手册明确写道，通常可先用零 half duration 运行，再对合成波形事后卷积，以便尝试不同 STF；列出的入口是 `process_syn.pl -h`、串行 `convolve_source_timefunction.f90`、`utils/convolve_source_timefunction.csh` 或 SAC，并给出 `make convolve_source_timefunction` 与设置 `hdur` 的说明：[同文件:66-82](../specfem3d_globe/doc/USER_MANUAL/04_running_the_solver.tex#L66)。
- 手册规定合成时间轴的零点是 triangle/Gaussian 的中心；非零 half duration 时模拟起点为 `-1.5 * half duration`，绝对时间为 `t_PDE + time shift + t_synthetic`：[同文件:87-99](../specfem3d_globe/doc/USER_MANUAL/04_running_the_solver.tex#L87)。
- 后处理章节把“在零 half-duration SEM 模拟之后，用 `CMTSOLUTION` 指定 half duration 卷积合成波形”列为推荐处理步骤第 2 步；仪器响应移除则单独针对观测数据：[`S/doc/USER_MANUAL/13_post_processing.tex:31-39`](../specfem3d_globe/doc/USER_MANUAL/13_post_processing.tex#L31)。
- `process_syn.pl` 的手册描述是“ASCII 合成输出转 SAC，并进行类似 `process_data.pl` 的操作”；示例 `-h` 将其描述为来自 `CMTSOLUTION` 的 triangle STF：[同文件:69-93](../specfem3d_globe/doc/USER_MANUAL/13_post_processing.tex#L69)。

### 手册未说明或未主张的事项

- 手册**未**给出 `convolve_source_timefunction.f90` 的 ASCII 列数、固定控制文件名、输出删样规则、离散归一化误差或 padding 规则。
- 手册**未**声称“solver 内非零 `half duration`”与“零 half duration 后处理卷积”在离散采样、起始时间、有限记录和边界处理上严格完全等价。
- 手册**未**声明该 Fortran/csh 工具可读取任意用户 moment-rate 文件；“容易使用多种 STF”是流程层面的描述，不能替代对各程序接口的审计。
- 有限断层情形被单独警告：half duration 通常由有限断层模型确定，通常不宜设零后再卷积：[`04_running_the_solver.tex:159-165`](../specfem3d_globe/doc/USER_MANUAL/04_running_the_solver.tex#L159)。本报告的结论仅适用于所述 CMT 点源工作流。

## 2. Solver 内部 STF：读取、换算与施加

### 调用链

```text
DATA/CMTSOLUTION
  -> get_cmt.f90: 读取 time shift、half duration、矩张量
  -> setup_sources_receivers.f90 / setup_sources()
  -> setup_stf_constants(): hdur_Gaussian = hdur / 1.628，确定 t0
  -> compute_add_sources.f90 / get_stf_viscoelastic()
  -> comp_source_time_function.f90 / comp_source_time_function_heavi()
  -> compute_add_sources(): sourcearrays * stf 加入 accel_crust_mantle
```

1. `get_cmt` 通过冒号后的字段读取 `time shift` 和 `half duration`：
   [`S/src/specfem3D/get_cmt.f90:222-246`](../specfem3d_globe/src/specfem3D/get_cmt.f90#L222)。
2. 对 CMT 源，若读入 `hdur < 5*DT`，源码把它替换成 `5*DT`；注释明确称其为“very short error function”：
   [`get_cmt.f90:367-380`](../specfem3d_globe/src/specfem3D/get_cmt.f90#L367)。因此 `half duration = 0` 在实现中不是数学上的无宽度 delta，而是与当前 `DT` 相关的短正持续时间。
3. 单一 CMT 源的运行时相对 `tshift_src` 被置零，同时原始最小 time shift 被保存用于事件时间信息：
   [`get_cmt.f90:392-399`](../specfem3d_globe/src/specfem3D/get_cmt.f90#L392)。这解释了单源日志显示 `time shift = 0` 而原始 `CMTSOLUTION` 仍保留非零 time shift 的现象。
4. `setup_stf_constants` 执行 `hdur_Gaussian = hdur / SOURCE_DECAY_MIMIC_TRIANGLE`，并对 CMT 以 `t0 = -min(tshift_src - 1.5*hdur)` 确定起点：
   [`S/src/specfem3D/setup_sources_receivers.f90:721-800`](../specfem3d_globe/src/specfem3D/setup_sources_receivers.f90#L721)。常数 `SOURCE_DECAY_MIMIC_TRIANGLE = 1.628d0` 定义在 [`S/setup/constants.h:316-320`](../specfem3d_globe/setup/constants.h#L316)。
5. 每个时间步，`compute_add_sources` 计算 `timeval = time_t - tshift_src`、取 `get_stf_viscoelastic`，并把 `sourcearrays * stf` 加到加速度：
   [`S/src/specfem3D/compute_add_sources.f90:48-95`](../specfem3d_globe/src/specfem3D/compute_add_sources.f90#L48)。

### 数学定义及物理量

设 `H` 为 `CMTSOLUTION` 的非零 half duration，`a = 1.628 / H`，则 solver 实际使用的 Gaussian 宽度是 `h_g = H / 1.628`。

对默认 CMT（非 monochromatic、非 sine-squared）注入的是归一化的伪 Heaviside / 累积矩函数：

```text
S(t) = 1/2 [1 + erf(t / h_g)]
```

见 [`S/src/specfem3D/comp_source_time_function.f90:66-82`](../specfem3d_globe/src/specfem3D/comp_source_time_function.f90#L66)。其导数（即对应的 moment-rate）是：

```text
m(t) = a / sqrt(pi) * exp[-(a t)^2]
```

`get_stf_viscoelastic` 对 CMT 的默认分支正是调用该函数，参数为 `hdur_Gaussian`：
[`compute_add_sources.f90:536-550`](../specfem3d_globe/src/specfem3D/compute_add_sources.f90#L536)。

因此“Gaussian”在这里特指 **moment-rate**；solver 直接乘到 moment-tensor source 的是其时间积分 `S(t)`，并非 Gaussian 值本身。该函数的极限为 0 和 1，故不会改变最终静态矩标度；实际矩张量缩放在 `get_cmt` 中另行完成（[`get_cmt.f90:402-410`](../specfem3d_globe/src/specfem3D/get_cmt.f90#L402)）。

### Newmark、LDDRK 与 STF 输出

- 两种时间推进均经同一个 `get_stf_viscoelastic` 定义取源函数。Newmark 用 `time_t=(it-1)*DT-t0`；LDDRK 使用其阶段时间 `time_t=(it-2+C_LDDRK(istage))*DT-t0` 来补偿推进顺序：[`compute_add_sources.f90:48-79`](../specfem3d_globe/src/specfem3D/compute_add_sources.f90#L48)。因此函数定义相同，取样时刻不同；本报告未运行两种方案作数值比较。
- `PRINT_SOURCE_TIME_FUNCTION` 触发 `print_stf_file()`（[`setup_sources_receivers.f90:684-688`](../specfem3d_globe/src/specfem3D/setup_sources_receivers.f90#L684)）。其文件每行是 `time(s), stf, scalar_moment`，其中 `stf` 来自 `get_stf_viscoelastic`：
  [`S/src/specfem3D/print_stf_file.f90:108-132`](../specfem3d_globe/src/specfem3D/print_stf_file.f90#L108)。故它输出的是累积矩/伪 Heaviside（及标度），不是 moment-rate，也不是“时间步进器中单独离散出的 Gaussian 核”。
- 合成波形已经包含该 `stf`，因为它在源项加入加速度之前相乘；不需要也不应把非零 half-duration 波形视作基础阶跃响应。

## 3. 事后卷积程序与完整调用链

### 构建与可调用性

| 项目 | 审计结果 |
| --- | --- |
| Makefile target | `make convolve_source_timefunction`、`make xconvolve_source_timefunction` 和 `make bin/xconvolve_source_timefunction` 的 `-n` 均解析为目标 `bin/xconvolve_source_timefunction`。默认目标列表也包含它：[`S/Makefile:592-609`](../specfem3d_globe/Makefile#L592)。 |
| 依赖 | `convolve_source_timefunction.aux.o` 与 `shared_par.shared_module.o`；链接规则见 [`S/src/auxiliaries/rules.mk:132-141`](../specfem3d_globe/src/auxiliaries/rules.mk#L132)。依赖文件完整。 |
| 实际编译 | 在 `/tmp/specfem-stf-audit.j7j6Pb` 中，以当前 `setup/constants.h`、`shared_par.f90` 与工具源文件，并沿用 `make -n` 显示的 gfortran 标志，成功生成 `xconvolve_source_timefunction` ELF。未改写 `S/obj` 或 `S/bin`。 |
| 调用 | 对隔离二进制执行无输入调用，到预期的 `input_convolve_code.txt` 缺失检查处退出（Fortran line 51）。这确认其没有命令行 help/argument 接口，而依赖固定控制文件。 |
| 当前环境 | `gfortran`、`mpif90`、`csh`、`perl` 存在；`sac`、`saclst`、`convolve_stf` 未在 `PATH` 中找到。 |

这只证明“核心程序已编译并可调用到其输入检查”；不证明任何与 solver 的波形等价性。

### `convolve_source_timefunction.f90`

入口是 `S/src/auxiliaries/convolve_source_timefunction.f90`，程序名 `convolve_source_time_function`。

- 它从当前工作目录固定读取 `input_convolve_code.txt` 三行：`nlines`、`half_duration_triangle`、逻辑量 `triangle`；然后从标准输入逐行读取 **两列数值** `timeval, sem`：
  [`convolve_source_timefunction.f90:50-63`](../specfem3d_globe/src/auxiliaries/convolve_source_timefunction.f90#L50)。它不读取 SAC binary、SAC alphanumeric 或任意 STF 文件。
- `dt = timeval(2)-timeval(1)`；没有检查等间隔、至少两样点、正 `dt` 或正 `half_duration`：
  [同文件:65-76](../specfem3d_globe/src/auxiliaries/convolve_source_timefunction.f90#L65)。
- `triangle=.false.` 时核为与 solver 同参数的
  `a exp[-(a tau)^2]/sqrt(pi)`，且离散和显式乘 `dt`：
  [同文件:111-122](../specfem3d_globe/src/auxiliaries/convolve_source_timefunction.f90#L111)。因此其连续核面积为 1，输出单位与输入单位保持一致；其用途是对阶跃响应施加单位面积 moment-rate。
- `triangle=.true.` 时是内置线性三角核，高度 `1/H`：
  [同文件:88-107](../specfem3d_globe/src/auxiliaries/convolve_source_timefunction.f90#L88)。这不是 solver 默认 CMT 的 Gaussian moment-rate。
- Gaussian 循环窗口只到 `N_j=ceil(1.5H/dt)`，虽另有 `exponent < 50` 判断，但在此窗口内该判断并不控制实际尾端。窗口截断后没有重新归一化；输出采用零 padding，且只写 `1 ... nlines-(N_j+1)`，保留原时间列而删掉结尾样点：
  [同文件:71-76、78-132](../specfem3d_globe/src/auxiliaries/convolve_source_timefunction.f90#L71)。

结论：对充分长的两列、等采样基础波形，程序按预期实施近似离散卷积；但其头尾处理、删样和截断意味着不能将其结果宣称为已证明与 solver 的非零 `H` 完全等价。

### `convolve_source_timefunction.csh`

`S/utils/scripts/convolve_source_timefunction.csh` 是上述程序的薄包装：

- 固定 `half_duration_triangle = 11.2`，且把 `triangle` 固定写为 `.false.`，故脚本只跑 Gaussian；不会从 `CMTSOLUTION` 读取目标 `hdur`：[`...csh:7-20`](../specfem3d_globe/utils/scripts/convolve_source_timefunction.csh#L7)。
- 以 `wc -l` 建立固定名 `input_convolve_code.txt`，调用相对路径 `../bin/xconvolve_source_timefunction`，并写 `${file}.convolved`；随后执行 `rm input_convolve_code.txt`：[`...csh:11-22`](../specfem3d_globe/utils/scripts/convolve_source_timefunction.csh#L11)。
- 因可执行路径相对**当前工作目录**而非脚本位置，只有从合适目录（例如在 `S/utils` 运行 `scripts/convolve_source_timefunction.csh`）时 `../bin` 才指向 `S/bin`；从 `S` 或 `S/utils/scripts` 直接运行会指向错误位置。固定临时文件也使并发运行互相冲突。
- `csh -n` 无参数时在 `$*` 的 glob 展开处报 `No match`；脚本没有 help/usage。未执行该脚本，以避免其创建/删除文件。

因此它不是可直接照抄运行的稳健入口；应修正可执行路径、目标 `hdur`、临时文件隔离和输出策略后才适用于生产处理。

### `process_syn.pl`

`S/utils/scripts/seis_process/process_syn.pl` 是另一条、且不同的调用链。

- 已实际无参数调用，返回 usage（exit 1），接口声明 `-h` 为“从 `-m CMTSOLUTION` 取 half duration 卷积 triangle STF”：[`process_syn.pl:7-45`](../specfem3d_globe/utils/scripts/seis_process/process_syn.pl#L7)。
- 对非 `-S` 输入，它执行同目录调用名 `ascii2sac.csh`；`ascii2sac.csh` 又硬编码 `./asc2sac`：[`process_syn.pl:95-107`](../specfem3d_globe/utils/scripts/seis_process/process_syn.pl#L95)，[`ascii2sac.csh:1-11`](../specfem3d_globe/utils/scripts/seis_process/ascii2sac.csh#L1)。这要求特定当前目录和未随本链验证的 `asc2sac`。
- 对 `-h`，它只在 `hdur > 1.0` 时执行 `$convolve_stf t $hdur $outfile`，随后把 `${outfile}.conv` 移回 `$outfile`：[`process_syn.pl:77-91、131-137`](../specfem3d_globe/utils/scripts/seis_process/process_syn.pl#L77)。`t` 是 triangle，不是上述 solver 参数化 Gaussian；原/输出 SAC 文件可能被覆盖。
- 其核心依赖是 `sac`、`saclst`、`convolve_stf`、可选 `phtimes.csh` 和 IASP91；注释掉了存在性检查。`phtimes.csh` 还硬编码 `/opt/seismo-util/source/iaspei-tau`：[`phtimes.csh:13-57`](../specfem3d_globe/utils/scripts/seis_process/phtimes.csh#L13)。本环境缺少 SAC、`saclst`、`convolve_stf`，故当前不能直接使用。

该脚本可处理 ASCII（先转换）或已有 SAC（`-S`）的**SAC 工作流**；它不是核心 Fortran 程序的包装，也不支持任意自定义 moment-rate。

## 4. 对现有 `event1_2chunk` 波形的判断

- `R/DATA/CMTSOLUTION:3-4` 为 `time shift = 4.7000 s`、`half duration = 3.1000 s`。
- `R/DATA/Par_file:264-276` 设定 CMT 源、非 monochromatic、非 sine-squared、`PRINT_SOURCE_TIME_FUNCTION = .false.`；`Par_file:300-304` 同时开启 ASCII 和 SAC binary 输出。
- `R/OUTPUT_FILES/output_solver.txt:115-121` 明确记录“using moment tensor source”“using (quasi) Heaviside source time function”“half duration: 3.1 seconds”。单源运行时 shift 为 0，与 `get_cmt` 的相对化规则一致，并不否定原始 4.7 s。日志还记录 Newmark、`DT=0.100000001 s`、起点 `-4.65000010 s`：`output_solver.txt:393-400`；该起点正是 `-1.5*3.1 s`。
- 本例 `PRINT_SOURCE_TIME_FUNCTION=.false.`，故 `OUTPUT_FILES` 中没有 `plot_source_time_function*.txt`；这只能说明未输出诊断 STF，不能说明波形未含 STF。
- 已检查的 ASCII 文件 `TA.V57A.BXN.sem.ascii` 有 21,200 行、开头为两列时间/振幅（起始时间约 `-4.65 s`）；目录中也有 `.sem.sac` 文件。对于核心 Fortran 程序，ASCII 两列文件格式适配；`process_syn.pl` 则可从 ASCII 转 SAC 或以 `-S` 走已有 SAC 分支，但当前依赖不满足。

### 再次卷积的效果

当前波形已经是 Green 函数与 `m_H(t)` 的卷积。若再次以相同的、理想归一化 Gaussian `m_H` 卷积，结果是 `m_H * m_H`，而不是“补上缺失 STF”。连续极限下它仍是 Gaussian，方差相加；以本代码的参数定义表示，其等效 half-duration 参数约为：

```text
H_eff = sqrt(H^2 + H^2) = sqrt(2) H = 4.384 s   (H = 3.1 s)
```

这会进一步展宽、降低高频和改变到时附近的形状。实际工具还叠加其截断、padding 与删样规则，故 `4.384 s` 只是理想连续 Gaussian 的解释，不是对本例输出的实测结果。用 triangle 或 SAC 的 `convolve_stf t` 则是另一种核，不能用这一 Gaussian 等效式替代。

若目标是以多个目标 `H` 对同一 Green/阶跃基础响应作公平比较，应重新计算各相同模型的 `half duration = 0` 基础波形（接受 solver 的 `5*DT` 短正值正则化），再把每个目标 STF 独立卷积；不应从已经是 `H=3.1 s` 的波形再卷积或反卷积得到该基础波形。

## 5. 论文与补充材料核查

本节只报告本地 `reference/` PDF 的明确文字。依 academic-research-suite 的本地 PDF 完整性预检，`aan0760_yuan_sm.pdf`（22 页）和 `sciadv.adz1962_sm.pdf`（23 页）为 `PASS`；`science.aan0760.pdf` 与 `sciadv.adz1962.pdf` 出现 xref-coverage 警告，预检为 `UNAVAILABLE`，因此对后两者不使用未经验证的 PDF 页码作精确锚点，只报告本地文本提取所见内容。

| 论文 | 明确报告 | 明确未找到/未报告 |
| --- | --- | --- |
| `reference/science.aan0760.pdf`（Yuan 等主文）及 `reference/aan0760_yuan_sm.pdf`（补充） | 补充材料第 2 页说明事件矩张量来自 Global CMT，并说明观测/合成波形的 Butterworth、10–20 s 等滤波处理（通过预检的 PDF 页/文本定位）。主文亦提到 CMT solution 和滤波。 | 未报告 `half duration` 数值、solver 内 STF 的具体定义、模拟结束后对合成波形的 STF 卷积，或 source deconvolution。 |
| `reference/sciadv.adz1962.pdf`（主文）及 `reference/sciadv.adz1962_sm.pdf`（补充） | 主文明确：原始观测去仪器响应、5–100 s Butterworth 滤波；为减小震源效应，**Pdiff 观测波形**以各事件 CMT 和 PREM 合成波形作 source deconvolution；建模所用矩张量来自 Global CMT；并说明使用 SPECFEM3D 与 AXISEM-3D。补充材料通过预检的第 2 页图注明确“source deconvolved seismograms”，第 5 页说明参考源参数基于 CMT。 | 未报告 SPECFEM3D 的 `half duration` 或 solver STF 参数，也未报告“对已完成合成波形再卷积 STF”或“对合成波形作 source deconvolution”。 |

必须区分：上述“去仪器响应”和“用 PREM 合成对**观测** Pdiff 作 source deconvolution”是观测数据处理；它们不能被解释为 SPECFEM solver 内 STF，亦不能被解释为对 SPECFEM 合成结果做事后 STF 卷积。论文中出现的滤波、对齐、包络、直方图均衡等处理也不等同于 STF 卷积。

## 6. 最终直接回答

1. **仅按手册操作能否完成模拟后 STF 卷积？** 可以。手册明确推荐点源零 half-duration 基础波形的事后卷积流程。
2. **提供的程序当前能否直接使用？** 核心 Fortran 已编译并可调用；整体工具链评级为 B，因 csh 路径/临时文件问题以及 `process_syn.pl` 的 SAC 依赖缺失，不能把全部手册入口称为当前“直接可用”。
3. **能否给零 half-duration 基础波形施加目标 Gaussian？** 核心 Fortran 以与 solver 相同的连续 Gaussian 参数化实现该目标，前提是输入为两列等采样 ASCII、目标 `H>0`，且使用者接受有限窗口、零 padding 和删样。它在源码设计上能够完成；离散结果与直接非零 `H` solver 的数值等价未验证。
4. **是否支持任意自定义 moment-rate？** 不支持。现有入口只提供内置 Gaussian/triangle（以及 `process_syn.pl` 的 triangle 调用）。
5. **是否需要改脚本、转换格式或自写程序？** 若坚持使用 `convolve_source_timefunction.csh`，需要至少修正路径、`hdur` 和临时/输出处理。若用 `process_syn.pl`，需提供 SAC、`saclst`、`convolve_stf`、相关转换/IASP91 工具，且它是 triangle 路径。核心 Fortran 不需 SAC，但要求两列 ASCII；若科学目标是任意自定义 moment-rate、保留完整记录并明确处理边界，现有程序不足，应另行编写/验证卷积实现。
6. **当前 3.1 s 波形是否是未卷积基础波形？** 否。日志已确认 solver 内施加非零伪 Heaviside/对应 Gaussian moment-rate；再卷积属于重复卷积。
7. **哪些已经确认、哪些未验证？** 已确认：手册表述、当前源码调用链、数学参数化、构建规则、核心隔离编译、入口接口、当前模拟设置与日志、论文明确文字。未验证：任意实际波形的卷积输出、与 solver 直接非零 `H` 的 A/B 等价性、截断/边界误差大小，以及对该 ULVZ/reference 模拟结果的任何科学结论。

