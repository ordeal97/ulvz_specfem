!=====================================================================
! Runtime analytical CMB ULVZ overlays shared by supported mantle models.
!=====================================================================
  module model_ulvz_par
  implicit none
  integer, parameter :: ULVZ_FAMILY_UNSUPPORTED=0,ULVZ_FAMILY_PREM=1,ULVZ_FAMILY_S40RTS=2
  integer, parameter :: ULVZ_NBODY_FIELDS=9
  double precision, parameter :: ULVZ_RCMB_M=3480000.d0
  type :: ulvz_body_t
    double precision :: center_latitude_degrees=0.d0,center_longitude_degrees=0.d0
    double precision :: thickness_km=0.d0,lateral_radius_km=0.d0,lateral_taper_km=0.d0,top_taper_km=0.d0
    double precision :: dvs=0.d0,dvp=0.d0,drho=0.d0
    double precision :: center_latitude_radians=0.d0,center_longitude_radians=0.d0
  end type ulvz_body_t
  logical :: ULVZ_CONFIG_PRESENT=.false.,ULVZ_ENABLED=.false.
  integer :: ULVZ_BACKGROUND_FAMILY=ULVZ_FAMILY_UNSUPPORTED,N_ULVZ=0
  character(len=16) :: ULVZ_BACKGROUND_MODEL='NONE'
  type(ulvz_body_t), allocatable :: ULVZ_BODIES(:)
  contains

  integer function ulvz_model_family(model_name)
  character(len=*),intent(in)::model_name
  ulvz_model_family=ULVZ_FAMILY_UNSUPPORTED
  if (ulvz_equal_ignore_case(model_name,'1d_isotropic_prem') .or. &
      ulvz_equal_ignore_case(model_name,'1d_transversely_isotropic_prem')) then
    ulvz_model_family=ULVZ_FAMILY_PREM
  else if (ulvz_equal_ignore_case(model_name,'s40rts')) then
    ulvz_model_family=ULVZ_FAMILY_S40RTS
  endif
  end function ulvz_model_family

  subroutine ulvz_initialize()
  use constants,only:myrank
  use shared_parameters,only:MODEL_NAME,OUTPUT_FILES
  character(len=*),parameter::ULVZ_FILE='DATA/ulvz_s40rts.par'
  logical::exists
  exists=.false.;if(myrank==0) inquire(file=ULVZ_FILE,exist=exists)
  call bcast_all_singlel(exists);ULVZ_CONFIG_PRESENT=exists
  if(exists)then
    if(myrank==0) call read_ulvz_parameters(ULVZ_FILE)
    call broadcast_ulvz_parameters()
  else
    call ulvz_clear_state()
    ULVZ_BACKGROUND_FAMILY=ulvz_model_family(MODEL_NAME)
    call ulvz_background_name(ULVZ_BACKGROUND_FAMILY,ULVZ_BACKGROUND_MODEL)
  endif
  if(myrank==0)then
    call ulvz_write_summary()
    call ulvz_write_provenance(trim(OUTPUT_FILES))
  endif
  end subroutine ulvz_initialize

  subroutine read_ulvz_parameters(filename)
  use shared_parameters,only:MODEL_NAME
  character(len=*),intent(in)::filename
  type(ulvz_body_t)::legacy_body
  logical::has_n,has_enabled,enabled,has_body,has_legacy
  integer::actual_family
  call ulvz_clear_state()
  call ulvz_scan_format(filename,has_n,has_enabled,enabled,has_body,has_legacy)
  if(has_n)then
    if(has_legacy)call ulvz_fail(filename,0,'legacy field cannot be mixed with N_ULVZ format')
    if(has_body .and. N_ULVZ==0)call ulvz_fail(filename,0,'N_ULVZ=0 cannot contain body fields')
    if(.not.has_body .and. N_ULVZ>0)call ulvz_fail(filename,0,'missing ULVZ_<index> body fields')
    if(has_enabled .and. (enabled .neqv. (N_ULVZ>0)))call ulvz_fail(filename,0,'ENABLED conflicts with N_ULVZ')
    call ulvz_read_new_bodies(filename)
  else
    if(has_body)call ulvz_fail(filename,0,'ULVZ_<index> field requires N_ULVZ')
    call ulvz_read_legacy_body(filename,enabled,legacy_body)
    call ulvz_validate_body(filename,1,legacy_body)
    if(enabled)then
      N_ULVZ=1;allocate(ULVZ_BODIES(1));ULVZ_BODIES(1)=legacy_body
    endif
  endif
  actual_family=ulvz_model_family(MODEL_NAME)
  if(actual_family==ULVZ_FAMILY_UNSUPPORTED) &
    call ulvz_fail(filename,0,'ULVZ parameter file is not supported for MODEL_NAME='//trim(MODEL_NAME))
  if(ULVZ_BACKGROUND_FAMILY/=actual_family) &
    call ulvz_fail(filename,0,'BACKGROUND_MODEL does not match parsed MODEL_NAME')
  call ulvz_normalize_bodies();call ulvz_check_overlaps(filename)
  ULVZ_ENABLED=N_ULVZ>0
  end subroutine read_ulvz_parameters

  subroutine ulvz_scan_format(filename,has_n,has_enabled,enabled,has_body,has_legacy)
  use constants,only:IIN
  character(len=*),intent(in)::filename
  logical,intent(out)::has_n,has_enabled,enabled,has_body,has_legacy
  logical::seen_background
  character(len=512)::line,key,value
  integer::ier,body_index,field_index
  has_n=.false.;has_enabled=.false.;enabled=.false.;has_body=.false.;has_legacy=.false.;seen_background=.false.
  open(unit=IIN,file=trim(filename),status='old',action='read',iostat=ier)
  if(ier/=0)call ulvz_fail(filename,0,'cannot open parameter file')
  do
    call ulvz_read_line(IIN,filename,line,key,value,ier);if(ier<0)exit;if(len_trim(key)==0)cycle
    if(ulvz_equal_ignore_case(key,'BACKGROUND_MODEL'))then
      if(seen_background)call ulvz_fail(filename,0,'duplicate BACKGROUND_MODEL')
      seen_background=.true.;ULVZ_BACKGROUND_FAMILY=ulvz_parse_background_family(value,filename)
      call ulvz_background_name(ULVZ_BACKGROUND_FAMILY,ULVZ_BACKGROUND_MODEL)
    else if(ulvz_equal_ignore_case(key,'N_ULVZ'))then
      if(has_n)call ulvz_fail(filename,0,'duplicate N_ULVZ')
      has_n=.true.;read(value,*,iostat=ier)N_ULVZ
      if(ier/=0 .or. N_ULVZ<0)call ulvz_fail(filename,0,'N_ULVZ must be a non-negative integer')
    else if(ulvz_equal_ignore_case(key,'ENABLED'))then
      if(has_enabled)call ulvz_fail(filename,0,'duplicate ENABLED')
      has_enabled=.true.;read(value,*,iostat=ier)enabled;if(ier/=0)call ulvz_fail(filename,0,'invalid ENABLED')
    else if(ulvz_legacy_field_index(key)>0)then
      has_legacy=.true.
    else
      call ulvz_parse_body_key(key,body_index,field_index,ier)
      if(ier/=0)call ulvz_fail(filename,0,'unknown key: '//trim(key))
      has_body=.true.
    endif
  enddo
  close(IIN)
  if(.not.seen_background)call ulvz_fail(filename,0,'missing BACKGROUND_MODEL')
  if(.not.has_n .and. .not.has_enabled)call ulvz_fail(filename,0,'missing ENABLED in legacy format')
  end subroutine ulvz_scan_format

  subroutine ulvz_read_new_bodies(filename)
  use constants,only:IIN
  character(len=*),intent(in)::filename
  logical,allocatable::seen(:,:)
  character(len=512)::line,key,value
  integer::ier,ibody,ifield,i
  if(N_ULVZ==0)then;allocate(ULVZ_BODIES(0));return;endif
  allocate(ULVZ_BODIES(N_ULVZ),seen(ULVZ_NBODY_FIELDS,N_ULVZ));seen=.false.
  open(unit=IIN,file=trim(filename),status='old',action='read',iostat=ier)
  if(ier/=0)call ulvz_fail(filename,0,'cannot open parameter file')
  do
    call ulvz_read_line(IIN,filename,line,key,value,ier);if(ier<0)exit;if(len_trim(key)==0)cycle
    call ulvz_parse_body_key(key,ibody,ifield,ier);if(ier/=0)cycle
    if(ibody<1 .or. ibody>N_ULVZ)call ulvz_fail(filename,ibody,'body index is outside 1..N_ULVZ')
    if(seen(ifield,ibody))call ulvz_fail(filename,ibody,'duplicate '//trim(key))
    call ulvz_set_body_field(ULVZ_BODIES(ibody),ifield,value,filename,ibody);seen(ifield,ibody)=.true.
  enddo
  close(IIN)
  do i=1,N_ULVZ
    if(any(.not.seen(:,i)))call ulvz_fail(filename,i,'missing required body parameter')
    call ulvz_validate_body(filename,i,ULVZ_BODIES(i))
  enddo
  deallocate(seen)
  end subroutine ulvz_read_new_bodies

  subroutine ulvz_read_legacy_body(filename,enabled,body)
  use constants,only:IIN
  character(len=*),intent(in)::filename
  logical,intent(out)::enabled
  type(ulvz_body_t),intent(out)::body
  logical::seen(ULVZ_NBODY_FIELDS),seen_enabled
  character(len=512)::line,key,value
  integer::ier,ifield,i
  seen=.false.;seen_enabled=.false.
  open(unit=IIN,file=trim(filename),status='old',action='read',iostat=ier)
  if(ier/=0)call ulvz_fail(filename,0,'cannot open parameter file')
  do
    call ulvz_read_line(IIN,filename,line,key,value,ier);if(ier<0)exit;if(len_trim(key)==0)cycle
    if(ulvz_equal_ignore_case(key,'ENABLED'))then
      if(seen_enabled)call ulvz_fail(filename,0,'duplicate ENABLED')
      read(value,*,iostat=ier)enabled;if(ier/=0)call ulvz_fail(filename,0,'invalid ENABLED');seen_enabled=.true.
    else
      ifield=ulvz_legacy_field_index(key);if(ifield<=0)cycle
      if(seen(ifield))call ulvz_fail(filename,1,'duplicate '//trim(key))
      call ulvz_set_body_field(body,ifield,value,filename,1);seen(ifield)=.true.
    endif
  enddo
  close(IIN)
  if(.not.seen_enabled)call ulvz_fail(filename,0,'missing ENABLED')
  do i=1,ULVZ_NBODY_FIELDS;if(.not.seen(i))call ulvz_fail(filename,1,'missing legacy body parameter');enddo
  end subroutine ulvz_read_legacy_body

  subroutine broadcast_ulvz_parameters()
  use constants,only:myrank
  integer::i
  double precision::params(ULVZ_NBODY_FIELDS)
  call bcast_all_singlei(N_ULVZ);call bcast_all_singlei(ULVZ_BACKGROUND_FAMILY)
  if(allocated(ULVZ_BODIES))then
    if(size(ULVZ_BODIES)/=N_ULVZ)deallocate(ULVZ_BODIES)
  endif
  if(.not.allocated(ULVZ_BODIES))allocate(ULVZ_BODIES(N_ULVZ))
  do i=1,N_ULVZ
    if(myrank==0)params=ulvz_body_values(ULVZ_BODIES(i))
    call bcast_all_dp(params,ULVZ_NBODY_FIELDS);call ulvz_set_body_values(ULVZ_BODIES(i),params)
  enddo
  call ulvz_background_name(ULVZ_BACKGROUND_FAMILY,ULVZ_BACKGROUND_MODEL);ULVZ_ENABLED=N_ULVZ>0
  end subroutine broadcast_ulvz_parameters

  subroutine ulvz_clear_state()
  if(allocated(ULVZ_BODIES))deallocate(ULVZ_BODIES)
  N_ULVZ=0;ULVZ_ENABLED=.false.;ULVZ_BACKGROUND_FAMILY=ULVZ_FAMILY_UNSUPPORTED;ULVZ_BACKGROUND_MODEL='NONE'
  end subroutine ulvz_clear_state

  subroutine ulvz_validate_body(filename,ibody,body)
  use constants,only:EARTH_R
  character(len=*),intent(in)::filename
  integer,intent(in)::ibody
  type(ulvz_body_t),intent(in)::body
  double precision::max_thickness_km
  max_thickness_km=((EARTH_R-24400.d0)-ULVZ_RCMB_M)/1000.d0
  if(.not.ulvz_is_finite(body%center_latitude_degrees) .or. .not.ulvz_is_finite(body%center_longitude_degrees) .or. &
     .not.ulvz_is_finite(body%thickness_km) .or. .not.ulvz_is_finite(body%lateral_radius_km) .or. &
     .not.ulvz_is_finite(body%lateral_taper_km) .or. .not.ulvz_is_finite(body%top_taper_km) .or. &
     .not.ulvz_is_finite(body%dvs) .or. .not.ulvz_is_finite(body%dvp) .or. &
     .not.ulvz_is_finite(body%drho)) call ulvz_fail(filename,ibody,'non-finite body value')
  if(body%center_latitude_degrees < -90.d0 .or. body%center_latitude_degrees > 90.d0) &
    call ulvz_fail(filename,ibody,'CENTER_LATITUDE_DEGREES must be in [-90,90]')
  if(body%thickness_km<=0.d0 .or. body%thickness_km>max_thickness_km) &
    call ulvz_fail(filename,ibody,'THICKNESS_KM must fit inside mantle above CMB')
  if(body%lateral_radius_km<=0.d0)call ulvz_fail(filename,ibody,'LATERAL_RADIUS_KM must be > 0')
  if(body%lateral_taper_km<0.d0 .or. body%lateral_taper_km>body%lateral_radius_km) &
    call ulvz_fail(filename,ibody,'LATERAL_TAPER_KM must be in [0,LATERAL_RADIUS_KM]')
  if(body%top_taper_km<0.d0 .or. body%top_taper_km>body%thickness_km) &
    call ulvz_fail(filename,ibody,'TOP_TAPER_KM must be in [0,THICKNESS_KM]')
  if(body%dvs<=-1.d0 .or. body%dvp<=-1.d0 .or. body%drho<=-1.d0) &
    call ulvz_fail(filename,ibody,'DVS, DVP, and DRHO must be > -1')
  end subroutine ulvz_validate_body

  subroutine ulvz_normalize_bodies()
  use constants,only:DEGREES_TO_RADIANS
  integer::i
  do i=1,N_ULVZ
    ULVZ_BODIES(i)%center_longitude_degrees=modulo(ULVZ_BODIES(i)%center_longitude_degrees+180.d0,360.d0)-180.d0
    ULVZ_BODIES(i)%center_latitude_radians=ULVZ_BODIES(i)%center_latitude_degrees*DEGREES_TO_RADIANS
    ULVZ_BODIES(i)%center_longitude_radians=ULVZ_BODIES(i)%center_longitude_degrees*DEGREES_TO_RADIANS
  enddo
  end subroutine ulvz_normalize_bodies

  subroutine ulvz_check_overlaps(filename)
  use constants,only:PI
  character(len=*),intent(in)::filename
  integer::i,j
  double precision::cosang,center_angle,ri,rj,tolerance
  tolerance=64.d0*epsilon(1.d0)
  do i=1,N_ULVZ-1
    ri=min(ULVZ_BODIES(i)%lateral_radius_km/(ULVZ_RCMB_M/1000.d0),PI)
    do j=i+1,N_ULVZ
      rj=min(ULVZ_BODIES(j)%lateral_radius_km/(ULVZ_RCMB_M/1000.d0),PI)
      cosang=dsin(ULVZ_BODIES(i)%center_latitude_radians)*dsin(ULVZ_BODIES(j)%center_latitude_radians)+ &
        dcos(ULVZ_BODIES(i)%center_latitude_radians)*dcos(ULVZ_BODIES(j)%center_latitude_radians)* &
        dcos(ULVZ_BODIES(i)%center_longitude_radians-ULVZ_BODIES(j)%center_longitude_radians)
      center_angle=dacos(max(-1.d0,min(1.d0,cosang)))
      if(center_angle<=ri+rj+tolerance)call ulvz_fail_pair(filename,i,j,'overlap or boundary contact')
    enddo
  enddo
  end subroutine ulvz_check_overlaps

  double precision function ulvz_body_taper_weight(body,radius,theta,phi)
  use constants,only:EARTH_R,PI,PI_OVER_TWO,TWO_PI
  type(ulvz_body_t),intent(in)::body
  double precision,intent(in)::radius,theta,phi
  double precision::lat,lon,height_km,cosang,distance_km,lateral_weight,top_weight,x,y
  ulvz_body_taper_weight=0.d0;lat=PI_OVER_TWO-theta;lon=modulo(phi+PI,TWO_PI)-PI
  height_km=(radius*EARTH_R-ULVZ_RCMB_M)/1000.d0
  if(height_km<0.d0 .or. height_km>body%thickness_km)return
  cosang=dsin(lat)*dsin(body%center_latitude_radians)+dcos(lat)*dcos(body%center_latitude_radians)* &
    dcos(lon-body%center_longitude_radians)
  distance_km=(ULVZ_RCMB_M/1000.d0)*dacos(max(-1.d0,min(1.d0,cosang)))
  if(distance_km>body%lateral_radius_km)return
  if(body%lateral_taper_km==0.d0 .or. distance_km<=body%lateral_radius_km-body%lateral_taper_km)then
    lateral_weight=1.d0
  else
    x=(distance_km-(body%lateral_radius_km-body%lateral_taper_km))/body%lateral_taper_km
    lateral_weight=.5d0*(1.d0+dcos(PI*x))
  endif
  if(body%top_taper_km==0.d0 .or. height_km<=body%thickness_km-body%top_taper_km)then
    top_weight=1.d0
  else
    y=(height_km-(body%thickness_km-body%top_taper_km))/body%top_taper_km;top_weight=.5d0*(1.d0+dcos(PI*y))
  endif
  ulvz_body_taper_weight=lateral_weight*top_weight
  end function ulvz_body_taper_weight

  double precision function ulvz_taper_weight(radius,theta,phi)
  double precision,intent(in)::radius,theta,phi
  integer::i
  ulvz_taper_weight=0.d0
  do i=1,N_ULVZ
    ulvz_taper_weight=ulvz_body_taper_weight(ULVZ_BODIES(i),radius,theta,phi)
    if(ulvz_taper_weight>0.d0)return
  enddo
  end function ulvz_taper_weight

  subroutine ulvz_apply_s40rts_overlay(radius,theta,phi,dvs,dvp,drho)
  double precision,intent(in)::radius,theta,phi
  double precision,intent(inout)::dvs,dvp,drho
  double precision::w
  integer::i
  if(ULVZ_BACKGROUND_FAMILY/=ULVZ_FAMILY_S40RTS)return
  do i=1,N_ULVZ
    w=ulvz_body_taper_weight(ULVZ_BODIES(i),radius,theta,phi);if(w<=0.d0)cycle
    dvs=(1.d0+dvs)*(1.d0+w*ULVZ_BODIES(i)%dvs)-1.d0
    dvp=(1.d0+dvp)*(1.d0+w*ULVZ_BODIES(i)%dvp)-1.d0
    drho=(1.d0+drho)*(1.d0+w*ULVZ_BODIES(i)%drho)-1.d0
    return
  enddo
  end subroutine ulvz_apply_s40rts_overlay

  subroutine ulvz_apply_prem_overlay(radius,theta,phi,rho,vpv,vph,vsv,vsh)
  double precision,intent(in)::radius,theta,phi
  double precision,intent(inout)::rho,vpv,vph,vsv,vsh
  double precision::w
  integer::i
  if(ULVZ_BACKGROUND_FAMILY/=ULVZ_FAMILY_PREM)return
  do i=1,N_ULVZ
    w=ulvz_body_taper_weight(ULVZ_BODIES(i),radius,theta,phi);if(w<=0.d0)cycle
    rho=rho*(1.d0+w*ULVZ_BODIES(i)%drho);vpv=vpv*(1.d0+w*ULVZ_BODIES(i)%dvp);vph=vph*(1.d0+w*ULVZ_BODIES(i)%dvp)
    vsv=vsv*(1.d0+w*ULVZ_BODIES(i)%dvs);vsh=vsh*(1.d0+w*ULVZ_BODIES(i)%dvs);return
  enddo
  end subroutine ulvz_apply_prem_overlay

  subroutine ulvz_write_summary()
  use constants,only:IMAIN
  integer::i
  write(IMAIN,'(a,i0)')'N_ULVZ = ',N_ULVZ;write(IMAIN,'(a,a)')'ULVZ background = ',trim(ULVZ_BACKGROUND_MODEL)
  if(N_ULVZ==0)write(IMAIN,'(a)')'ULVZ baseline: no active body'
  do i=1,N_ULVZ
    write(IMAIN,'(a,i0)')'ULVZ body ',i
    write(IMAIN,'(a,2(1x,es24.16))')'  center_lat_lon_deg =', &
      ULVZ_BODIES(i)%center_latitude_degrees,ULVZ_BODIES(i)%center_longitude_degrees
    write(IMAIN,'(a,2(1x,es24.16))')'  R_H_km =',ULVZ_BODIES(i)%lateral_radius_km,ULVZ_BODIES(i)%thickness_km
    write(IMAIN,'(a,2(1x,es24.16))')'  lateral_top_taper_km =', &
      ULVZ_BODIES(i)%lateral_taper_km,ULVZ_BODIES(i)%top_taper_km
    write(IMAIN,'(a,3(1x,es24.16))')'  dVs_dVp_dRho =',ULVZ_BODIES(i)%dvs,ULVZ_BODIES(i)%dvp,ULVZ_BODIES(i)%drho
  enddo
  call flush_IMAIN()
  end subroutine ulvz_write_summary

  subroutine ulvz_write_provenance(output_files)
  character(len=*),intent(in)::output_files
  character(len=1024)::filename
  integer::unit,ier,i
  filename=trim(output_files)//'/ulvz_normalized.csv'
  open(newunit=unit,file=trim(filename),status='new',action='write',iostat=ier)
  if(ier/=0)call ulvz_fail(trim(filename),0,'cannot write normalized provenance')
  write(unit,'(a)')'background,n_ulvz,body_index,center_latitude_degrees,center_longitude_degrees,'// &
    'lateral_radius_km,thickness_km,lateral_taper_km,top_taper_km,dvs,dvp,drho'
  if(N_ULVZ==0)then
    write(unit,'(a,a,i0,a)')trim(ULVZ_BACKGROUND_MODEL),',',0,',,,,,,,,,,'
  else
    do i=1,N_ULVZ
      write(unit,'(a,a,i0,a,i0,9(a,es24.16))')trim(ULVZ_BACKGROUND_MODEL),',',N_ULVZ,',',i, &
        ',',ULVZ_BODIES(i)%center_latitude_degrees,',',ULVZ_BODIES(i)%center_longitude_degrees, &
        ',',ULVZ_BODIES(i)%lateral_radius_km,',',ULVZ_BODIES(i)%thickness_km, &
        ',',ULVZ_BODIES(i)%lateral_taper_km,',',ULVZ_BODIES(i)%top_taper_km, &
        ',',ULVZ_BODIES(i)%dvs,',',ULVZ_BODIES(i)%dvp,',',ULVZ_BODIES(i)%drho
    enddo
  endif
  close(unit)
  end subroutine ulvz_write_provenance

  subroutine ulvz_read_line(unit,filename,line,key,value,ier)
  integer,intent(in)::unit
  character(len=*),intent(in)::filename
  character(len=*),intent(out)::line,key,value
  integer,intent(out)::ier
  integer::hash_pos,equals_pos
  read(unit,'(A)',iostat=ier)line;key='';value='';if(ier/=0)return
  line=adjustl(line);if(len_trim(line)==0 .or. line(1:1)=='#')return
  hash_pos=index(line,'#');if(hash_pos>0)line=line(:hash_pos-1)
  line=adjustl(line);if(len_trim(line)==0)return;equals_pos=index(line,'=')
  if(equals_pos<=1 .or. len_trim(line(equals_pos+1:))==0)call ulvz_fail(filename,0,'malformed key/value line')
  key=adjustl(line(:equals_pos-1));value=adjustl(line(equals_pos+1:))
  end subroutine ulvz_read_line

  subroutine ulvz_parse_body_key(key,ibody,ifield,ier)
  character(len=*),intent(in)::key
  integer,intent(out)::ibody,ifield,ier
  character(len=512)::rest,index_string,field
  integer::underscore
  ibody=0;ifield=0;ier=1
  if(len_trim(key)<8 .or. .not.ulvz_starts_with_ignore_case(key,'ULVZ_'))return
  rest=key(6:);underscore=index(rest,'_');if(underscore<=1)return
  index_string=rest(:underscore-1);field=rest(underscore+1:);read(index_string,*,iostat=ier)ibody
  if(ier/=0 .or. ibody<1)then;ier=1;return;endif
  ifield=ulvz_legacy_field_index(field);if(ifield<=0)then;ier=1;return;endif
  ier=0
  end subroutine ulvz_parse_body_key

  integer function ulvz_legacy_field_index(key)
  character(len=*),intent(in)::key
  character(len=64),parameter::fields(ULVZ_NBODY_FIELDS)=(/ character(len=64) :: &
    'CENTER_LATITUDE_DEGREES','CENTER_LONGITUDE_DEGREES','THICKNESS_KM', &
    'LATERAL_RADIUS_KM','LATERAL_TAPER_KM','TOP_TAPER_KM','DVS','DVP','DRHO' /)
  integer::i
  ulvz_legacy_field_index=0
  do i=1,ULVZ_NBODY_FIELDS
    if(ulvz_equal_ignore_case(key,fields(i)))then
      ulvz_legacy_field_index=i
      return
    endif
  enddo
  end function ulvz_legacy_field_index

  subroutine ulvz_set_body_field(body,ifield,value,filename,ibody)
  type(ulvz_body_t),intent(inout)::body
  integer,intent(in)::ifield,ibody
  character(len=*),intent(in)::value,filename
  double precision::x
  integer::ier
  read(value,*,iostat=ier)x;if(ier/=0)call ulvz_fail(filename,ibody,'invalid '//trim(ulvz_field_name(ifield)))
  select case(ifield)
  case(1);body%center_latitude_degrees=x
  case(2);body%center_longitude_degrees=x
  case(3);body%thickness_km=x
  case(4);body%lateral_radius_km=x
  case(5);body%lateral_taper_km=x
  case(6);body%top_taper_km=x
  case(7);body%dvs=x
  case(8);body%dvp=x
  case(9);body%drho=x
  end select
  end subroutine ulvz_set_body_field

  function ulvz_body_values(body)result(values)
  type(ulvz_body_t),intent(in)::body
  double precision::values(ULVZ_NBODY_FIELDS)
  values=(/body%center_latitude_degrees,body%center_longitude_degrees,body%thickness_km, &
    body%lateral_radius_km,body%lateral_taper_km,body%top_taper_km,body%dvs,body%dvp,body%drho/)
  end function ulvz_body_values
  subroutine ulvz_set_body_values(body,values)
  use constants,only:DEGREES_TO_RADIANS
  type(ulvz_body_t),intent(out)::body
  double precision,intent(in)::values(ULVZ_NBODY_FIELDS)
  body%center_latitude_degrees=values(1);body%center_longitude_degrees=values(2);body%thickness_km=values(3)
  body%lateral_radius_km=values(4);body%lateral_taper_km=values(5);body%top_taper_km=values(6)
  body%dvs=values(7);body%dvp=values(8);body%drho=values(9)
  body%center_latitude_radians=body%center_latitude_degrees*DEGREES_TO_RADIANS
  body%center_longitude_radians=body%center_longitude_degrees*DEGREES_TO_RADIANS
  end subroutine ulvz_set_body_values

  integer function ulvz_parse_background_family(value,filename)
  character(len=*),intent(in)::value,filename
  if(ulvz_equal_ignore_case(value,'PREM'))then;ulvz_parse_background_family=ULVZ_FAMILY_PREM
  else if(ulvz_equal_ignore_case(value,'S40RTS'))then;ulvz_parse_background_family=ULVZ_FAMILY_S40RTS
  else;call ulvz_fail(filename,0,'BACKGROUND_MODEL must be PREM or S40RTS');endif
  end function ulvz_parse_background_family
  subroutine ulvz_background_name(family,name)
  integer,intent(in)::family
  character(len=*),intent(out)::name
  name='NONE';if(family==ULVZ_FAMILY_PREM)name='PREM';if(family==ULVZ_FAMILY_S40RTS)name='S40RTS'
  end subroutine ulvz_background_name
  character(len=64) function ulvz_field_name(ifield)
  integer,intent(in)::ifield
  character(len=64),parameter::names(ULVZ_NBODY_FIELDS)=(/ character(len=64) :: &
    'CENTER_LATITUDE_DEGREES','CENTER_LONGITUDE_DEGREES','THICKNESS_KM', &
    'LATERAL_RADIUS_KM','LATERAL_TAPER_KM','TOP_TAPER_KM','DVS','DVP','DRHO' /)
  ulvz_field_name=names(ifield)
  end function ulvz_field_name
  subroutine ulvz_fail(filename,ibody,message)
  use constants,only:myrank
  character(len=*),intent(in)::filename,message
  integer,intent(in)::ibody
  character(len=1024)::text
  if(ibody>0)then
    write(text,'(a,a,a,i0,a,a)')'ULVZ parameter error in ',trim(filename),' body ',ibody,': ',trim(message)
  else;text='ULVZ parameter error in '//trim(filename)//': '//trim(message);endif
  call exit_MPI(myrank,trim(text))
  end subroutine ulvz_fail
  subroutine ulvz_fail_pair(filename,i,j,message)
  use constants,only:myrank
  character(len=*),intent(in)::filename,message
  integer,intent(in)::i,j
  character(len=1024)::text
  write(text,'(a,a,a,i0,a,i0,a,a)')'ULVZ parameter error in ',trim(filename),': bodies ',i,' and ',j,' ',trim(message)
  call exit_MPI(myrank,trim(text))
  end subroutine ulvz_fail_pair
  logical function ulvz_equal_ignore_case(a,b)
  character(len=*),intent(in)::a,b
  integer::i,la,lb
  character::ca,cb
  la=len_trim(a);lb=len_trim(b);if(la/=lb)then;ulvz_equal_ignore_case=.false.;return;endif
  do i=1,la
    ca=a(i:i);cb=b(i:i)
    if(lge(ca,'A').and.lle(ca,'Z'))ca=achar(iachar(ca)+iachar('a')-iachar('A'))
    if(lge(cb,'A').and.lle(cb,'Z'))cb=achar(iachar(cb)+iachar('a')-iachar('A'))
    if(ca/=cb)then;ulvz_equal_ignore_case=.false.;return;endif
  enddo
  ulvz_equal_ignore_case=.true.
  end function ulvz_equal_ignore_case
  logical function ulvz_starts_with_ignore_case(value,prefix)
  character(len=*),intent(in)::value,prefix
  if(len_trim(value)<len_trim(prefix))then
    ulvz_starts_with_ignore_case=.false.
  else
    ulvz_starts_with_ignore_case=ulvz_equal_ignore_case(value(:len_trim(prefix)),prefix)
  endif
  end function ulvz_starts_with_ignore_case
  logical function ulvz_is_finite(value)
  double precision,intent(in)::value
  ulvz_is_finite=(value==value).and.(dabs(value)<huge(value))
  end function ulvz_is_finite
  end module model_ulvz_par
