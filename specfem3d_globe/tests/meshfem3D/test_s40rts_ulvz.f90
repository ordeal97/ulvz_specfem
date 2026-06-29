program test_s40rts_ulvz

  use constants, only: DEGREES_TO_RADIANS,EARTH_R,PI_OVER_TWO,myrank
  use model_s40rts_par
  use shared_parameters, only: MODEL,MODEL_NAME

  implicit none

  double precision, parameter :: TOL = 1.d-10
  double precision, parameter :: R_EARTH_ = EARTH_R
  double precision, parameter :: RCMB_ = 3480000.d0
  double precision :: radius,theta,phi,w,dvs,dvp,drho
  double precision, external :: s40rts_ulvz_taper_weight

  call init_mpi()
  call world_rank(myrank)

  if (myrank == 0) print *,'program: test_s40rts_ulvz'

  call test_model_name_suffixes()
  call test_parameter_read_and_broadcast()
  call test_overlay_geometry()

  if (myrank == 0) print *,'test_s40rts_ulvz done successfully'

  call finalize_mpi()

contains

  subroutine assert_close(name,value,expected,tol)

  character(len=*), intent(in) :: name
  double precision, intent(in) :: value,expected,tol

  if (dabs(value - expected) > tol) then
    print *,'FAILED: ',trim(name),' value=',value,' expected=',expected
    stop 1
  endif

  end subroutine assert_close

  subroutine assert_true(name,value)

  character(len=*), intent(in) :: name
  logical, intent(in) :: value

  if (.not. value) then
    print *,'FAILED: ',trim(name)
    stop 1
  endif

  end subroutine assert_true

  subroutine test_model_name_suffixes()

  MODEL = 's40rts_crust1.0_AIC'
  call get_model_parameters_flags()
  call assert_true('s40rts_crust1.0_AIC maps to s40rts',trim(MODEL_NAME) == 's40rts')

  MODEL = 's40rts_paper'
  call get_model_parameters_flags()
  call assert_true('s40rts_paper remains separate',trim(MODEL_NAME) == 's40rts_paper')

  end subroutine test_model_name_suffixes

  subroutine test_parameter_read_and_broadcast()

  MODEL_NAME = 's40rts'

  if (myrank == 0) then
    call read_ulvz_s40rts_parameters()
  else
    call reset_ulvz_state()
  endif

  call broadcast_ulvz_s40rts_parameters()

  call assert_true('enabled broadcasts',S40RTS_ULVZ_ENABLED)
  call assert_close('center latitude',S40RTS_ULVZ_CENTER_LATITUDE_DEGREES,10.d0,TOL)
  call assert_close('center longitude normalized',S40RTS_ULVZ_CENTER_LONGITUDE_DEGREES,-170.d0,TOL)
  call assert_close('thickness',S40RTS_ULVZ_THICKNESS_KM,20.d0,TOL)
  call assert_close('lateral radius',S40RTS_ULVZ_LATERAL_RADIUS_KM,100.d0,TOL)
  call assert_close('lateral taper',S40RTS_ULVZ_LATERAL_TAPER_KM,20.d0,TOL)
  call assert_close('top taper',S40RTS_ULVZ_TOP_TAPER_KM,5.d0,TOL)
  call assert_close('dvs',S40RTS_ULVZ_DVS,-0.2d0,TOL)
  call assert_close('dvp',S40RTS_ULVZ_DVP,-0.1d0,TOL)
  call assert_close('drho',S40RTS_ULVZ_DRHO,0.1d0,TOL)

  end subroutine test_parameter_read_and_broadcast

  subroutine test_overlay_geometry()

  MODEL_NAME = 's40rts'
  S40RTS_ULVZ_ENABLED = .true.
  S40RTS_ULVZ_CENTER_LATITUDE_DEGREES = 0.d0
  S40RTS_ULVZ_CENTER_LONGITUDE_DEGREES = 0.d0
  S40RTS_ULVZ_THICKNESS_KM = 20.d0
  S40RTS_ULVZ_LATERAL_RADIUS_KM = 100.d0
  S40RTS_ULVZ_LATERAL_TAPER_KM = 20.d0
  S40RTS_ULVZ_TOP_TAPER_KM = 5.d0
  S40RTS_ULVZ_DVS = -0.2d0
  S40RTS_ULVZ_DVP = -0.1d0
  S40RTS_ULVZ_DRHO = 0.1d0
  S40RTS_ULVZ_CENTER_LATITUDE_RADIANS = 0.d0
  S40RTS_ULVZ_CENTER_LONGITUDE_RADIANS = 0.d0

  theta = PI_OVER_TWO
  phi = 0.d0
  radius = (RCMB_ + 1.d0) / R_EARTH_
  w = s40rts_ulvz_taper_weight(radius,theta,phi)
  call assert_close('center just above CMB has w=1',w,1.d0,TOL)

  dvs = 0.03d0
  dvp = 0.d0
  drho = 0.d0
  call s40rts_apply_ulvz_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('relative overlay composition',dvs,-0.176d0,TOL)

  radius = (RCMB_ + 21000.d0) / R_EARTH_
  w = s40rts_ulvz_taper_weight(radius,theta,phi)
  call assert_close('above thickness has w=0',w,0.d0,TOL)

  radius = (RCMB_ + 17500.d0) / R_EARTH_
  w = s40rts_ulvz_taper_weight(radius,theta,phi)
  call assert_true('top taper is continuous inside bounds',w > 0.d0 .and. w < 1.d0)

  radius = (RCMB_ + 1.d0) / R_EARTH_
  phi = (100.d0 / (RCMB_ / 1000.d0)) + 1.d-5
  w = s40rts_ulvz_taper_weight(radius,theta,phi)
  call assert_close('outside lateral radius has w=0',w,0.d0,TOL)

  phi = (90.d0 / (RCMB_ / 1000.d0))
  w = s40rts_ulvz_taper_weight(radius,theta,phi)
  call assert_true('lateral taper is continuous inside bounds',w > 0.d0 .and. w < 1.d0)

  S40RTS_ULVZ_LATERAL_TAPER_KM = 0.d0
  S40RTS_ULVZ_TOP_TAPER_KM = 0.d0
  phi = 0.d0
  w = s40rts_ulvz_taper_weight(radius,theta,phi)
  call assert_close('zero taper does not divide by zero',w,1.d0,TOL)

  S40RTS_ULVZ_DVS = 0.d0
  S40RTS_ULVZ_DVP = 0.d0
  S40RTS_ULVZ_DRHO = 0.d0
  dvs = 0.03d0
  dvp = 0.04d0
  drho = -0.01d0
  call s40rts_apply_ulvz_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('zero dvs unchanged',dvs,0.03d0,TOL)
  call assert_close('zero dvp unchanged',dvp,0.04d0,TOL)
  call assert_close('zero drho unchanged',drho,-0.01d0,TOL)

  S40RTS_ULVZ_DVS = -0.2d0
  MODEL_NAME = 's40rts_paper'
  dvs = 0.03d0
  dvp = 0.04d0
  drho = -0.01d0
  call s40rts_apply_ulvz_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('s40rts_paper skips overlay',dvs,0.03d0,TOL)

  MODEL_NAME = 's40rts'
  S40RTS_ULVZ_ENABLED = .false.
  dvs = 0.03d0
  dvp = 0.04d0
  drho = -0.01d0
  call s40rts_apply_ulvz_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('disabled keeps native dvs',dvs,0.03d0,TOL)
  call assert_close('disabled keeps native dvp',dvp,0.04d0,TOL)
  call assert_close('disabled keeps native drho',drho,-0.01d0,TOL)

  end subroutine test_overlay_geometry

  subroutine reset_ulvz_state()

  S40RTS_ULVZ_ENABLED = .true.
  S40RTS_ULVZ_CENTER_LATITUDE_DEGREES = -999.d0
  S40RTS_ULVZ_CENTER_LONGITUDE_DEGREES = -999.d0
  S40RTS_ULVZ_THICKNESS_KM = -999.d0
  S40RTS_ULVZ_LATERAL_RADIUS_KM = -999.d0
  S40RTS_ULVZ_LATERAL_TAPER_KM = -999.d0
  S40RTS_ULVZ_TOP_TAPER_KM = -999.d0
  S40RTS_ULVZ_DVS = -999.d0
  S40RTS_ULVZ_DVP = -999.d0
  S40RTS_ULVZ_DRHO = -999.d0
  S40RTS_ULVZ_CENTER_LATITUDE_RADIANS = -999.d0
  S40RTS_ULVZ_CENTER_LONGITUDE_RADIANS = -999.d0

  end subroutine reset_ulvz_state

end program test_s40rts_ulvz
