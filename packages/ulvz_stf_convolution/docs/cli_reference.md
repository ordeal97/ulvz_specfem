# CLI reference

```text
ulvz-convolve-stf --input PATH [PATH ...] --output PATH \
  --stf-kind gaussian|triangle|numeric \
  [--half-duration H | --stf-file FILE] [options]
```

| 选项 | 说明 |
| --- | --- |
| `--input` | 一个文件、多个文件或引用 shell 的 glob（例如 `'OUTPUT/*.sem.sac'`）。 |
| `--output` | 单输入时为文件；多输入时为输出目录。 |
| `--input-format`, `--output-format` | `auto`、`ascii`、`sac` 或 `asdf`；auto 以 `.sac` 识别 SAC、以 `.h5`/`.asdf` 识别 ASDF。 |
| `--stf-kind` | `gaussian`、`triangle` 或 `numeric`。 |
| `--half-duration` | 内置 STF 必需，单位秒。 |
| `--stf-file` | 数值 STF 必需：两列 seconds/amplitude。 |
| `--stf-time-shift` | 秒，正数延迟 STF；Fortran 兼容模式不可用。 |
| `--phase-arrivals-src` | 可选的 `ulvz_phase_arrivals` `src` 目录；仅在检测到正式 theoretical-arrivals metadata 时使用。 |
| `--mode` | `same`、`full` 或 `fortran`。 |
| `--compat fortran` | `--mode fortran` 的别名。 |
| `--method` | `auto`、`direct`、`fft`；auto 会先选择并记录实际方法。 |
| `--no-normalize` | 不对数值 STF 自动面积归一化。 |
| `--allow-coarse-stf` | 明确允许 `dt < max_gap <= 4*dt` 的插值，附带带宽丢失警告。 |
| `--overwrite` | 允许覆盖已有输出（但仍禁止覆盖输入）。 |
| `--dry-run` | 只读取、验证、卷积和报告，不创建输出。 |
| `--report FILE` | 写 JSON metadata；不能和 `--dry-run` 同用。 |

## Formal theoretical-arrivals propagation

对于 SAC/ASDF，工具按如下顺序寻找正式 annotation：先查找
`<input waveform>.theoretical_arrivals/`，再查找输入所在目录（SAC pick copy 还会检查其父目录）。
候选目录中的 `theoretical_arrivals.csv`、`synthetic.theoretical_arrivals.h5` 可单独存在；两者都存在
时必须由 `ulvz_phase_arrivals` reader 验证行完全一致。没有 annotation 时，卷积行为与旧版本完全相同。

发现正式 annotation 后，需要 `ulvz_phase_arrivals` API 0.2+。默认从已安装 package 导入；
`--phase-arrivals-src` 可提供其 `src` 目录。没有兼容 API、schema 不兼容或 CSV/HDF5 不一致都会报错，
不会降级为自行解析或重新计算 TauP。

派生 metadata 写入 `<output waveform>.theoretical_arrivals/`。`applied_stf_time_shift_s` 是本次
显式 `--stf-time-shift`；`total_stf_time_shift_s` 供连续 convolution 累计使用。absolute arrival
由 centroid source time、total shift 和既有 `travel_time_s` 计算；`effective_arrival_*` index 则必须
依据实际写出的 output trace `starttime`/sampling rate。`full` 模式尤其不能从输入 index 加
`shift/dt` 推断结果。

SAC 只会更新由正式 sidecar 及 package 定义 phase-slot 共同确认的 primary picks；其 `t0`–`t6`
始终相对输出 SAC reference time，而不是 waveform-relative arrival。

批量 SAC 示例：

```bash
ulvz-convolve-stf --input 'OUTPUT_FILES/*.sem.sac' --output results/stf_sac \
  --input-format sac --output-format sac --stf-kind gaussian --half-duration 3.1
```

SPECFEM ASDF 整文件示例：

```bash
ulvz-convolve-stf --input OUTPUT_FILES/synthetic.h5 --output results/synthetic.convolved.h5 \
  --input-format asdf --output-format asdf --stf-kind gaussian --half-duration 3.1
```

ASDF 输入一次处理该文件 `/Waveforms` 下的全部 trace，不能与 ASCII/SAC 混用。
需要安装 `ulvz-stf-convolution[asdf]`；`--dry-run` 会读取并卷积全部 trace，但不写输出。
