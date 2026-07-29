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
| `--input-format`, `--output-format` | `auto`、`ascii` 或 `sac`；auto 以 `.sac` 后缀识别 SAC。 |
| `--stf-kind` | `gaussian`、`triangle` 或 `numeric`。 |
| `--half-duration` | 内置 STF 必需，单位秒。 |
| `--stf-file` | 数值 STF 必需：两列 seconds/amplitude。 |
| `--stf-time-shift` | 秒，正数延迟 STF；Fortran 兼容模式不可用。 |
| `--mode` | `same`、`full` 或 `fortran`。 |
| `--compat fortran` | `--mode fortran` 的别名。 |
| `--method` | `auto`、`direct`、`fft`；auto 会先选择并记录实际方法。 |
| `--no-normalize` | 不对数值 STF 自动面积归一化。 |
| `--allow-coarse-stf` | 明确允许 `dt < max_gap <= 4*dt` 的插值，附带带宽丢失警告。 |
| `--overwrite` | 允许覆盖已有输出（但仍禁止覆盖输入）。 |
| `--dry-run` | 只读取、验证、卷积和报告，不创建输出。 |
| `--report FILE` | 写 JSON metadata；不能和 `--dry-run` 同用。 |

批量 SAC 示例：

```bash
ulvz-convolve-stf --input 'OUTPUT_FILES/*.sem.sac' --output results/stf_sac \
  --input-format sac --output-format sac --stf-kind gaussian --half-duration 3.1
```
