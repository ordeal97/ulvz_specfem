!=====================================================================
! Runtime analytical CMB ULVZ shared by supported mantle backgrounds.
!=====================================================================

  module model_ulvz_par

  implicit none

  integer, parameter :: ULVZ_FAMILY_UNSUPPORTED = 0
  integer, parameter :: ULVZ_FAMILY_PREM = 1
  integer, parameter :: ULVZ_FAMILY_S40RTS = 2

  logical :: ULVZ_CONFIG_PRESENT = .false.
  logical :: ULVZ_ENABLED = .false.
  integer :: ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_UNSUPPORTED
  double precision :: ULVZ_CENTER_LATITUDE_DEGREES = 0.d0
  double precision :: ULVZ_CENTER_LONGITUDE_DEGREES = 0.d0
  double precision :: ULVZ_THICKNESS_KM = 0.d0
  double precision :: ULVZ_LATERAL_RADIUS_KM = 0.d0
  double precision :: ULVZ_LATERAL_TAPER_KM = 0.d0
  double precision :: ULVZ_TOP_TAPER_KM = 0.d0
  double precision :: ULVZ_DVS = 0.d0
  double precision :: ULVZ_DVP = 0.d0
  double precision :: ULVZ_DRHO = 0.d0
  double precision :: ULVZ_CENTER_LATITUDE_RADIANS = 0.d0
  double precision :: ULVZ_CENTER_LONGITUDE_RADIANS = 0.d0

  contains

  integer function ulvz_model_family(model_name)

  character(len=*), intent(in) :: model_name

  ulvz_model_family = ULVZ_FAMILY_UNSUPPORTED
  if (ulvz_equal_ignore_case(model_name,'1d_isotropic_prem') .or. &
      ulvz_equal_ignore_case(model_name,'1d_transversely_isotropic_prem')) then
    ulvz_model_family = ULVZ_FAMILY_PREM
  else if (ulvz_equal_ignore_case(model_name,'s40rts')) then
    ulvz_model_family = ULVZ_FAMILY_S40RTS
  endif

  end function ulvz_model_family

!----------------------------------

  subroutine ulvz_initialize()

  use constants, only: myrank

  implicit none

  character(len=*), parameter :: ULVZ_FILE = 'DATA/ulvz_s40rts.par'
  logical :: exists

  exists = .false.
  if (myrank == 0) inquire(file=ULVZ_FILE,exist=exists)
  call bcast_all_singlel(exists)

  ULVZ_CONFIG_PRESENT = exists
  if (.not. exists) then
    ULVZ_ENABLED = .false.
    ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_UNSUPPORTED
    return
  endif

  if (myrank == 0) call read_ulvz_parameters(ULVZ_FILE)
  call broadcast_ulvz_parameters()

  end subroutine ulvz_initialize

!----------------------------------

  subroutine read_ulvz_parameters(filename)

  use constants, only: DEGREES_TO_RADIANS,IMAIN,myrank
  use shared_parameters, only: MODEL_NAME

  implicit none

  character(len=*), intent(in) :: filename
  character(len=64) :: background_model
  integer :: actual_family,ier

  call check_ulvz_parameter_file_keys(filename)

  call param_open(filename,len(filename),ier)
  if (ier /= 0) call exit_MPI(myrank,'Error opening '//trim(filename))

  call read_value_string(background_model,'BACKGROUND_MODEL',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading BACKGROUND_MODEL in '//trim(filename))
  call read_value_logical(ULVZ_ENABLED,'ENABLED',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading ENABLED in '//trim(filename))
  call read_value_double_precision(ULVZ_CENTER_LATITUDE_DEGREES,'CENTER_LATITUDE_DEGREES',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading CENTER_LATITUDE_DEGREES in '//trim(filename))
  call read_value_double_precision(ULVZ_CENTER_LONGITUDE_DEGREES,'CENTER_LONGITUDE_DEGREES',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading CENTER_LONGITUDE_DEGREES in '//trim(filename))
  call read_value_double_precision(ULVZ_THICKNESS_KM,'THICKNESS_KM',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading THICKNESS_KM in '//trim(filename))
  call read_value_double_precision(ULVZ_LATERAL_RADIUS_KM,'LATERAL_RADIUS_KM',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading LATERAL_RADIUS_KM in '//trim(filename))
  call read_value_double_precision(ULVZ_LATERAL_TAPER_KM,'LATERAL_TAPER_KM',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading LATERAL_TAPER_KM in '//trim(filename))
  call read_value_double_precision(ULVZ_TOP_TAPER_KM,'TOP_TAPER_KM',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading TOP_TAPER_KM in '//trim(filename))
  call read_value_double_precision(ULVZ_DVS,'DVS',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading DVS in '//trim(filename))
  call read_value_double_precision(ULVZ_DVP,'DVP',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading DVP in '//trim(filename))
  call read_value_double_precision(ULVZ_DRHO,'DRHO',ier)
  if (ier /= 0) call exit_MPI(myrank,'Error reading DRHO in '//trim(filename))
  call close_parameter_file()

  ULVZ_BACKGROUND_FAMILY = ulvz_parse_background_family(background_model)
  actual_family = ulvz_model_family(MODEL_NAME)
  if (actual_family == ULVZ_FAMILY_UNSUPPORTED) &
    call exit_MPI(myrank,'ULVZ parameter file is not supported for MODEL_NAME='//trim(MODEL_NAME))
  if (ULVZ_BACKGROUND_FAMILY /= actual_family) &
    call exit_MPI(myrank,'BACKGROUND_MODEL does not match parsed MODEL_NAME')

  call validate_ulvz_parameters(filename)
  ULVZ_CENTER_LONGITUDE_DEGREES = modulo(ULVZ_CENTER_LONGITUDE_DEGREES + 180.d0,360.d0) - 180.d0
  ULVZ_CENTER_LATITUDE_RADIANS = ULVZ_CENTER_LATITUDE_DEGREES * DEGREES_TO_RADIANS
  ULVZ_CENTER_LONGITUDE_RADIANS = ULVZ_CENTER_LONGITUDE_DEGREES * DEGREES_TO_RADIANS

  write(IMAIN,*) 'ULVZ overlay background/enabled: ',trim(background_model),ULVZ_ENABLED
  call flush_IMAIN()

  end subroutine read_ulvz_parameters

!----------------------------------

  subroutine broadcast_ulvz_parameters()

  use constants, only: DEGREES_TO_RADIANS

  implicit none

  double precision :: params(9)

  params(1) = ULVZ_CENTER_LATITUDE_DEGREES
  params(2) = ULVZ_CENTER_LONGITUDE_DEGREES
  params(3) = ULVZ_THICKNESS_KM
  params(4) = ULVZ_LATERAL_RADIUS_KM
  params(5) = ULVZ_LATERAL_TAPER_KM
  params(6) = ULVZ_TOP_TAPER_KM
  params(7) = ULVZ_DVS
  params(8) = ULVZ_DVP
  params(9) = ULVZ_DRHO
  call bcast_all_singlel(ULVZ_ENABLED)
  call bcast_all_singlei(ULVZ_BACKGROUND_FAMILY)
  call bcast_all_dp(params,9)

  ULVZ_CENTER_LATITUDE_DEGREES = params(1)
  ULVZ_CENTER_LONGITUDE_DEGREES = params(2)
  ULVZ_THICKNESS_KM = params(3)
  ULVZ_LATERAL_RADIUS_KM = params(4)
  ULVZ_LATERAL_TAPER_KM = params(5)
  ULVZ_TOP_TAPER_KM = params(6)
  ULVZ_DVS = params(7)
  ULVZ_DVP = params(8)
  ULVZ_DRHO = params(9)
  ULVZ_CENTER_LATITUDE_RADIANS = ULVZ_CENTER_LATITUDE_DEGREES * DEGREES_TO_RADIANS
  ULVZ_CENTER_LONGITUDE_RADIANS = ULVZ_CENTER_LONGITUDE_DEGREES * DEGREES_TO_RADIANS

  end subroutine broadcast_ulvz_parameters

!----------------------------------

  subroutine check_ulvz_parameter_file_keys(filename)

  use constants, only: IIN,myrank

  implicit none

  integer, parameter :: NKEYS = 11
  character(len=64), parameter :: required_keys(NKEYS) = (/ character(len=64) :: &
    'BACKGROUND_MODEL','ENABLED','CENTER_LATITUDE_DEGREES','CENTER_LONGITUDE_DEGREES', &
    'THICKNESS_KM','LATERAL_RADIUS_KM','LATERAL_TAPER_KM','TOP_TAPER_KM','DVS','DVP','DRHO' /)
  character(len=*), intent(in) :: filename
  logical :: seen(NKEYS)
  character(len=512) :: line,content
  character(len=128) :: key,value
  integer :: ier,hash_pos,equals_pos,ikey

  seen(:) = .false.
  open(unit=IIN,file=trim(filename),status='old',action='read',iostat=ier)
  if (ier /= 0) call exit_MPI(myrank,'Error opening '//trim(filename))
  do
    read(IIN,'(A)',iostat=ier) line
    if (ier < 0) exit
    if (ier > 0) call exit_MPI(myrank,'Error reading '//trim(filename))
    content = adjustl(line)
    if (len_trim(content) == 0 .or. content(1:1) == '#') cycle
    hash_pos = index(content,'#')
    if (hash_pos > 0) content = content(:hash_pos-1)
    content = adjustl(content)
    if (len_trim(content) == 0) cycle
    equals_pos = index(content,'=')
    if (equals_pos <= 1) call exit_MPI(myrank,'Malformed line in '//trim(filename))
    key = adjustl(content(:equals_pos-1))
    value = adjustl(content(equals_pos+1:))
    if (len_trim(key) == 0 .or. len_trim(value) == 0) call exit_MPI(myrank,'Malformed key/value in '//trim(filename))
    ikey = ulvz_key_index(key,required_keys,NKEYS)
    if (ikey == 0) call exit_MPI(myrank,'Unknown key in '//trim(filename)//': '//trim(key))
    if (seen(ikey)) call exit_MPI(myrank,'Duplicate key in '//trim(filename)//': '//trim(key))
    seen(ikey) = .true.
  enddo
  close(IIN)
  do ikey = 1,NKEYS
    if (.not. seen(ikey)) call exit_MPI(myrank,'Missing key in '//trim(filename)//': '//trim(required_keys(ikey)))
  enddo

  end subroutine check_ulvz_parameter_file_keys

!----------------------------------

  subroutine validate_ulvz_parameters(filename)

  use constants, only: EARTH_R,myrank

  implicit none

  character(len=*), intent(in) :: filename
  double precision, parameter :: RMOHO_ = EARTH_R - 24400.d0
  double precision, parameter :: RCMB_ = 3480000.d0
  double precision :: max_thickness_km

  max_thickness_km = (RMOHO_ - RCMB_) / 1000.d0
  if (.not. ulvz_is_finite(ULVZ_CENTER_LATITUDE_DEGREES) .or. &
      .not. ulvz_is_finite(ULVZ_CENTER_LONGITUDE_DEGREES) .or. &
      .not. ulvz_is_finite(ULVZ_THICKNESS_KM) .or. &
      .not. ulvz_is_finite(ULVZ_LATERAL_RADIUS_KM) .or. &
      .not. ulvz_is_finite(ULVZ_LATERAL_TAPER_KM) .or. &
      .not. ulvz_is_finite(ULVZ_TOP_TAPER_KM) .or. &
      .not. ulvz_is_finite(ULVZ_DVS) .or. .not. ulvz_is_finite(ULVZ_DVP) .or. &
      .not. ulvz_is_finite(ULVZ_DRHO)) call exit_MPI(myrank,'Non-finite ULVZ value in '//trim(filename))
  if (ULVZ_CENTER_LATITUDE_DEGREES < -90.d0 .or. ULVZ_CENTER_LATITUDE_DEGREES > 90.d0) &
    call exit_MPI(myrank,'CENTER_LATITUDE_DEGREES must be in [-90,90]')
  if (ULVZ_THICKNESS_KM <= 0.d0 .or. ULVZ_THICKNESS_KM > max_thickness_km) &
    call exit_MPI(myrank,'THICKNESS_KM must fit inside the mantle above the CMB')
  if (ULVZ_LATERAL_RADIUS_KM <= 0.d0) call exit_MPI(myrank,'LATERAL_RADIUS_KM must be > 0')
  if (ULVZ_LATERAL_TAPER_KM < 0.d0 .or. ULVZ_LATERAL_TAPER_KM > ULVZ_LATERAL_RADIUS_KM) &
    call exit_MPI(myrank,'LATERAL_TAPER_KM must be in [0,LATERAL_RADIUS_KM]')
  if (ULVZ_TOP_TAPER_KM < 0.d0 .or. ULVZ_TOP_TAPER_KM > ULVZ_THICKNESS_KM) &
    call exit_MPI(myrank,'TOP_TAPER_KM must be in [0,THICKNESS_KM]')
  if (ULVZ_DVS <= -1.d0 .or. ULVZ_DVP <= -1.d0 .or. ULVZ_DRHO <= -1.d0) &
    call exit_MPI(myrank,'DVS, DVP, and DRHO must be > -1')

  end subroutine validate_ulvz_parameters

!----------------------------------

  double precision function ulvz_taper_weight(radius,theta,phi)

  use constants, only: EARTH_R,PI,PI_OVER_TWO,TWO_PI

  implicit none

  double precision, intent(in) :: radius,theta,phi
  double precision, parameter :: RCMB_ = 3480000.d0
  double precision :: lat,lon,height_above_cmb_km,cosang,lateral_distance_km
  double precision :: lateral_weight,top_weight,x,y

  ulvz_taper_weight = 0.d0
  if (.not. ULVZ_ENABLED) return
  lat = PI_OVER_TWO - theta
  lon = modulo(phi + PI,TWO_PI) - PI
  height_above_cmb_km = (radius * EARTH_R - RCMB_) / 1000.d0
  if (height_above_cmb_km < 0.d0 .or. height_above_cmb_km > ULVZ_THICKNESS_KM) return
  cosang = dsin(lat) * dsin(ULVZ_CENTER_LATITUDE_RADIANS) + &
           dcos(lat) * dcos(ULVZ_CENTER_LATITUDE_RADIANS) * dcos(lon - ULVZ_CENTER_LONGITUDE_RADIANS)
  cosang = max(-1.d0,min(1.d0,cosang))
  lateral_distance_km = (RCMB_ / 1000.d0) * dacos(cosang)
  if (lateral_distance_km > ULVZ_LATERAL_RADIUS_KM) return
  if (ULVZ_LATERAL_TAPER_KM == 0.d0 .or. &
      lateral_distance_km <= ULVZ_LATERAL_RADIUS_KM - ULVZ_LATERAL_TAPER_KM) then
    lateral_weight = 1.d0
  else
    x = (lateral_distance_km - (ULVZ_LATERAL_RADIUS_KM - ULVZ_LATERAL_TAPER_KM)) / ULVZ_LATERAL_TAPER_KM
    lateral_weight = 0.5d0 * (1.d0 + dcos(PI * x))
  endif
  if (ULVZ_TOP_TAPER_KM == 0.d0 .or. height_above_cmb_km <= ULVZ_THICKNESS_KM - ULVZ_TOP_TAPER_KM) then
    top_weight = 1.d0
  else
    y = (height_above_cmb_km - (ULVZ_THICKNESS_KM - ULVZ_TOP_TAPER_KM)) / ULVZ_TOP_TAPER_KM
    top_weight = 0.5d0 * (1.d0 + dcos(PI * y))
  endif
  ulvz_taper_weight = lateral_weight * top_weight

  end function ulvz_taper_weight

!----------------------------------

  subroutine ulvz_apply_s40rts_overlay(radius,theta,phi,dvs,dvp,drho)

  implicit none

  double precision, intent(in) :: radius,theta,phi
  double precision, intent(inout) :: dvs,dvp,drho
  double precision :: w

  if (ULVZ_BACKGROUND_FAMILY /= ULVZ_FAMILY_S40RTS) return
  if (.not. ULVZ_ENABLED) return
  if (ULVZ_DVS == 0.d0 .and. ULVZ_DVP == 0.d0 .and. ULVZ_DRHO == 0.d0) return
  w = ulvz_taper_weight(radius,theta,phi)
  if (w <= 0.d0) return
  dvs = (1.d0 + dvs) * (1.d0 + w * ULVZ_DVS) - 1.d0
  dvp = (1.d0 + dvp) * (1.d0 + w * ULVZ_DVP) - 1.d0
  drho = (1.d0 + drho) * (1.d0 + w * ULVZ_DRHO) - 1.d0

  end subroutine ulvz_apply_s40rts_overlay

!----------------------------------

  subroutine ulvz_apply_prem_overlay(radius,theta,phi,rho,vpv,vph,vsv,vsh)

  implicit none

  double precision, intent(in) :: radius,theta,phi
  double precision, intent(inout) :: rho,vpv,vph,vsv,vsh
  double precision :: w

  if (ULVZ_BACKGROUND_FAMILY /= ULVZ_FAMILY_PREM) return
  if (.not. ULVZ_ENABLED) return
  w = ulvz_taper_weight(radius,theta,phi)
  if (w <= 0.d0) return
  rho = rho * (1.d0 + w * ULVZ_DRHO)
  vpv = vpv * (1.d0 + w * ULVZ_DVP)
  vph = vph * (1.d0 + w * ULVZ_DVP)
  vsv = vsv * (1.d0 + w * ULVZ_DVS)
  vsh = vsh * (1.d0 + w * ULVZ_DVS)

  end subroutine ulvz_apply_prem_overlay

!----------------------------------

  integer function ulvz_parse_background_family(background_model)

  use constants, only: myrank

  implicit none

  character(len=*), intent(in) :: background_model

  if (ulvz_equal_ignore_case(background_model,'PREM')) then
    ulvz_parse_background_family = ULVZ_FAMILY_PREM
  else if (ulvz_equal_ignore_case(background_model,'S40RTS')) then
    ulvz_parse_background_family = ULVZ_FAMILY_S40RTS
  else
    call exit_MPI(myrank,'BACKGROUND_MODEL must be PREM or S40RTS')
  endif

  end function ulvz_parse_background_family

!----------------------------------

  integer function ulvz_key_index(key,keys,nkeys)

  implicit none

  integer, intent(in) :: nkeys
  character(len=*), intent(in) :: key,keys(nkeys)
  integer :: ikey

  ulvz_key_index = 0
  do ikey = 1,nkeys
    if (ulvz_equal_ignore_case(key,keys(ikey))) then
      ulvz_key_index = ikey
      return
    endif
  enddo

  end function ulvz_key_index

!----------------------------------

  logical function ulvz_equal_ignore_case(a,b)

  implicit none

  character(len=*), intent(in) :: a,b
  integer :: i,la,lb
  character :: ca,cb

  la = len_trim(a)
  lb = len_trim(b)
  if (la /= lb) then
    ulvz_equal_ignore_case = .false.
    return
  endif
  do i = 1,la
    ca = a(i:i)
    cb = b(i:i)
    if (lge(ca,'A') .and. lle(ca,'Z')) ca = achar(iachar(ca) + iachar('a') - iachar('A'))
    if (lge(cb,'A') .and. lle(cb,'Z')) cb = achar(iachar(cb) + iachar('a') - iachar('A'))
    if (ca /= cb) then
      ulvz_equal_ignore_case = .false.
      return
    endif
  enddo
  ulvz_equal_ignore_case = .true.

  end function ulvz_equal_ignore_case

!----------------------------------

  logical function ulvz_is_finite(value)

  implicit none

  double precision, intent(in) :: value

  ulvz_is_finite = (value == value) .and. (dabs(value) < huge(value))

  end function ulvz_is_finite

  end module model_ulvz_par
