  # Task 3C: External S40RTS ULVZ Parameter Input Implementation Plan

  ## Summary

  实现一个只由已解析 MODEL_NAME 触发的 S40RTS cylindrical-cap ULVZ overlay。仅当 trim(MODEL_NAME) == 's40rts' 时读
  取、校验、广播 DATA/ulvz_s40rts.par 并在 mantle_s40rts() 末尾叠加 ULVZ；s40rts_paper 完全跳过该逻辑，不要求参数文
  件存在。

  计划修改/新增文件：

  - 修改：specfem3d_globe/src/meshfem3D/model_s40rts.f90
  - 修改：specfem3d_globe/tests/meshfem3D/test_models.makefile，仅添加新测试 target，复用现有测试框架，不新增独立
    Makefile

  - 新增：specfem3d_globe/DATA/ulvz_s40rts.par.example
  - 新增：specfem3d_globe/tests/meshfem3D/test_s40rts_ulvz.f90
  - 新增：specfem3d_globe/tests/meshfem3D/5.test_s40rts_ulvz.sh
  - 新增：docs/task_3c_external_s40rts_ulvz.md

  明确不修改：真实 DATA/ulvz_s40rts.par、S40RTS/P12 系数文件、DATA/Par_file、dispatcher、get_model_parameters、
  setup/constants*、根 Makefile、src/meshfem3D/rules.mk。

  ## Existing Interfaces To Use

  - 参数读取：
      - param_open(filename, len(filename), ier) 可打开任意参数文件；底层 C parser 支持 key = value、忽略空行和 #
        注释。

      - read_value_logical(value_to_read, name, ier)
      - read_value_double_precision(value_to_read, name, ier)
      - close_parameter_file() 调用 param_close()。

  - 结构校验：
      - 现有 parser 不能检测重复 key，也会忽略 malformed 非匹配行；因此新增一个很小的
        check_ulvz_s40rts_parameter_file_keys()，只扫描 key inventory、重复 key、未知 key 和缺失 key，不解析数值。

      - 实际 value parsing 仍全部使用现有 read_value_* routines。

  - MPI 广播：
      - bcast_all_singlel(buffer) 广播 logical scalar。
      - bcast_all_dp(buffer, countval) 广播 double precision array。
      - ULVZ logical 单独广播；9 个 double 参数打包为数组一次广播。

  - MODEL_NAME 来源：
      - get_model_parameters.F90 已将原始 MODEL lower-case、剥离 crust/AIC/ACM 等后缀，并设置 MODEL_NAME =
        trim(MODEL_ROOT)。

      - model_s40rts.f90 当前已 use shared_parameters, only: MODEL_NAME，并用它区分 s40rts_paper scaling；实现只继
        续使用该变量，不重新解析 MODEL。

  ## Implementation Changes

  - 在 model_s40rts_par 中新增并初始化：
    S40RTS_ULVZ_ENABLED = .false.，中心经纬度、厚度、横向半径、lateral/top taper、DVS/DVP/DRHO，以及标准化后的中心
    经纬度 radians。

  - 新增 helper，均放在 model_s40rts.f90：
    read_ulvz_s40rts_parameters()、check_ulvz_s40rts_parameter_file_keys()、validate_ulvz_s40rts_parameters()、
    broadcast_ulvz_s40rts_parameters()、s40rts_ulvz_taper_weight()、s40rts_apply_ulvz_overlay()。

  - 在 model_s40rts_broadcast() 中保持现有顺序：
    native S40RTS/P12 rank-0 read 不变；
    native coefficient/spline broadcasts 不变；
    然后仅当 MODEL_NAME == 's40rts' 时 rank 0 读取/校验 ULVZ 参数、打印简洁 summary，并广播 ULVZ 参数。

  - 对 MODEL_NAME /= 's40rts'：
    不打开 DATA/ulvz_s40rts.par，不广播 ULVZ 参数，不应用 overlay。

  - 在 mantle_s40rts() 中，在 native spline、球谐展开、s40rts/s40rts_paper scaling 全部完成之后，return 之前调用
    overlay。

  - overlay 早返回条件：
    MODEL_NAME /= 's40rts'、.not. S40RTS_ULVZ_ENABLED、w <= 0.d0、三项 perturbation 全为 0.d0。

  - debug：
    内部 logical, parameter :: S40RTS_ULVZ_DEBUG = .false.，配合 saved flag 最多输出一次单点诊断；不加入外部参数文
    件格式。

  ## Geometry And Overlay Formula

  坐标：

  radius = r / EARTH_R
  lat    = PI_OVER_TWO - theta
  lon    = normalized(phi)

  高度与横向距离使用 S40RTS 现有常数：

  height_above_cmb_km = (radius * R_EARTH_ - RCMB_) / 1000.d0

  cosang = sin(lat) * sin(lat0)
         + cos(lat) * cos(lat0) * cos(lon - lon0)

  cosang = max(-1.d0, min(1.d0, cosang))
  lateral_distance_km = (RCMB_ / 1000.d0) * acos(cosang)

  ULVZ volume：

  0 <= height_above_cmb_km <= THICKNESS_KM
  lateral_distance_km <= LATERAL_RADIUS_KM

  Cosine taper：

  lateral_weight = 0 outside radius
  lateral_weight = 1 inside untapered core or when LATERAL_TAPER_KM == 0
  lateral_weight = 0.5 * (1 + cos(PI * x)) across lateral taper

  top_weight = 0 above thickness
  top_weight = 1 below untapered top zone or when TOP_TAPER_KM == 0
  top_weight = 0.5 * (1 + cos(PI * y)) across top taper

  w = lateral_weight * top_weight

  底部不 taper；height_above_cmb_km < 0 时 w = 0。

  Local-native-S40RTS-relative 组合：

  dvs  = (1.d0 + dvs ) * (1.d0 + w * S40RTS_ULVZ_DVS ) - 1.d0
  dvp  = (1.d0 + dvp ) * (1.d0 + w * S40RTS_ULVZ_DVP ) - 1.d0
  drho = (1.d0 + drho) * (1.d0 + w * S40RTS_ULVZ_DRHO) - 1.d0

  ## Validation And Test Plan

  - 参数校验：
    required keys 全部存在且不重复；未知 key 或 malformed non-comment line 失败；
    THICKNESS_KM > 0，LATERAL_RADIUS_KM > 0；
    taper 范围合法；
    DVS/DVP/DRHO > -1；
    latitude 在 [-90, 90]；
    longitude 为有限实数并标准化到 [-180, 180)；
    THICKNESS_KM <= (RMOHO_ - RCMB_) / 1000.d0。

  - 编译前后记录：
    sha256sum DATA/s40rts/S40RTS.dat DATA/s20rts/P12.dat。

  - 编译：
    cd specfem3d_globe && make -j 4 xmeshfem3D。

  - 轻量测试：
    tests/meshfem3D/5.test_s40rts_ulvz.sh 临时在测试目录创建 fixture DATA/ulvz_s40rts.par，不碰项目根真实参数文件。

  - 测试覆盖：
    successful read；
    2 个 MPI rank 参数一致；
    disabled 保持 native perturbations；
    outside w = 0；
    CMB 上方极小正距离中心点 w = 1；
    高于 thickness w = 0；
    lateral/top taper 连续；
    taper width 为 0 不除零；
    三项 perturbation 为 0 不改变 native；
    +0.03, -0.20, w=1 -> -0.176；
    s40rts_crust1.0_AIC -> MODEL_NAME = s40rts 并进入 ULVZ path；
    s40rts_paper -> MODEL_NAME = s40rts_paper 且不读取/不应用；
    coefficient checksums 不变。

  ## Documentation And Completion

  docs/task_3c_external_s40rts_ulvz.md 记录：

  - 所有 changed files；
  - 参数文件格式、key 含义和单位；
  - MODEL_NAME 与原始 MODEL 的区别；
  - 支持的 S40RTS suffix 组合；
  - s40rts_paper 排除原因；
  - parser、校验、广播实现；
  - 坐标、geometry、taper、overlay 公式；
  - 所有 shell commands；
  - git diff --check、编译和测试结果；
  - coefficient checksums；
  - 最终 git status --short；
  - 未解决事项。

  完成时只报告简洁 diff 摘要、编译/测试证据和未解决问题；不运行 full mesh，也不运行 forward simulation。
