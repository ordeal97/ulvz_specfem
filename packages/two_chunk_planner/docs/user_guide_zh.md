# Canonical 双 chunk planner 使用指南

## 1. 用途与适用范围

`two_chunk_planner` 是本 ULVZ 项目已接受 canonical 区域几何的运行前、只读规划与
审计工具。它搜索 central latitude/longitude 与 `GAMMA_ROTATION_AZIMUTH`，分类震源
和台站，审计路径/目标覆盖，并生成供人工审阅的 Par_file 片段。它不运行、也不能替代
SPECFEM mesher、database、solver、Stacey、分解、波形或生产级边界返回验收。

它仅支持 `NCHUNKS=2`、90°×90° chunk、AB 为 central first chunk、AC 为
supported-left second chunk，以及全系统唯一的中心和方向。不支持非 90°或矩形 chunk、
其他 attachment side、非相邻 chunk、独立定向、任意 two-chunk topology 或
three-/multi-chunk 模式。见[几何图](figures/canonical_two_chunk_geometry.svg)。

## 2. 环境与安装

基础依赖为 Python >=3.11、NumPy、Matplotlib、PyYAML；phase-aware 还需要 ObsPy，
而 geographic TauP path 需要 ObsPy 可使用 geographiclib。本项目使用：

```bash
PY=${ULVZ_PYTHON:-python3}
PYTHONPATH=packages/two_chunk_planner/src "$PY" -m two_chunk_planner --help
PYTHONPATH=packages/two_chunk_planner/src "$PY" - <<'PY'
from obspy.geodetics.base import HAS_GEOGRAPHICLIB
print(HAS_GEOGRAPHICLIB)
PY
```

可选 editable install：

```bash
"$PY" -m pip install -e packages/two_chunk_planner
"$PY" -m pip install -e 'packages/two_chunk_planner[phase]'
```

第二条命令声明 ObsPy phase extra；应检查 `HAS_GEOGRAPHICLIB`，不能假定
geographiclib 已可用。安装不等于应用 patch。若从项目 checkout 外部安装，必须显式
给出 `--project-root` 与 `--specfem-root`，因为 hash 校验需要 project patch manifest
和 SPECFEM target source。缺少 ObsPy 会报
`phase-aware mode requires optional dependency obspy`；缺少 geographic position 时会
成为缺失 phase-path，不会自动替代路径。

## 3. 快速开始

在仓库根目录运行，所有 `--output` 路径必须尚不存在。

```bash
P=packages/two_chunk_planner
PY=${ULVZ_PYTHON:-python3}
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan \
  --cmtsolution $P/examples/geometry_only/DATA/CMTSOLUTION \
  --stations $P/examples/geometry_only/DATA/STATIONS \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output $P/validation/manual_geometry_<UTC>
```

phase-aware Pdiff/Sdiff 使用：

```bash
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan \
  --cmtsolution $P/examples/phase_aware/DATA/CMTSOLUTION --stations $P/examples/phase_aware/DATA/STATIONS \
  --path-mode phase-aware --phases Pdiff,Sdiff --taup-model prem --taup-resample \
  --analysis-window 0 1900 --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output $P/validation/manual_phase_<UTC>
```

CSV 台站示例使用：

```bash
PYTHONPATH=$P/src "$PY" -m two_chunk_planner plan --source 0 0 50 \
  --stations-csv $P/examples/station_csv/stations.csv --analysis-window 0 1900 \
  --latitude-range 0,0 --longitude-range 0,0 --gamma-range 0,0 \
  --output $P/validation/manual_csv_<UTC>
```

其中固定 `0,0` center/gamma 仅用于确定性快速示例，不能理解为一般推荐。

## 4. 输入与校验

必须二选一：`--cmtsolution` 或 `--source LAT LON DEPTH_KM`；也必须二选一：
`--stations` 或 `--stations-csv`。CMTSOLUTION 要有 PDE header 和 12 条 labelled
record，并校验非零矩张量、有限经纬度和非负深度。STATIONS 每行六个空白字段：
station、network、latitude、longitude、elevation、burial。CSV 必须有
`network,station,latitude_deg,longitude_deg`；`elevation_m`、`burial_m` 可选。重复
network/station 和非法数值会被拒绝。

工具读取 `--par-file`，否则读取 `--specfem-root` 下的 `DATA/Par_file`；它使用
`ELLIPTICITY`、`SUPPRESS_CRUSTAL_MESH`、`ADD_4TH_DOUBLING` 进行几何或 NEX 兼容性
判断，但不会修改该文件。一次运行必须给出 phases、analysis window 或
`--target-energy-end-s` 之一。

`--target-region` 为严格 YAML。package 示例包括：circle（`name`、`type: circle`、
`center.latitude_deg`、`center.longitude_deg`、`radius_km`）；polygon（`name`、
`type: polygon`、至少三个有名 vertices）；corridor（`name`、`type: corridor`、至少
两个有名 centerline point、正 `half_width_km`）。未知或缺失 YAML field 均为错误。
`--weights` 是独立严格 mapping，仅允许 `coverage`、`external_margin`、
`endpoint_margin`、`cost`；不存在 YAML/CLI 优先级合并。source 与 station 的两种
输入形式均为互斥，而非合并。

## 5. 路径模式与 phase coverage

`geometry-only`（默认）采样地表 source-station 大圆；其 `--phases` 文本不生成
phase path。`phase-aware` 对每个 phase×station 独立调用
`TauPyModel.get_ray_paths_geo()`。每条记录包含 requested/returned phase、到时、TauP
model、`resample`、ray-parameter tolerance、地理样本数、最大采样深度和由 Cartesian
弦长累加的 `raypath_length_km`，其状态固定为
`taup_raypath_polyline_estimate`。

CMB-near 字段是最大采样深度附近的 proxy，使用可配置
`--cmb-near-depth-tolerance-km`（默认 25 km）；它不是物理 CMB 交点。全部 TauP
record 都带 `boundary_time_use=forbidden`。

默认 strict：任一请求的 phase×station 缺失后，工具列出全部缺失 pair 并拒绝整个
请求。加 `--allow-partial-phase-coverage` 后，保留可用的原请求 phase，并在
`candidates.json`、`geometry_audit.json`、`report.md` 写入 requested/provided/missing
的 `phase_inventory` 和“不替代 phase”警告。

## 6. center/gamma 搜索与 canonical 几何

工具执行确定性 coarse grid、local refinement、final refinement。默认
latitude/longitude/gamma coarse step 为 10°/10°/15°，local 为 2°/2°/3°，final 为
0.5°/0.5°/0.5°；默认范围为 latitude −90..90、longitude −180..180、gamma 0..360。
极点表示会 canonicalize，避免同一物理方向重复。结果按总分降序、再按 center
latitude、longitude、gamma 排序，最多返回五个不同的可行候选。

AB 与 AC 在 xi-constant shared interface 相接；C1/C2 是物理 endpoints；external
face 与内部 interface 不同。靠近 internal interface 仅警告，震源/台站精确落在
external boundary 或 endpoint 会被拒绝。点会分类为 central chunk、supported-left
chunk、shared interface、endpoint/external boundary 或 outside。若没有可行候选，仍会
写出全部输出、rejection summary 和注明无可行候选的 Par_file fragment。

## 7. 边界时间与 NEX/MPI 建议

对可行候选，给出 `--boundary-speed-upper-km-s` 时工具计算采样 surface-arc 的
source→boundary→station proxy。它始终是 `heuristic_not_conservative`，
`hard_constraint_used=false`，仅供参考。`analysis_end_s` 优先取
`--target-energy-end-s`，否则取 `--analysis-window` 终点；所报告 margin 不是 hard
pass/fail。没有可行候选时状态为 `unavailable`；未给速度时秒数为 null。TauP 不参与
这一计算。

默认 NEX 为 96×96，总 ranks 关系为 `2*NPROC_XI*NPROC_ETA`。兼容性还取决于当前
Par_file physics flag。NEX=96 且总 ranks 2、8、12 标记为 `project_validated`；其他
数学兼容配置仅为 `mathematically_compatible_not_project_validated`。lateral work 只是
per-rank proxy，不是运行时间预测。

## 8. 输出与完整流程

每次成功运行写出：`candidates.json`、`candidates.csv`、
`recommended_Par_file.inc`、`geometry_audit.json`、`boundary_time_audit.json`、
`report.md`、`map.png`、`run_manifest.json`。复制 Par_file fragment 前应检查 patch
provenance、source/station class 与 margin、`path_audits`、`phase_inventory`、TauP
metadata、boundary status、NEX/MPI label、warning 和 rejection reason。

推荐流程：准备输入；geometry-only 初筛；可用时做 phase-aware 复核；选择并人工审阅
候选；把 fragment 手工复制到独立管理的 SPECFEM Par_file；之后独立运行 mesher/database，
检查 C1/C2 与 Stacey role，运行 solver，并做波形和外边界返回验收。

## 9. 常见问题与限制

- **输出目录已存在：** 选择新路径；工具刻意拒绝覆盖。
- **patch hash 不匹配：** 停止，核对 project manifest、SPECFEM root 和 accepted patch；
  不要绕过。
- **缺依赖或 TauP 无震相：** 不自动安装；strict 失败，partial 只报告原请求的可用路径。
- **所有候选被拒绝：** 查看 `rejection_summary`；输出仍可审计。
- **日期变更线：** map 在 ±180° 分段，Cartesian 长度不受影响。
- **target YAML 错误：** 仅使用上述严格 key/type。
- **phase-aware 较慢或与 geometry-only 不同：** 前者使用 TauP ray path，后者使用地表
  大圆；排序是确定性的，不是随机噪声。
- **boundary time unavailable 或过早：** 它不是生产安全证据；必须单独进行波形/边界返回
  评估。
- **MPI 标记非 project-validated：** 它仅数学兼容。

## 10. 当前验证状态

合成 AB→AC Pdiff/Sdiff 与旋转后的 dateline case 已通过；fixture 不是 Kim/Song 输入。
完整 package 测试为 13 passed。resample 长度差为 Pdiff 14.7813 km（0.130094%）、
Sdiff 8.6426 km（0.076131%），因此 sampling stability 为 `indeterminate`。当前状态为
`boundary_time_production_safe=false` 与
`canonical_geometry_planning_validated__waveform_and_boundary_production_validation_required`。
