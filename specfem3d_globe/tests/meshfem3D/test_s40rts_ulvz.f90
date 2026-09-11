program test_s40rts_ulvz

  use constants, only: myrank,PI_OVER_TWO,DEGREES_TO_RADIANS,EARTH_R
  use model_ulvz_par
  use shared_parameters, only: MODEL_NAME

  implicit none

  double precision, parameter :: TOL = 1.d-12
  double precision, parameter :: RCMB = 3480000.d0
  double precision :: legacy_weight,legacy_values(3),permuted_weight,permuted_values(3)
  double precision :: radius,theta,phi,rho,vpv,vph,vsv,vsh
  integer :: i
  character(len=512) :: fixture_root

  call init_mpi()
  call world_rank(myrank)
  MODEL_NAME = 's40rts'
  fixture_root = 'ulvz_fixtures'
  call get_command_argument(1,fixture_root)
  if(len_trim(fixture_root)==0) fixture_root = 'ulvz_fixtures'

  call load_file('legacy_single_ulvz.par')
  call assert_int('legacy body count',N_ULVZ,1)
  call assert_true('legacy enabled',ULVZ_ENABLED)
  call assert_close('legacy longitude normalized',ULVZ_BODIES(1)%center_longitude_degrees,-170.d0,TOL)
  call point_for_body(ULVZ_BODIES(1),radius,theta,phi)
  legacy_weight = ulvz_taper_weight(radius,theta,phi)
  call s40_values(radius,theta,phi,legacy_values)

  call load_file('multi_ulvz_one.par')
  call assert_int('new one-body count',N_ULVZ,1)
  call assert_close('new one-body weight',ulvz_taper_weight(radius,theta,phi),legacy_weight,TOL)
  call compare_s40('legacy/new one-body equality',radius,theta,phi,legacy_values)

  call load_file('multi_ulvz_zero.par')
  call assert_int('explicit zero count',N_ULVZ,0)
  call assert_true('explicit zero disabled',.not.ULVZ_ENABLED)
  call assert_close('explicit zero weight',ulvz_taper_weight(radius,theta,phi),0.d0,TOL)
  call s40_values(radius,theta,phi,permuted_values)
  call assert_close('explicit zero native dvs',permuted_values(1),.03d0,TOL)
  if(myrank==0) call ulvz_write_provenance('OUTPUT_FILES/zero_second')

  MODEL_NAME = '1d_transversely_isotropic_prem'
  ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_PREM
  rho=5.d0;vpv=10.d0;vph=11.d0;vsv=6.d0;vsh=7.d0
  call ulvz_apply_prem_overlay(radius,theta,phi,rho,vpv,vph,vsv,vsh)
  call assert_close('zero PREM rho unchanged',rho,5.d0,TOL)

  MODEL_NAME = 's40rts'
  call load_file('multi_ulvz_three.par')
  call assert_int('three body count',N_ULVZ,3)
  do i=1,3
    call point_for_body(ULVZ_BODIES(i),radius,theta,phi)
    call assert_true('three-body core point has weight',ulvz_taper_weight(radius,theta,phi)>0.999d0)
    call s40_values(radius,theta,phi,legacy_values)
    call assert_close('three-body dvs',legacy_values(1),(1.d0+.03d0)*(1.d0+ULVZ_BODIES(i)%dvs)-1.d0,TOL)
    call assert_close('three-body dvp',legacy_values(2),(1.d0+.04d0)*(1.d0+ULVZ_BODIES(i)%dvp)-1.d0,TOL)
    call assert_close('three-body drho',legacy_values(3),(.99d0)*(1.d0+ULVZ_BODIES(i)%drho)-1.d0,TOL)
  enddo
  if(myrank==0) call ulvz_write_provenance('OUTPUT_FILES/three_second')
  radius = RCMB/EARTH_R;theta=PI_OVER_TWO;phi=60.d0*DEGREES_TO_RADIANS
  call assert_close('three-body outside weight',ulvz_taper_weight(radius,theta,phi),0.d0,TOL)

  call point_for_body(ULVZ_BODIES(2),radius,theta,phi)
  legacy_weight=ulvz_taper_weight(radius,theta,phi)
  call s40_values(radius,theta,phi,legacy_values)
  call load_file('multi_ulvz_three_permuted.par')
  permuted_weight=ulvz_taper_weight(radius,theta,phi)
  call s40_values(radius,theta,phi,permuted_values)
  call assert_close('permutation weight',permuted_weight,legacy_weight,TOL)
  do i=1,3
    call assert_close('permutation material',permuted_values(i),legacy_values(i),TOL)
  enddo
  call load_file('multi_ulvz_one.par')
  call assert_int('broadcast reinitializes three to one',N_ULVZ,1)

  if(myrank==0) print *,'test_s40rts_ulvz done successfully'
  call finalize_mpi()

contains

  character(len=1024) function fixture(name)
    character(len=*),intent(in)::name
    fixture=trim(fixture_root)//'/'//trim(name)
  end function fixture

  subroutine load_file(name)
    character(len=*),intent(in)::name
    if(myrank==0) call read_ulvz_parameters(fixture(name))
    call broadcast_ulvz_parameters()
  end subroutine load_file

  subroutine point_for_body(body,r,th,ph)
    type(ulvz_body_t),intent(in)::body
    double precision,intent(out)::r,th,ph
    r=(RCMB+1000.d0)/EARTH_R
    th=PI_OVER_TWO-body%center_latitude_degrees*DEGREES_TO_RADIANS
    ph=body%center_longitude_degrees*DEGREES_TO_RADIANS
  end subroutine point_for_body

  subroutine s40_values(r,th,ph,values)
    double precision,intent(in)::r,th,ph
    double precision,intent(out)::values(3)
    values=(/.03d0,.04d0,-.01d0/)
    call ulvz_apply_s40rts_overlay(r,th,ph,values(1),values(2),values(3))
  end subroutine s40_values

  subroutine compare_s40(label,r,th,ph,expected)
    character(len=*),intent(in)::label
    double precision,intent(in)::r,th,ph,expected(3)
    double precision::actual(3)
    integer::j
    call s40_values(r,th,ph,actual)
    do j=1,3
      call assert_close(label,actual(j),expected(j),TOL)
    enddo
  end subroutine compare_s40

  subroutine assert_true(label,ok)
    character(len=*),intent(in)::label
    logical,intent(in)::ok
    if(.not.ok) then
      print *,'ULVZ assertion failed: ',trim(label)
      stop 1
    endif
  end subroutine assert_true

  subroutine assert_int(label,actual,expected)
    character(len=*),intent(in)::label
    integer,intent(in)::actual,expected
    if(actual/=expected) then
      print *,'ULVZ integer assertion failed: ',trim(label)
      stop 1
    endif
  end subroutine assert_int

  subroutine assert_close(label,actual,expected,tolerance)
    character(len=*),intent(in)::label
    double precision,intent(in)::actual,expected,tolerance
    if(abs(actual-expected)>tolerance) then
      print *,'ULVZ numeric assertion failed: ',trim(label)
      stop 1
    endif
  end subroutine assert_close

end program test_s40rts_ulvz
