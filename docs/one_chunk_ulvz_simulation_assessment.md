# One-chunk ULVZ 合成波形能否基本替代 six-chunk global：技术评估

## 1. 摘要

对于当前**本地构造**的 Hawai'i 震源—ULVZ—台站几何，`NCHUNKS=1` 的 135°×135° regional domain 在目标区域与 six-chunk global 具有接近的实际 GLL spacing，并在统一的中等分辨率全时窗对照中较好复现了 HICAND 的 Pdiff 和主要 Sdiff 波形。推荐候选是 center `(16°, -166°)`、`GAMMA_ROTATION_AZIMUTH=154°`、全径向网格和侧边 Stacey absorbing conditions。

这并不表示 one chunk 与 global 无条件等价。Pdiff 的替代性在本 fixture 中很强；Sdiff、绝对振幅与 postcursor 对域大小、mesh alignment 和网格布局更敏感。边界 probes 与完整记录均未给出能**唯一**归因于侧边界的 science-window 污染，但也未能将后期差异完全分解。因此结论保持 **B：有实证支持的条件性生产候选**，`production_safe=false`，而非 A 类或无条件的 production-safe。

本报告只整理已有 mesher、solver 和后处理结果。没有重跑模拟、没有修改 `SPECFEM3D_GLOBE` 源码，也不声称复现 Kim et al. 的原始输入或生产分辨率。

## 2. 研究问题和适用范围

问题是：在什么条件下，one-chunk 可以在 ULVZ 合成波形研究中基本替代 six-chunk global，从而用于大量参数扫描？这里的“基本替代”是针对相同物理设置下的目标相位和科学时间窗，不是逐样点相同，也不是对任意事件、任意频段、任意 ULVZ 参数或绝对全波形拟合的保证。

已验证 fixture 为 `locally_constructed_one_chunk_boundary_validation`：source 为 `(-5°, 145°)`、深度 208.6 km；science station 为 HICAND `(25.26927°N, 110.75903°W)`；ULVZ 中心为 `(19.6°N, 155.5°W)`、半径 512 km、高度 50 km、`dVs=-0.20`、`dVp=-0.15`、`dRho=+0.10`，采用 smooth taper。直接来源：`results/one_chunk_boundary_validation_20260713T161732Z/08_reports/summary.json` 的 `source`、`ulvz` 和 `fixture` 字段。

它是 Hawai'i 论文给出的事件类型和几何范围的本地代理，不是论文 Fig. S4 的精确重建：项目中没有论文原始 `Par_file`、CMTSOLUTION、STATIONS 或 orientation。

## 3. 已完成测试概览

| 证据层级 | 已完成内容 | 可支持的判断 | 不能支持的判断 | 直接证据 |
| --- | --- | --- | --- | --- |
| 源码约束 | 参数、坐标映射、吸收边界、位置例程审计 | `NCHUNKS=1` 是支持的 regional mode | 大宽度必然数值可靠 | `docs/one_chunk_hawaii_yuan_analysis.md` 的 source-constraint evidence；`specfem3d_globe/src/shared/read_compute_parameters.f90:430-439` |
| 低分辨率宽度扫描 | 90°、105°、120°、135°、150°，NEX=32 | 这些宽度均可 mesh，Jacobian 为正 | 生产频率、生产精度或所有宽度安全 | `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary.json` 的 `mesh_status` |
| 几何搜索 | Hawai'i 与 Yuan 代理几何、边界余量 | 当前 Hawai'i 代理的 135°候选覆盖 | 论文原始 orientation | `03_orientation_search/outputs/orientation_search.json` 与 `08_reports/summary.json` |
| 中等分辨率统一全时窗对照 | 135° one chunk、120° one chunk、6-chunk global | 当前 fixture 的 runtime、spacing 与波形差异 | 生产分辨率认证或普适边界安全 | `results/one_chunk_boundary_validation_20260713T161732Z/08_reports/summary.json` |
| 完整记录后处理 | 已有 one135/global 的 51 对 seismograms | 全时窗差异的量级和时间诊断 | 新的正演验证或边界因果证明 | `results/one_chunk_waveform_comparison_20260714T123258Z/` |

two-chunk 路径不作为本报告的生产替代方案。当前 `NCHUNKS=2` 在多 rank 角点 interface 有已知缺陷，分类同为 B；见 `results/two_chunk_mesh_analysis_20260713T111923Z/07_reports/summary.json` 的 `corner_interface_complete=false`、`chunks_physically_connected=false`。

## 4. One-chunk 几何和宽度限制

`NCHUNKS=1` 是源码明确允许的参数值。当前 parser 没有对 one-chunk xi/eta width 施加显式上限；但坐标映射在 `specfem3d_globe/src/meshfem3D/compute_coordinates_grid.f90:149-163` 使用 `tan(width/2)`。因此 `<180°` 只是避免 tan 奇点的数学条件，**不是**数值可靠宽度上限。旋转由 center latitude/longitude 放置局部 AB face，gamma 旋转局部轴；证据见 `specfem3d_globe/src/shared/euler_angles.f90:30-86`。

one chunk 的四个 lateral sides 是 regional 边界，`xmin/xmax/ymin/ymax` 按 Stacey absorbing boundary 分类；证据见 `specfem3d_globe/src/meshfem3D/get_absorb.f90:268-300,335-412`。要包含 CMB Pdiff/Sdiff，必须采用全径向网格，不能使用 regional cutoff；当前 fixture 的 `REGIONAL_MESH_CUTOFF=.false.` 可在 `04_onechunk_135/fixture/run_final_corrected_probes_fullcopy/DATA/Par_file:97` 核实。

## 5. 90°–150°网格质量测试

所有五个 width 的 NEX=32、full-radial 低分辨率 mesh 均正常结束且 Jacobian 为正。该扫描只是拓扑、参数合法性和畸变趋势检查，不是生产精度认证；原始汇总在 `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary.json` 的 `tested_widths_deg` 与 `mesh_status`，每个 mesher log 位于 `05_mesh_smoke/logs/`。

| width | mesher 结果 | crust/mantle edge scale ratio | minimum Jacobian eigenvalue ratio | 说明 |
| ---: | --- | ---: | ---: | --- |
| 90° | 成功、正 Jacobian | 94.8 | 0.02062 | 畸变最低，但当前 Hawai'i 代理余量不足 |
| 105° | 成功、正 Jacobian | 110.7 | 0.01615 | 仍不足以提供当前几何所需的保守余量 |
| 120° | 成功、正 Jacobian | 130.8 | 0.01224 | 可覆盖代理几何，但最小余量只有 16.8° |
| 135° | 成功、正 Jacobian | 161.0 | 0.00863 | 当前覆盖余量与畸变之间的选定平衡 |
| 150° | 成功、正 Jacobian | 212.0 | 0.00434 | 畸变显著，不推荐用于生产 |

表中质量值由 `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary_validated.json` 和各 width 的 `05_mesh_smoke/fixtures/width_*/run/OUTPUT_FILES/output_mesher.txt` 交叉记录。150°并不是“不可运行”，而是当前已测范围内 Jacobian 质量最差、横向尺度比最大的选择；不能因其可以 mesh 就作为 reference domain。

## 6. Hawai'i 135°候选域和边界余量

当前 Hawai'i 代理的几何优化结果为：

```text
NCHUNKS                         = 1
ANGULAR_WIDTH_XI_IN_DEGREES     = 135
ANGULAR_WIDTH_ETA_IN_DEGREES    = 135
CENTER_LATITUDE_IN_DEGREES      = 16
CENTER_LONGITUDE_IN_DEGREES     = -166
GAMMA_ROTATION_AZIMUTH          = 154
REGIONAL_MESH_CUTOFF            = .false.
ABSORBING_CONDITIONS            = .true.
```

直接输入证据：`results/one_chunk_boundary_validation_20260713T161732Z/04_onechunk_135/fixture/run_final_corrected_probes_fullcopy/DATA/Par_file:13-29,97,115`。几何搜索给出的最小 lateral margin 是 source 24.3304°、station 24.7565°、ULVZ edge 55.0038°、CMB proxy 48.3837°；直接来源为 `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary.json` 的四个 `*_boundary_margin_deg` 字段。

它通过 10°、15°和20°筛选而未达到25°（source 少约0.67°）。这些角距离仅表示几何不贴边，不能自动转换为“无反射”或生产安全时间窗；传播速度、目标周期、记录长度和边界吸收效率仍须共同验证。

## 7. One-chunk 与 six-chunk 的实际分辨率匹配

中等分辨率统一全时窗对照使用：

| 配置 | one135 | six-chunk global |
| --- | ---:| ---:|
| NEX_XI/NEX_ETA | 96/96 | 64/64 每个 90° face |
| NPROC_XI/NPROC_ETA | 2/2 | 2/2 每个 face |
| MPI ranks | 4 | 24 |
| lateral absorbing edge | 是 | 否 |

配置与 ranks 的直接记录在 `results/one_chunk_boundary_validation_20260713T161732Z/08_reports/summary.json` 的 `one135`、`global6` 字段和两份 final `DATA/Par_file`。3:2 NEX 只是名义角间距设计；真正的 matching 取自 mesh database 的目标层统计。`03_mesh_resolution/analysis_target_layers/actual_mesh_resolution_summary.json` 给出的 P50 horizontal/radial GLL spacing 差异如下：source 2.08%/约0%、ULVZ internal 5.64%/约0%、ULVZ edge 5.23%/约0%、CMB corridor 0.28%/约0%、station 0.93%/约0%。五个区域均低于预先记录的15% matching criterion。

因此下面的 waveform comparison 可以称为该 fixture、该低频设置下的 matched-resolution comparison；它不能证明 `NEX=96` 已达到任何正式最短周期或 Kim et al. 约6.3 s 的生产分辨率。

## 8. Solver 运行和完整目标时间窗

本次 one135、global6 和 one120 都完成 16,800 steps、exit status 0；最终 solver 报告结束时间为 1723.6965 s。共同 `DT=0.1035 s`，requested duration 为 1708.5736 s。直接来源：`results/one_chunk_boundary_validation_20260713T161732Z/08_reports/summary.json` 的 `common_dt_s`、`record_length_requested_s`、`solver_reported_end_time_s`、各 case 的 `solver_steps` 和 `solver_status`。

本地 PREM TauP 给出 Pdiff=821.6790 s、Sdiff=1518.5736 s，postcursor window end=1588.5736 s；它们来自同一 JSON 的 `taup_prem`。故本运行覆盖 Pdiff、Sdiff、70 s postcursor end 和120 s安全余量。两种 solver 都成功定位 17 个 receivers（1 science station + 16 probes），证据为 `deep_probe_station_support=true` 和各 case 的 `OUTPUT_FILES/output_solver.txt`。

## 9. Pdiff 波形对比

科学相位分析使用 HICAND-Z、80–250 s period-band filtering，并在每个相位窗内允许搜索 time shift。窗口为 Pdiff `791.679–891.679 s`。`results/one_chunk_boundary_validation_20260713T161732Z/07_waveform_analysis/metrics_v2/waveform_window_metrics.csv` 中 `XX.HICAND.MXZ.sem.ascii,Pdiff` 的直接值为：

- zero-lag CC=0.9996991，best CC=0.9999010；
- estimated shift=-0.41404 s；
- peak amplitude difference=+0.02511；envelope amplitude difference=+0.05825；
- RMS residual=`1.1636e-9`。

同一分析的 `domain_convergence_diagnosis.json` 和 `08_reports/summary.json` 记录 Pdiff residual RMS / early-pre-return RMS=0.09407。Pdiff 窗没有相对于 early baseline 的残差放大，且形状、到时和包络都接近。因此，对当前 fixture 的 Pdiff 主相，one135 具有很强的替代性。

## 10. Sdiff、振幅与 postcursor 波形对比

HICAND-Z Sdiff 窗是 `1488.574–1588.574 s`，同一 CSV 的直接值为 zero-lag CC=0.9714462、best CC=0.9816294、estimated shift=-2.38073 s、peak amplitude difference=-0.05096、envelope amplitude difference=-0.10817、RMS residual=`6.3671e-9`。Sdiff residual RMS / early RMS=0.30323，来自 `07_waveform_analysis/metrics_v2/domain_convergence_diagnosis.json` 与 `08_reports/summary.json`。

这仍是总体一致的 Sdiff，但明显弱于 Pdiff 的替代性：Sdiff 的波形形状、相对到时和绝对振幅差异更大。`07_waveform_analysis/metrics_v2/postcursor_metrics.csv` 中 Pdiff postcursor/main amplitude ratio 是 global 2.1467、one135 2.3244；Sdiff 的相应值是 global 2.5639、one135 2.3237。该数字说明 postcursor 振幅解释须谨慎；它不是 one/global 完全相同的证据。

one120（同为 NEX=96）将 HICAND-Z Sdiff CC 降至0.9200459，Sdiff residual/early 提高至0.5893873；直接来源为 `08_reports/summary.json` 的 `one120_domain_test.science_z`。这表明 Sdiff 对域大小、mesh alignment 或网格布局敏感。但是 one120 对 global 的实际 horizontal spacing 差异为6.1–11.8%，见 `03_mesh_resolution/analysis_120_target_layers/actual_mesh_resolution_summary.json`，所以它不是纯 domain-size perturbation，不能把下降唯一归因于侧边界。

## 11. 完整记录波形对比：HICAND 三分量全时窗诊断

这是一项已有 solver output 的后处理，不是新的正演。它比较 HICAND 的 MXE、MXN、MXZ 三个分量，时间轴相同，从 -15.000 s 到1723.697 s、每条16,800 samples。直接来源：`results/one_chunk_waveform_comparison_20260714T123258Z/04_metrics/comparison_metadata.json` 的 `components`、`time_start_s`、`time_end_s`、`time_samples` 和 `time_axes_identical`。

图件如下：

- `results/one_chunk_waveform_comparison_20260714T123258Z/03_figures/hicand_complete_raw.png`：raw output；
- `results/one_chunk_waveform_comparison_20260714T123258Z/03_figures/hicand_complete_80_250s.png`：**80–250 s period-band filtered records**。

两图均为三行两列：左列叠加 135° one-chunk 与 six-chunk global，右列为逐样点 `one − global` residual；绿色/橙色阴影分别标注 Pdiff/Sdiff 时间窗，红色虚线为 station-return lower bound。滤波图的“80–250 s”表示周期通带，不表示80–250秒的时间窗口：绘图脚本 `02_script/plot_full_waveform_comparison.py:31-34` 使用 fourth-order Butterworth `1/250–1/80 Hz` 并以 `sosfiltfilt` 零相位应用；同目录 `comparison_metadata.json.processing` 也记录其定义。

`04_metrics/full_record_metrics.csv` 包含51对 trace，各有 raw 与 `80-250_s_bandpass` 两种处理，共102 data rows（加 header 共103行）。它们是**全记录、零时移**指标，不能与允许在 Pdiff/Sdiff 窗中估计 time shift 的相位窗 CC/shift 视为同一种误差度量。原始记录的 HICAND 指标如下：

| 分量 | zero-lag CC | relative L2 residual | one/global peak | max residual/global peak |
| --- | ---: | ---: | ---: | ---: |
| MXE | 0.91308 | 0.43560 | 1.25892 | 0.43425 |
| MXN | 0.57478 | 0.86399 | 0.82241 | 1.05088 |
| MXZ | 0.76241 | 0.80341 | 1.13231 | 0.92168 |

filtered full-record HICAND 的对应值为：MXE CC=0.96469、relative L2=0.32654；MXN CC=0.99644、relative L2=0.08526；MXZ CC=0.79253、relative L2=0.61952。上述全部数值直接来自该 CSV 的 `XX.HICAND.*` 行。全51条 raw trace 的 CC 范围为0.56256–0.94816、中位数0.80885，relative L2 范围0.32386–1.34998、中位数0.61673；filtered trace 的 CC 范围0.79253–0.99644、中位数0.96469，relative L2 范围0.08526–1.08724、中位数0.28599。

完整记录显示三分量并不一致，也没有一条与 global 逐样点相同：metadata 的 `exact_file_counts` 为 byte-identical=0、numeric-identical=0。它支持“Pdiff 局部窗高度一致、全记录不等价”的判断，不能用一条视觉上相近的 waveform 代表全部分量、全部到时或 probes。

## 12. 边界返回诊断与残差归因

station return lower bound=1196.4 s 是基于几何和速度估计得到的、侧向边界残余能量**最早可能**返回 HICAND 的保守下界；直接记录在 `02_taup_geometry/fixture_and_duration_135deg.json` 和 `07_waveform_analysis/metrics_v2/domain_convergence_diagnosis.json`。它不是在波形中检测到的实际反射到时，也不保证该时刻一定存在可见反射。

该诊断的 early-pre-return 窗为801.679–1176.408 s。HICAND-Z residual envelope 和 probes 的 one-minus-global differences 在该保守下界之前已经出现；而 science trace 在下界之后没有满足“late residual increase >3× early RMS、与几何下界相容、且与 probe onset 同时出现”的预注册归因规则。直接来源：`metrics_v2/domain_convergence_diagnosis.json` 的 `attribution_rule`、`science_late_residual_onset_s` 与 `probe_onsets.csv`。因此：

- Pdiff 窗内 residual 低，支持 one135 的局部替代性；
- Sdiff 窗 residual 更高，但没有出现可唯一归于侧边界的新增残差；
- 下界之前的系统差异排除了“全体 residual 都是晚期边界反射”的简单解释；
- 下界之后缺少可唯一分离的 probe-return 证据，不能反向证明边界完全无影响。

one/global residual 可能混合以下因素：lateral Stacey absorbing boundary、regional/global 域差异、cubed-sphere 网格方向和离散误差、元素/GLL alignment、以及同一 ULVZ 在两种网格采样下的表示差异。两边输入的 ULVZ 参数相同，故不能把差异称为“不同 ULVZ 物理”；但 ULVZ 信号对 sampling/alignment 的敏感性仍会反映在差异中。

## 13. 何时 one chunk 可以基本替代 six chunks

下列是建议性的验证框架，不是对所有事件、周期、ULVZ 参数或网格通用的硬阈值。当前 Hawai'i fixture 的 CC、time shift、residual 和 margin 只是该框架的一次已测实例。

1. source、所有保留 stations、ULVZ 的完整边缘和 CMB-sensitive corridor 均在域内，并报告各自的 lateral margin。
2. 在 source、ULVZ core/edge、CMB corridor、station 附近，one/global 的实际 horizontal 与 radial GLL spacing 接近；不能只比较 NEX。
3. 比较必须固定背景模型、ULVZ、source、stations、DT、time scheme、record length、输出采样和物理开关。
4. Pdiff、Sdiff 的目标主窗 CC、time shift、振幅/包络残差应小于该研究要区分的 ULVZ 参数效应。
5. postcursor delay 和 postcursor/main amplitude ratio 的科学结论不应因 domain 选择而实质改变。
6. science window 内不应有与几何预测边界返回相一致的额外残差增长；若有，必须用 global 或更大域区分。
7. 同一参数扫描固定 mesh、chunk center、gamma、width 和 station geometry，避免把 grid signature 混入 ULVZ effect。
8. 对代表性 ULVZ 参数做 six-chunk 抽样质量控制，尤其检查 Sdiff/postcursor，而非仅依赖一次 smoke 或单台站相似性。

满足以上框架时，one chunk 可作为大量参数扫描的**条件性工作域**。程序正常结束、Jacobian 为正、waveform 非零、单台站看似相似、或短时 smoke test 均不足以单独证明替代关系。

## 14. 何时不能替代 six chunks

不应使用当前 one135 结论的情形包括：

- 未重新搜索 center/gamma 的不同事件、不同 source–ULVZ–receiver 方位；
- 120°–140°长距离事件且其 CMB corridor 或 stations 余量不足；Yuan Event 2 的构造代理在150°时仅18.1°，见 `03_orientation_search/outputs/orientation_search.csv`；
- 需要150°域来取得覆盖的情况，因为已测畸变明显；
- 高于当前 80–250 s period-band 所代表的频率内容，或目标最短周期/最小波长尚未重新确定 NEX 的情况；
- 以绝对 Sdiff 振幅、微小时差或 postcursor/main ratio 作为核心反演目标，却没有 global 抽样 QC 的情况；
- 需要无条件全时窗、全三分量等价，或要把 residual 唯一归因于边界的情况。

## 15. 仅使用 ULVZ-enabled 波形的额外风险

若数据集只模拟 `ULVZ-enabled`，而不计算相同网格上的 `reference-disabled`，则边界/离散化误差不能通过 `enabled − disabled` 差分被直接抵消或量化。该选择可以节省计算，却收紧数据集的一致性要求：

- 同一事件内固定 chunk center、gamma、width、NEX、NPROC、DT、时间方案、record length 和 output sampling；
- 固定 source、stations 和背景模型，只改变 ULVZ 几何或物性参数；
- 每个样本保存 mesh ID、center、gamma、width、source/station/ULVZ/CMB margins、NEX/NPROC、模型参数和 global validation status；
- 用少量 six-chunk **ULVZ-enabled** models 作为 QC，覆盖弱/中/强异常，小/中/大半径，薄/厚模型，abrupt/smooth boundary，以及强弱不同的 postcursor；
- 不把未经控制的不同 orientation 或不同网格混入同一物理参数效应的比较。

因此，当前证据支持 one135 生成该 Hawai'i 类型的 ULVZ-enabled 合成波形；Pdiff 绝对波形可信度较高，Sdiff 的绝对振幅、postcursor amplitude ratio 和小时间差须更谨慎。它不支持把该结论推广到未经验证的事件和 orientation。

## 16. ULVZ 合成数据集设计建议

| 数据集层级 | 域与目的 | 必须固定/记录 | 不应承担的结论 |
| --- | --- | --- | --- |
| 主数据集 | 135° one chunk，大量 ULVZ-enabled parameter sweep | 同一事件固定 orientation、mesh、source/stations/physics；完整 metadata | 对所有事件的绝对 global 等价 |
| 质量控制集 | 少量 six-chunk global ULVZ-enabled | 覆盖参数空间端点与代表性 postcursor | 代替全量 one-chunk 扫描 |
| 域敏感性集 | 保持135°和目标分辨率，小幅移动 center 或 gamma | 一致的 ULVZ/source/stations；比较域稳定性 | 将单一 orientation 当作普适最优 |

机器学习训练/验证/测试划分应优先按 event 或 mesh/orientation group 分组，而不是在不同事件和网格的 trace 中随机拆分；否则模型可能学习 domain/grid signature 而不是 ULVZ 特征。不得纳入150°高畸变网格、余量不足的长距离事件、未记录 mesh/orientation metadata 的样本。

## 17. 当前 Hawai'i 候选的 Par_file 核心配置

以下是已验证 fixture 的核心参数，不是可直接复制给其他事件的生产处方。直接来源均为 `results/one_chunk_boundary_validation_20260713T161732Z/04_onechunk_135/fixture/run_final_corrected_probes_fullcopy/DATA/Par_file`。

| 参数 | 当前值 | 含义与限制 |
| --- | --- | --- |
| `SIMULATION_TYPE` | 1 | forward；见第7行 |
| `NCHUNKS` | 1 | regional one-chunk；第13行 |
| angular width xi/eta | 135°/135° | 当前几何的折衷；第16–17行 |
| center lat/lon/gamma | 16°/-166°/154° | 只适用于本地构造几何；第18–20行 |
| `NEX_XI/NEX_ETA` | 96/96 | 本次 matched-resolution 对照值，不是通用生产 NEX；第24–25行 |
| `NPROC_XI/NPROC_ETA` | 2/2 | 4 ranks；第28–29行 |
| `MODEL` | `s40rts` | 与本地 ULVZ overlay 的统一物理设置；第68行 |
| `ATTENUATION` | `.false.` | 本次 domain-convergence 对照的统一设置，非 Kim et al. 完整科学复现；第76行 |
| `RECORD_LENGTH_IN_MINUTES` | 28.47622603 | 由当前 TauP 时间窗决定；第86行 |
| cutoff | `.false.` | 保留 CMB/外核路径；第97行 |
| lateral absorption | `.true.` | regional sides 使用 Stacey；第115行 |
| oceans/topography/rotation/gravity | `.false.` | 仅当前统一 fixture；第71–76行 |

其他事件必须用实际 source/station/ULVZ/CMB corridor 重新优化 center 与 gamma，并依据目标最短周期、最小波长和实际 GLL spacing 重新确定 NEX。

## 18. 局限性和后续验证

已验证事实是：one135/global 的当前 fixture 可以运行、目标区分辨率相近、Pdiff 高度一致、主要 Sdiff 一致且全时窗未显示可唯一归因于侧边界的 science-window 污染。合理解释是135°在当前几何下提供了足够大的工作域，而120°和150°分别暴露了余量/域敏感性与网格畸变的两端风险。

未解决的问题包括：实际 Kim et al. 输入缺失；probes 未能唯一分离物理多路径与边界返回；one120 不是纯 domain-size test；当前频段和 `ATTENUATION=.false.` 不代表生产频率/完整物理。要提高结论强度，应在目标最短周期与最终 ULVZ 参数范围上保持实际 spacing matching，运行更多站与更多 orientation 的 six-chunk ULVZ-enabled 抽样 QC，并使用可分离的域大小收敛设计。

## 19. 最终结论

对于当前 locally constructed Hawai'i 几何，在 135°×135°、center `(16°, -166°)`、gamma=154°，并使 source、ULVZ、CMB corridor 和 station 的实际 GLL spacing 与 six-chunk global 接近的条件下，one chunk 能较好复现 global 的 Pdiff 和主要 Sdiff 波形。Pdiff 替代性很强；Sdiff 和 postcursor 对域大小、mesh alignment 及网格布局更敏感。

完整记录后处理加强了这一受限结论：它确认全三分量、全时窗并非逐样点相同，且 residual 在保守 return lower bound 之前已存在；没有发现能唯一归于侧边界的 science-window 新增污染。由于后期 residual 的来源仍不能唯一分离、probes 不足以单独识别返回波、one120 对比含有 spacing/alignment 混杂，当前方案仍是 **B 类条件性生产候选**，不是无条件的 `production_safe` six-chunk 替代方案。

## 20. 证据表

| 问题 | 结论 | 最直接证据 |
| --- | --- | --- |
| one chunk 是否允许 | 是；无显式 width parser cap | `specfem3d_globe/src/shared/read_compute_parameters.f90:430-439`；`results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary.json` |
| 180°含义 | tan 映射奇点，不是可靠宽度 | `specfem3d_globe/src/meshfem3D/compute_coordinates_grid.f90:149-163` |
| 150°是否推荐 | 否；ratio 212、Jacobian 0.00434 | `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary_validated.json` |
| 135°几何余量 | 24.3°/24.8°/55.0°/48.4° | `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/08_reports/summary.json` |
| 实际 resolution 是否匹配 | 是，所有目标区 P50 spacing 差异≤5.7% | `results/one_chunk_boundary_validation_20260713T161732Z/03_mesh_resolution/analysis_target_layers/actual_mesh_resolution_summary.json` |
| 统一全时窗 runtime | three cases 16,800 steps、exit 0、结束1723.70 s | `results/one_chunk_boundary_validation_20260713T161732Z/08_reports/summary.json`；各 `logs/*.exit_code` |
| Pdiff 一致性 | HICAND-Z CC 0.99970，shift -0.41 s | `07_waveform_analysis/metrics_v2/waveform_window_metrics.csv` |
| Sdiff 一致性 | HICAND-Z CC 0.97145，shift -2.38 s；非完全等价 | 同上 |
| 120°含义 | Sdiff 对域/网格敏感，但受 spacing 混杂 | `08_reports/summary.json`；`analysis_120_target_layers/actual_mesh_resolution_summary.json` |
| 完整记录是否相同 | 否；51对均非字节或数值逐样点相同 | `results/one_chunk_waveform_comparison_20260714T123258Z/04_metrics/comparison_metadata.json` |
| 边界污染是否被证明 | 未在 science window 唯一证明，也未完全排除 | `07_waveform_analysis/metrics_v2/domain_convergence_diagnosis.json` |
| 最终分类 | B，`production_safe=false` | `results/one_chunk_boundary_validation_20260713T161732Z/08_reports/summary.json` |

## 本次文档变更

本次仅新增本报告并更新 `docs/project_status.md` 的索引。未运行 mesher、solver、编译或任何新的正演模拟；未修改 SPECFEM3D_GLOBE 生产源码或既有结果。
