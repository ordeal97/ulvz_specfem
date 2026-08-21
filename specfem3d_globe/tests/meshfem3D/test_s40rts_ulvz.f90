program test_s40rts_ulvz

  use constants, only: DEGREES_TO_RADIANS,EARTH_R,PI_OVER_TWO,myrank
  use model_ulvz_par
  use shared_parameters, only: MODEL,MODEL_NAME

  implicit none

  double precision, parameter :: TOL = 1.d-10
  double precision, parameter :: R_EARTH_ = EARTH_R
  double precision, parameter :: RCMB_ = 3480000.d0
  double precision :: radius,theta,phi,w,dvs,dvp,drho

  call init_mpi()
  call world_rank(myrank)

  if (myrank == 0) print *,'program: test_s40rts_ulvz'

  call test_model_name_suffixes()
  call test_parameter_read_and_broadcast()
  call test_overlay_geometry()
  call test_prem_overlay()

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

  call assert_true('isotropic PREM maps to PREM family', &
                   ulvz_model_family('1d_isotropic_prem') == ULVZ_FAMILY_PREM)
  call assert_true('TISO PREM maps to PREM family', &
                   ulvz_model_family('1d_transversely_isotropic_prem') == ULVZ_FAMILY_PREM)

  end subroutine test_model_name_suffixes

  subroutine test_parameter_read_and_broadcast()

  MODEL_NAME = 's40rts'

  if (myrank == 0) call read_ulvz_parameters('DATA/ulvz_s40rts.par')
  if (myrank /= 0) call reset_ulvz_state()

  call broadcast_ulvz_parameters()

  call assert_true('enabled broadcasts',ULVZ_ENABLED)
  call assert_true('S40RTS background broadcasts',ULVZ_BACKGROUND_FAMILY == ULVZ_FAMILY_S40RTS)
  call assert_close('center latitude',ULVZ_CENTER_LATITUDE_DEGREES,10.d0,TOL)
  call assert_close('center longitude normalized',ULVZ_CENTER_LONGITUDE_DEGREES,-170.d0,TOL)
  call assert_close('thickness',ULVZ_THICKNESS_KM,20.d0,TOL)
  call assert_close('lateral radius',ULVZ_LATERAL_RADIUS_KM,100.d0,TOL)
  call assert_close('lateral taper',ULVZ_LATERAL_TAPER_KM,20.d0,TOL)
  call assert_close('top taper',ULVZ_TOP_TAPER_KM,5.d0,TOL)
  call assert_close('dvs',ULVZ_DVS,-0.2d0,TOL)
  call assert_close('dvp',ULVZ_DVP,-0.1d0,TOL)
  call assert_close('drho',ULVZ_DRHO,0.1d0,TOL)

  end subroutine test_parameter_read_and_broadcast

  subroutine test_overlay_geometry()

  MODEL_NAME = 's40rts'
  ULVZ_ENABLED = .true.
  ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_S40RTS
  ULVZ_CENTER_LATITUDE_DEGREES = 0.d0
  ULVZ_CENTER_LONGITUDE_DEGREES = 0.d0
  ULVZ_THICKNESS_KM = 20.d0
  ULVZ_LATERAL_RADIUS_KM = 100.d0
  ULVZ_LATERAL_TAPER_KM = 20.d0
  ULVZ_TOP_TAPER_KM = 5.d0
  ULVZ_DVS = -0.2d0
  ULVZ_DVP = -0.1d0
  ULVZ_DRHO = 0.1d0
  ULVZ_CENTER_LATITUDE_RADIANS = 0.d0
  ULVZ_CENTER_LONGITUDE_RADIANS = 0.d0

  theta = PI_OVER_TWO
  phi = 0.d0
  radius = (RCMB_ + 1.d0) / R_EARTH_
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_close('center just above CMB has w=1',w,1.d0,TOL)

  dvs = 0.03d0
  dvp = 0.d0
  drho = 0.d0
  call ulvz_apply_s40rts_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('relative overlay composition',dvs,-0.176d0,TOL)

  radius = (RCMB_ + 21000.d0) / R_EARTH_
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_close('above thickness has w=0',w,0.d0,TOL)

  radius = (RCMB_ + 17500.d0) / R_EARTH_
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_true('top taper is continuous inside bounds',w > 0.d0 .and. w < 1.d0)

  radius = (RCMB_ + 1.d0) / R_EARTH_
  phi = (100.d0 / (RCMB_ / 1000.d0)) + 1.d-5
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_close('outside lateral radius has w=0',w,0.d0,TOL)

  phi = (90.d0 / (RCMB_ / 1000.d0))
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_true('lateral taper is continuous inside bounds',w > 0.d0 .and. w < 1.d0)

  ULVZ_LATERAL_TAPER_KM = 0.d0
  ULVZ_TOP_TAPER_KM = 0.d0
  phi = 0.d0
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_close('zero taper does not divide by zero',w,1.d0,TOL)

  ULVZ_DVS = 0.d0
  ULVZ_DVP = 0.d0
  ULVZ_DRHO = 0.d0
  dvs = 0.03d0
  dvp = 0.04d0
  drho = -0.01d0
  call ulvz_apply_s40rts_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('zero dvs unchanged',dvs,0.03d0,TOL)
  call assert_close('zero dvp unchanged',dvp,0.04d0,TOL)
  call assert_close('zero drho unchanged',drho,-0.01d0,TOL)

  ULVZ_DVS = -0.2d0
  ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_UNSUPPORTED
  MODEL_NAME = 's40rts_paper'
  dvs = 0.03d0
  dvp = 0.04d0
  drho = -0.01d0
  call ulvz_apply_s40rts_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('s40rts_paper skips overlay',dvs,0.03d0,TOL)

  MODEL_NAME = 's40rts'
  ULVZ_ENABLED = .false.
  dvs = 0.03d0
  dvp = 0.04d0
  drho = -0.01d0
  call ulvz_apply_s40rts_overlay(radius,theta,phi,dvs,dvp,drho)
  call assert_close('disabled keeps native dvs',dvs,0.03d0,TOL)
  call assert_close('disabled keeps native dvp',dvp,0.04d0,TOL)
  call assert_close('disabled keeps native drho',drho,-0.01d0,TOL)

  end subroutine test_overlay_geometry

  subroutine test_prem_overlay()

  double precision :: rho,vpv,vph,vsv,vsh,eta_before,eta_after

  MODEL_NAME = '1d_transversely_isotropic_prem'
  ULVZ_ENABLED = .true.
  ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_PREM
  ULVZ_CENTER_LATITUDE_RADIANS = 0.d0
  ULVZ_CENTER_LONGITUDE_RADIANS = 0.d0
  ULVZ_THICKNESS_KM = 20.d0
  ULVZ_LATERAL_RADIUS_KM = 100.d0
  ULVZ_LATERAL_TAPER_KM = 20.d0
  ULVZ_TOP_TAPER_KM = 5.d0
  ULVZ_DVP = -0.1d0
  ULVZ_DVS = -0.2d0
  ULVZ_DRHO = 0.1d0
  theta = PI_OVER_TWO
  phi = 0.d0
  radius = RCMB_ / R_EARTH_
  rho = 5.d0
  vpv = 10.d0
  vph = 11.d0
  vsv = 6.d0
  vsh = 7.d0
  eta_before = 1.3d0
  eta_after = eta_before
  call ulvz_apply_prem_overlay(radius,theta,phi,rho,vpv,vph,vsv,vsh)
  call assert_close('PREM CMB rho ratio',rho,5.5d0,TOL)
  call assert_close('PREM CMB vpv ratio',vpv,9.d0,TOL)
  call assert_close('PREM CMB vph ratio',vph,9.9d0,TOL)
  call assert_close('PREM CMB vsv ratio',vsv,4.8d0,TOL)
  call assert_close('PREM CMB vsh ratio',vsh,5.6d0,TOL)
  call assert_close('PREM eta remains unchanged',eta_after,eta_before,TOL)

  radius = (RCMB_ - 1.d0) / R_EARTH_
  rho = 5.d0
  vpv = 10.d0
  vph = 11.d0
  vsv = 6.d0
  vsh = 7.d0
  call ulvz_apply_prem_overlay(radius,theta,phi,rho,vpv,vph,vsv,vsh)
  call assert_close('PREM below CMB unchanged',rho,5.d0,TOL)

  radius = (RCMB_ + 20000.d0) / R_EARTH_
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_close('PREM top boundary has zero weight',w,0.d0,TOL)
  radius = RCMB_ / R_EARTH_
  phi = 100.d0 / (RCMB_ / 1000.d0)
  w = ulvz_taper_weight(radius,theta,phi)
  call assert_close('PREM lateral boundary has zero weight',w,0.d0,TOL)

  end subroutine test_prem_overlay

  subroutine reset_ulvz_state()

  ULVZ_ENABLED = .true.
  ULVZ_CENTER_LATITUDE_DEGREES = -999.d0
  ULVZ_CENTER_LONGITUDE_DEGREES = -999.d0
  ULVZ_THICKNESS_KM = -999.d0
  ULVZ_LATERAL_RADIUS_KM = -999.d0
  ULVZ_LATERAL_TAPER_KM = -999.d0
  ULVZ_TOP_TAPER_KM = -999.d0
  ULVZ_DVS = -999.d0
  ULVZ_DVP = -999.d0
  ULVZ_DRHO = -999.d0
  ULVZ_CENTER_LATITUDE_RADIANS = -999.d0
  ULVZ_CENTER_LONGITUDE_RADIANS = -999.d0

  end subroutine reset_ulvz_state

end program test_s40rts_ulvz
