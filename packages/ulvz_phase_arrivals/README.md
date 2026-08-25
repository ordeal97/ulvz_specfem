# ULVZ phase-arrivals

当前 package/API 版本为 **0.2.0**；annotation writer 写 **schema 1.1.0**。

`ulvz-add-phase-arrivals` 为完成的 SPECFEM3D_GLOBE synthetic 输出计算 PREM/TauP 理论到时。支持 ASDF `synthetic.h5` 与浅层目录中的 SPECFEM SAC (`*.sac` / `*.SAC`)；两种输入只共享 trace metadata reader，震源、台站和走时计算只有一套实现。

## 安装与调用

本项目不自动安装依赖。目标 Python 环境须已有 `obspy`、`h5py` 与 `numpy`，然后按需安装本地包：

```bash
python -m pip install -e packages/ulvz_phase_arrivals
ulvz-add-phase-arrivals /path/to/run --format asdf
ulvz-add-phase-arrivals --manifest production_run_manifest.csv --root /path/to/production-root --format asdf
ulvz-add-phase-arrivals --manifest production_run_manifest.csv --root /path/to/production-root --format asdf --resume
```

常用选项：

```bash
ulvz-add-phase-arrivals /path/to/run --format sac --write-sac-picks
ulvz-add-phase-arrivals /path/to/run --phases P,Pdiff,S,Sdiff,PP,SKS,SS --stf-time-shift-s 3
ulvz-add-phase-arrivals /path/to/run --dry-run
```

`--format auto` 只在 ASDF 或 SAC 中恰有一种存在时选择输入。两者同时存在时必须显式给 `--format asdf` 或 `--format sac`。`--model` 当前固定为 `prem`。

## 时间定义

`CMTSOLUTION + STATIONS` 是唯一 geometry 权威。工具保存 PDE origin、CMTSOLUTION `time shift` 和 centroid 坐标/深度，并使用：

```text
centroid_source_time = PDE_origin_time + CMTSOLUTION_time_shift
base_arrival_time = centroid_source_time + TauP_travel_time
effective_arrival_time = base_arrival_time + stf_time_shift_s
arrival_from_trace_start = effective_arrival_time - actual_trace_starttime
```

`travel_time_s` 仅是 TauP/PREM 传播时间。CMTSOLUTION half duration/数值 STF duration 不会自动改变 arrival。数值 STF 的第一列是物理时间，但本工具不会从 STF start、peak、centroid 或 half duration 猜测整体 shift；只有显式 `--stf-time-shift-s` 会改变 `effective_arrival_time`。卷积后再次运行时，工具总是使用卷积后 waveform 的实际 starttime 重新计算 sample index。

对已经由 `ulvz_stf_convolution` 卷积的 waveform，schema API 不重新运行 TauP，而是保留
`travel_time_s`、base arrival、TauP model、phase/rank、ray parameter 和 source/station geometry，
并以累计 shift 重新派生：

```text
total_stf_time_shift_s = prior_total_stf_time_shift_s + applied_stf_time_shift_s
effective_source_time = centroid_source_time + total_stf_time_shift_s
effective_arrival_time = effective_source_time + travel_time_s
effective_arrival_from_trace_start = effective_arrival_time - actual_output_trace_starttime
```

## 输出与 schema

默认输出到 `<run>/OUTPUT_FILES/`：

- `theoretical_arrivals.csv`：每行是 `trace × requested_phase × TauP arrival`。
- `synthetic.theoretical_arrivals.h5`：小型 **ASDF AuxiliaryData-compatible HDF5 sidecar**，路径为 `AuxiliaryData/TheoreticalArrivals/<NETWORK>_<STATION>/data`。

sidecar 不含 `Waveforms`，不复制 waveform payload，也不应被称为完整 waveform ASDF。`data` 是按 CSV field 顺序的结构化 HDF5 dataset；`parameters` attribute 保存 schema version、field 顺序和 row layout，根 attribute 保存 provenance。`ulvz_phase_arrivals.read_sidecar()` 可从 sidecar 精确重建 CSV 行。

当前 writer 写 schema **1.1.0**，reader 继续读取并规范化 **1.0.0**。v1.1 不改变 v1.0 的
`base_arrival_time_utc`、`travel_time_s`、TauP、phase、rank 或 geometry 语义；它新增
`applied_stf_time_shift_s`、`total_stf_time_shift_s`、`effective_source_time_utc`、实际 output
trace axis 和 `effective_arrival_*` 字段，供派生 waveform 重定时使用。正式 API
`read_annotation()` 接受 CSV-only、HDF5-only 或彼此一致的两者；`derive_convolved_rows()`
只变换已有行、绝不重新计算 TauP；`write_outputs()` 只写新的 v1.1 产物。

公开 Python API 为 `API_VERSION`、`SCHEMA_VERSION`、`CSV_FIELDS`、`TraceAxis`、
`read_annotation()`、`read_csv()`、`read_sidecar()`、`arrival_identity()`、
`derive_convolved_rows()`、`write_outputs()` 与 `retime_sac_primary_picks()`。输入为 v1.0
时 reader 在内存中补齐 v1.1 派生字段；写出新 annotation 时仍保留输入 schema/version 和
base 字段身份，避免将物理传播字段重解释为 STF 坐标。

当 CSV 与 HDF5 同时存在，`read_annotation()` 必须验证两者的规范化行完全一致；只存在其一时
可读取；发现不兼容 schema/API 或不一致产物时应停止，而非静默选择一个来源。

核心字段包括：trace identity/axis、source 与 station 几何、`requested_phase`/`returned_phase`/`status`、`arrival_rank`、`is_primary`、`distance_deg`、`travel_time_s`、base/effective absolute arrival、trace-relative arrival/sample index，以及可用的 ray parameter、takeoff/incident angle。每个请求 phase 没有 TauP arrival 时仍保存 `status=missing` 行；P/Pdiff 与 S/Sdiff 永不合并。

默认拒绝覆盖任一既有输出。`--overwrite` 仅替换 sidecar/CSV，绝不修改原始 waveform 文件。
`--resume` 跳过已有且可读的完整 sidecar/CSV 对；若只存在其中一个产物，会要求用 `--overwrite` 显式修复。

## SAC pick 副本

`--write-sac-picks` 只用于 `--format sac`。它把带 header pick 的 SAC **副本**写入 `<output-dir>/sac_picks/`，保持原始 SAC 只读。只写各 phase 的 earliest primary arrival：`t0=P`、`t1=Pdiff`、`t2=S`、`t3=Sdiff`、`t4=PP`、`t5=SKS`、`t6=SS`，并设置相应 `kt#`。t-slot 相对 SAC reference time；missing phase 保持未定义。完整多 arrival 与 missing/ray 元数据始终以 CSV/sidecar 为准。

`retime_sac_primary_picks()` 仅接受上述正式 primary-row 与 package 定义的 `kt0`–`kt6`
组合，并将 pick 写成输出 SAC reference time 的偏移。它不会把 waveform-relative sample time
写进 SAC header，也不会将任意用户 `t0`–`t9` 认定为理论到时。

## 与 STF convolution 的接入

`ulvz_stf_convolution` 可直接调用上述 API 为派生 SAC/ASDF 写 annotation。它的
`--phase-arrivals-src` 参数可指向本 package 的 `src` 目录，无需自动安装任何第三方依赖：

```bash
ulvz-convolve-stf ... \
  --phase-arrivals-src /path/to/packages/ulvz_phase_arrivals/src
```

派生产物位于 `<output waveform>.theoretical_arrivals/`，其中仍使用正式
`theoretical_arrivals.csv` 与 `synthetic.theoretical_arrivals.h5` 名称；输入 annotation 与
输入 waveform 均只读。

## Whale hook

`Aplus_Whale_production_package/config/production.toml` 的 `[arrival_annotation]` 默认关闭。开启后，controller 只会在 output QC PASS 后运行标注；annotation 失败独立记录，不会改变 output QC PASS、DONE 语义或既有 scratch cleanup。可以随时用 manifest 命令补标，无需 scratch。
