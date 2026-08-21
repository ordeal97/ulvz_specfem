# ulvz-stf-convolution

独立的、`dt` 感知的线性卷积工具，用于把震源 moment-rate function
施加到 SPECFEM 基础波形。它不依赖本项目的任何其他 Python 包，也不需要
SPECFEM 运行时；SPECFEM 源码仅用于其 `fortran` 兼容模式的行为基准。

对于希望改变震源持续时间的合成波形，应从 `half duration = 0` 所生成的
基础波形开始。已经以非零 half duration 运行过 solver 的波形已经含有
solver STF；再卷积会把两个 STF 相乘，而不是替换原来的 STF。

## 安装与测试

从此目录单独安装：

```bash
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python -m pip install -e '.[sac,asdf,test]'
/import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python -m pytest -q
ulvz-convolve-stf --help
```

核心依赖是 NumPy 和 SciPy。SAC 是可选功能，依赖 ObsPy；ASDF 是可选功能，
依赖 h5py。若未安装相应 extra，ASCII 和数值 STF 功能仍可用，SAC/ASDF 操作
会明确报错。

## 不安装直接使用

无需执行 `pip install`。在本 package 根目录运行时，将 `src` 加入
`PYTHONPATH`，并通过模块入口调用：

```bash
cd /import/freenas-m-01-seismology/xjiang/ulvz_specfem/packages/ulvz_stf_convolution
PYTHONPATH=src /import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m ulvz_stf_convolution --help
```

例如，直接处理单个 ASCII 波形：

```bash
cd /import/freenas-m-01-seismology/xjiang/ulvz_specfem/packages/ulvz_stf_convolution
PYTHONPATH=src /import/freenas-m-01-seismology/xjiang/software/anaconda3/envs/ulvz-specfem/bin/python \
  -m ulvz_stf_convolution \
  --input OUTPUT_FILES/XX.STA..BHZ.sem.ascii \
  --output results/XX.STA..BHZ.gaussian.sem.ascii \
  --stf-kind gaussian --half-duration 3.1 --mode same
```

此方式不会生成安装后的 `ulvz-convolve-stf` 命令；请始终使用
`python -m ulvz_stf_convolution`。运行环境仍须已有 NumPy 和 SciPy；使用 SAC
输入或输出时还须已有 ObsPy，使用 ASDF 输入或输出时还须已有 h5py。

## 输入、输出与安全性

ASCII 输入/输出是两列 `time_seconds amplitude`。时间必须有限、严格递增且
均匀。SAC 输入/输出使用 ObsPy 的 binary SAC reader/writer；常见的
`*.sem.sac` 可直接传给 `--input`。默认拒绝覆盖已有输出，并且始终拒绝令
输出与输入是同一文件。`--dry-run` 只验证并报告，不写文件。

单个 ASCII 例子：

```bash
ulvz-convolve-stf --input OUTPUT_FILES/XX.STA..BHZ.sem.ascii \
  --output results/XX.STA..BHZ.gaussian.sem.ascii \
  --stf-kind gaussian --half-duration 3.1 --mode same
```

单个 SAC 例子：

```bash
ulvz-convolve-stf --input OUTPUT_FILES/XX.STA..BHZ.sem.sac \
  --output results/XX.STA..BHZ.gaussian.sem.sac \
  --input-format sac --output-format sac --stf-kind gaussian \
  --half-duration 3.1 --mode full
```

SAC `same` 保持原绝对开始时间和 `b`。`full` 保留原 reference time，并以
新输出的开始偏移更新 `b`；写出后工具会重新读取并核验 `starttime`、
`b`、`e`、`delta`、`npts` 和数据。

### SPECFEM ASDF 整文件输入/输出

当 `Par_file` 启用 `OUTPUT_SEISMOS_ASDF = .true.` 时，SPECFEM 会写出
`OUTPUT_FILES/synthetic.h5`。本包将该文件作为一个完整单位处理：读取
`/Waveforms` 下全部台站和分量、逐条应用同一 STF，并写出新的完整 ASDF 文件。
QuakeML、StationXML、AuxiliaryData、Provenance、根/组属性及其他非波形数据会从
输入复制到输出；输入文件绝不会被修改。

```bash
ulvz-convolve-stf --input OUTPUT_FILES/synthetic.h5 \
  --output results/synthetic.gaussian.h5 \
  --input-format asdf --output-format asdf \
  --stf-kind gaussian --half-duration 3.1 --mode same
```

ASDF `same` 保留每条 waveform 的 dataset 名称、`starttime` 和样点数。`full`
及 `fortran` 若改变记录长度或起点，会同步更新 dataset 的 `starttime` 属性和
SPECFEM waveform 名称中的起止时间（名称本身只有秒级精度，亚秒级变化以属性为准）。
仅支持 SPECFEM `synthetic.h5` 的 ASDF 1.0
`/Waveforms` 布局；不能与 ASCII/SAC 输入混合在同一命令中。

## 内置 STF 与兼容模式

现代 `gaussian` 使用

```text
s(t) = a / sqrt(pi) * exp(-(a t)^2),  a = 1.628 / H
```

并在离散网格的 `[-ceil(1.5H/dt) dt, +ceil(1.5H/dt) dt]` 截断后按时间积分
重新归一化为 1。`triangle` 复现参考 Fortran 工具的三角函数采样定义。

`--mode fortran`（或 `--compat fortran`）专用于复现实用程序
`convolve_source_timefunction.f90`：Gaussian 保留其 ±1.5H 截断和未重新
归一化的离散振幅；triangle 保留其 `ceil(H/dt)` 网格、端点和删去最后
`N+1` 个样点的行为。这个兼容模式只支持这两种内置 STF，不支持时间平移或
数值 STF，也不应被误当成现代 `same`/`full` 输出。

## 自定义数值 STF

文件必须是两列：

```text
time_seconds amplitude
```

其中 `t=0` 是卷积零点。时间不必均匀，但必须有限且严格递增；默认用真实
时间坐标的梯形积分归一化：`s_norm=s/integral(s dt)`。允许负振幅；积分为零
或接近零时会停止。`--no-normalize` 可保留用户振幅标度，但仍会拒绝不稳定的
零积分 STF。

目标网格永远相对 `t=0` 定义：
`j_min=floor(t_min/dt)`、`j_max=ceil(t_max/dt)`、`t_j=j*dt`，范围外补零。
`--stf-time-shift` 使用插值；正值表示延迟，不会通过整数取整移动样点。对
比波形更细的 STF，工具先在 t=0 对齐的细网格作 PCHIP 重建，再以 FIR
`resample_poly` 低通/降采样，并重新检查、归一化面积。输入最大空缺超过
`4*dt` 时拒绝；介于 `dt` 与 `4*dt` 时需要显式 `--allow-coarse-stf`，并在
报告中给出不能恢复带宽的警告。

例子：

```bash
ulvz-convolve-stf --input base.sem.ascii --output results/custom.sem.ascii \
  --stf-kind numeric --stf-file my_moment_rate.txt --stf-time-shift 0.037 \
  --mode full --method auto
```

每次运行在 stderr 输出 JSON 摘要：波形 `dt/npts`、STF 原始和归一化积分、
STF 时间范围、重采样方式与警告、卷积模式、最终实际使用的 `direct` 或 `fft`
以及输出路径。

## `same`、`full` 与单位

实现的离散近似为

```text
y[n] = dt * sum_k x[k] s[n-k]
```

`dt` 仅乘一次。`full` 保留完整线性卷积，输出起点是输入起点加 STF 的实际
网格起点；`same` 保留输入时间范围和样点数，裁剪依据 STF 的坐标索引，因而
能正确处理负时间或非对称 STF，不做居中猜测。面积归一化 STF 保持波形单位和
近似低频振幅尺度。

## 限制与验证边界

本包不接收任意解析函数或多列格式；任意用户 STF 必须先提供为两列数值
moment-rate 文件。它不执行 deconvolution，也不证明“后处理卷积”等价于某个
solver 配置。测试包含小型、确定性的 Python/Fortran 对照；这只验证参考工具
的离散行为，不是 A/B SPECFEM 模拟等价性验证。

详细 CLI 参数见 [CLI reference](docs/cli_reference.md)。
