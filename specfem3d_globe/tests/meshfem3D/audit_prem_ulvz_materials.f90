program audit_prem_ulvz_materials

  use constants, only: CUSTOM_REAL,EARTH_R,PI,PI_OVER_TWO,DEGREES_TO_RADIANS,NGLLX,NGLLY,NGLLZ
  use model_ulvz_par
  use shared_parameters, only: MODEL

  implicit none

  integer, parameter :: NPOINTS = 11
  double precision, parameter :: RCMB_M = 3480000.d0
  double precision, parameter :: THICKNESS_KM = 80.d0
  double precision, parameter :: LATERAL_RADIUS_KM = 400.d0
  double precision, parameter :: LATERAL_TAPER_KM = 100.d0
  double precision, parameter :: TOP_TAPER_KM = 20.d0
  double precision, parameter :: DVS = -0.20d0, DVP = -0.10d0, DRHO = 0.05d0
  double precision, parameter :: TOL = 1.d-10

  type point_record
    character(len=32) :: label = ''
    character(len=24) :: source = ''
    integer :: rank = -1, ispec = -1, i = -1, j = -1, k = -1
    double precision :: radius = 0.d0, theta = 0.d0, phi = 0.d0
    double precision :: height_km = 0.d0, lateral_km = 0.d0, weight = 0.d0
  end type point_record

  type coordinate_db
    integer :: nspec = 0, nglob = 0
    real(kind=CUSTOM_REAL), allocatable :: x(:),y(:),z(:)
    integer, allocatable :: ibool(:,:,:,:)
  end type coordinate_db

  type(point_record) :: points(NPOINTS)
  type(coordinate_db) :: db
  character(len=512) :: fixture_dir,csv_file,report_file,filename
  integer :: iproc,ier,unit,pass_count,fail_count

  call get_command_argument(1,fixture_dir)
  call get_command_argument(2,csv_file)
  call get_command_argument(3,report_file)
  if (len_trim(fixture_dir) == 0 .or. len_trim(csv_file) == 0 .or. len_trim(report_file) == 0) then
    stop 'Usage: audit_prem_ulvz_materials FIXTURE_DIR OUTPUT_CSV OUTPUT_REPORT'
  endif

  call configure_ulvz()
  call initialize_points(points)
  do iproc = 0,1
    write(filename,"(a,'/DATABASES_MPI/proc',i6.6,'_reg1_solver_data.bin')") trim(fixture_dir),iproc
    call read_coordinate_database(trim(filename),db)
    call update_fixture_candidates(db,iproc,points)
    call free_coordinate_database(db)
  enddo
  call finalize_constructed_points(points)

  open(newunit=unit,file=trim(csv_file),status='new',action='write',iostat=ier)
  if (ier /= 0) stop 'Cannot create material audit CSV'
  write(unit,'(a)') 'model,point,source,rank,ispec,i,j,k,radius_norm,height_km,lateral_km,w,'// &
    'rho_prem,rho_ulvz,rho_ratio,rho_expected,vpv_prem,vpv_ulvz,vpv_ratio,vpv_expected,'// &
    'vph_prem,vph_ulvz,vph_ratio,vph_expected,vsv_prem,vsv_ulvz,vsv_ratio,vsv_expected,'// &
    'vsh_prem,vsh_ulvz,vsh_ratio,vsh_expected,eta_prem,eta_ulvz,eta_ratio,status'

  pass_count = 0
  fail_count = 0
  call audit_model('1d_isotropic_prem',.false.,points,unit,pass_count,fail_count)
  call audit_model('1d_transversely_isotropic_prem',.true.,points,unit,pass_count,fail_count)
  call audit_tiso_component_independence(unit,pass_count,fail_count)
  close(unit)

  open(newunit=unit,file=trim(report_file),status='new',action='write',iostat=ier)
  if (ier /= 0) stop 'Cannot create material audit report'
  write(unit,'(a)') '# PREM + ULVZ material audit'
  write(unit,'(a,i0)') 'pass_rows=',pass_count
  write(unit,'(a,i0)') 'fail_rows=',fail_count
  write(unit,'(a)') 'Fixture GLL coordinates were read from the existing TISO PREM disabled database.'
  write(unit,'(a)') 'CMB, top and lateral-boundary rows are analytical probes using the same material routines.'
  write(unit,'(a)') 'All material values are SPECFEM non-dimensional internal values; ratios are dimensionless.'
  if (fail_count == 0) then
    write(unit,'(a)') 'status=PASS'
  else
    write(unit,'(a)') 'status=FAIL'
  endif
  close(unit)
  if (fail_count /= 0) stop 1

contains

  subroutine configure_ulvz()
    ULVZ_ENABLED = .true.
    ULVZ_BACKGROUND_FAMILY = ULVZ_FAMILY_PREM
    ULVZ_CENTER_LATITUDE_DEGREES = 45.d0
    ULVZ_CENTER_LONGITUDE_DEGREES = 140.d0
    ULVZ_CENTER_LATITUDE_RADIANS = ULVZ_CENTER_LATITUDE_DEGREES * DEGREES_TO_RADIANS
    ULVZ_CENTER_LONGITUDE_RADIANS = ULVZ_CENTER_LONGITUDE_DEGREES * DEGREES_TO_RADIANS
    ULVZ_THICKNESS_KM = THICKNESS_KM
    ULVZ_LATERAL_RADIUS_KM = LATERAL_RADIUS_KM
    ULVZ_LATERAL_TAPER_KM = LATERAL_TAPER_KM
    ULVZ_TOP_TAPER_KM = TOP_TAPER_KM
    ULVZ_DVS = DVS
    ULVZ_DVP = DVP
    ULVZ_DRHO = DRHO
  end subroutine configure_ulvz

  subroutine initialize_points(values)
    type(point_record), intent(out) :: values(NPOINTS)
    integer :: n
    do n = 1,NPOINTS
      values(n)%label = ''
      values(n)%weight = -1.d0
    enddo
    values(1)%label = 'fixture_core'
    values(2)%label = 'fixture_taper'
    values(3)%label = 'fixture_outside'
    values(4)%label = 'fixture_cmb_nearest_inside'
    values(5)%label = 'fixture_top_nearest_inside'
    values(6)%label = 'fixture_above_top_inside'
    values(7)%label = 'exact_cmb_center'
    values(8)%label = 'exact_top_center'
    values(9)%label = 'exact_above_top_center'
    values(10)%label = 'nominal_lateral_boundary'
    values(11)%label = 'lateral_boundary_outside_100m'
  end subroutine initialize_points

  subroutine read_coordinate_database(name,values)
    character(len=*), intent(in) :: name
    type(coordinate_db), intent(inout) :: values
    integer :: read_unit,read_status
    open(newunit=read_unit,file=trim(name),status='old',form='unformatted',action='read',iostat=read_status)
    if (read_status /= 0) stop 'Cannot open fixture solver database'
    read(read_unit) values%nspec
    read(read_unit) values%nglob
    allocate(values%x(values%nglob),values%y(values%nglob),values%z(values%nglob))
    allocate(values%ibool(NGLLX,NGLLY,NGLLZ,values%nspec))
    read(read_unit) values%x
    read(read_unit) values%y
    read(read_unit) values%z
    read(read_unit) values%ibool
    close(read_unit)
  end subroutine read_coordinate_database

  subroutine free_coordinate_database(values)
    type(coordinate_db), intent(inout) :: values
    deallocate(values%x,values%y,values%z,values%ibool)
  end subroutine free_coordinate_database

  subroutine update_fixture_candidates(values,rank,records)
    type(coordinate_db), intent(in) :: values
    integer, intent(in) :: rank
    type(point_record), intent(inout) :: records(NPOINTS)
    integer :: ispec,i,j,k,iglob
    type(point_record) :: candidate

    do ispec = 1,values%nspec
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            iglob = values%ibool(i,j,k,ispec)
            call make_fixture_point(candidate,rank,ispec,i,j,k,dble(values%x(iglob)),dble(values%y(iglob)),dble(values%z(iglob)))
            if (candidate%weight > records(1)%weight) then
              records(1) = candidate
              records(1)%label = 'fixture_core'
            endif
            if (candidate%weight > 0.05d0 .and. candidate%weight < 0.95d0) then
              if (records(2)%weight < 0.d0 .or. &
                  dabs(candidate%weight - 0.5d0) < dabs(records(2)%weight - 0.5d0)) then
                records(2) = candidate
                records(2)%label = 'fixture_taper'
              endif
            endif
            if (candidate%weight == 0.d0 .and. candidate%height_km > 5.d0 .and. candidate%height_km < 60.d0) then
              if (records(3)%weight < 0.d0) then
                records(3) = candidate
                records(3)%label = 'fixture_outside'
              endif
            endif
            if (candidate%lateral_km <= LATERAL_RADIUS_KM - LATERAL_TAPER_KM) then
              if (records(4)%weight < 0.d0 .or. dabs(candidate%height_km) < dabs(records(4)%height_km)) then
                records(4) = candidate
                records(4)%label = 'fixture_cmb_nearest_inside'
              endif
              if (records(5)%weight < 0.d0 .or. &
                  dabs(candidate%height_km - THICKNESS_KM) < dabs(records(5)%height_km - THICKNESS_KM)) then
                records(5) = candidate
                records(5)%label = 'fixture_top_nearest_inside'
              endif
              if (candidate%height_km > THICKNESS_KM .and. &
                  (records(6)%weight < 0.d0 .or. candidate%height_km < records(6)%height_km)) then
                records(6) = candidate
                records(6)%label = 'fixture_above_top_inside'
              endif
            endif
          enddo
        enddo
      enddo
    enddo
  end subroutine update_fixture_candidates

  subroutine make_fixture_point(record,rank,ispec,i,j,k,x,y,z)
    type(point_record), intent(out) :: record
    integer, intent(in) :: rank,ispec,i,j,k
    double precision, intent(in) :: x,y,z
    double precision :: cosang,lat,lon
    record%source = 'fixture_gll'
    record%rank = rank
    record%ispec = ispec
    record%i = i
    record%j = j
    record%k = k
    record%radius = dsqrt(x*x + y*y + z*z)
    record%theta = dacos(z / record%radius)
    record%phi = datan2(y,x)
    if (record%phi < 0.d0) record%phi = record%phi + 2.d0*PI
    record%height_km = (record%radius * EARTH_R - RCMB_M) / 1000.d0
    lat = PI_OVER_TWO - record%theta
    lon = modulo(record%phi + PI,2.d0*PI) - PI
    cosang = dsin(lat)*dsin(ULVZ_CENTER_LATITUDE_RADIANS) + &
             dcos(lat)*dcos(ULVZ_CENTER_LATITUDE_RADIANS) * dcos(lon-ULVZ_CENTER_LONGITUDE_RADIANS)
    cosang = max(-1.d0,min(1.d0,cosang))
    record%lateral_km = (RCMB_M/1000.d0) * dacos(cosang)
    record%weight = ulvz_taper_weight(record%radius,record%theta,record%phi)
  end subroutine make_fixture_point

  subroutine finalize_constructed_points(records)
    type(point_record), intent(inout) :: records(NPOINTS)
    call set_constructed_point(records(7),0.d0,0.d0)
    call set_constructed_point(records(8),THICKNESS_KM,0.d0)
    call set_constructed_point(records(9),THICKNESS_KM+1.d0,0.d0)
    call set_constructed_point(records(10),40.d0,LATERAL_RADIUS_KM)
    call set_constructed_point(records(11),40.d0,LATERAL_RADIUS_KM+0.1d0)
  end subroutine finalize_constructed_points

  subroutine set_constructed_point(record,height_km,lateral_km)
    type(point_record), intent(inout) :: record
    double precision, intent(in) :: height_km,lateral_km
    record%source = 'exact_probe'
    record%radius = (RCMB_M + 1000.d0*height_km) / EARTH_R
    ! A meridional displacement is a great-circle distance by construction.
    record%theta = PI_OVER_TWO - ULVZ_CENTER_LATITUDE_RADIANS - lateral_km / (RCMB_M/1000.d0)
    record%phi = ULVZ_CENTER_LONGITUDE_RADIANS
    record%height_km = height_km
    record%lateral_km = lateral_km
    record%weight = ulvz_taper_weight(record%radius,record%theta,record%phi)
  end subroutine set_constructed_point

  subroutine audit_model(model_name,is_tiso,records,csv_unit,passed,failed)
    character(len=*), intent(in) :: model_name
    logical, intent(in) :: is_tiso
    type(point_record), intent(in) :: records(NPOINTS)
    integer, intent(in) :: csv_unit
    integer, intent(inout) :: passed,failed
    integer :: n
    MODEL = model_name
    call get_model_parameters()
    do n = 1,NPOINTS
      call audit_one_point(model_name,is_tiso,records(n),csv_unit,passed,failed)
    enddo
  end subroutine audit_model

  subroutine audit_one_point(model_name,is_tiso,record,csv_unit,passed,failed)
    character(len=*), intent(in) :: model_name
    logical, intent(in) :: is_tiso
    type(point_record), intent(in) :: record
    integer, intent(in) :: csv_unit
    integer, intent(inout) :: passed,failed
    double precision :: rho0,vpv0,vph0,vsv0,vsh0,eta0,qk,qm,drhodr,vp,vs,rprem
    double precision :: rho1,vpv1,vph1,vsv1,vsh1,eta1,expected(6),ratio(6)
    logical :: ok

    rprem = max(record%radius,(RCMB_M/EARTH_R)*1.000001d0)
    qk = 0.d0
    qm = 0.d0
    if (is_tiso) then
      call model_prem_aniso(rprem,rho0,vpv0,vph0,vsv0,vsh0,eta0,qk,qm,0,.false.,.false.)
    else
      call model_prem_iso(rprem,rho0,drhodr,vp,vs,qk,qm,0,.false.,.false.)
      vpv0 = vp
      vph0 = vp
      vsv0 = vs
      vsh0 = vs
      eta0 = 1.d0
    endif
    rho1 = rho0
    vpv1 = vpv0
    vph1 = vph0
    vsv1 = vsv0
    vsh1 = vsh0
    eta1 = eta0
    call ulvz_apply_prem_overlay(record%radius,record%theta,record%phi,rho1,vpv1,vph1,vsv1,vsh1)
    ratio = (/rho1/rho0,vpv1/vpv0,vph1/vph0,vsv1/vsv0,vsh1/vsh0,eta1/eta0/)
    expected = (/1.d0+record%weight*DRHO,1.d0+record%weight*DVP,1.d0+record%weight*DVP, &
                 1.d0+record%weight*DVS,1.d0+record%weight*DVS,1.d0/)
    ok = maxval(dabs(ratio-expected)) <= TOL
    if (ok) then
      passed = passed + 1
    else
      failed = failed + 1
    endif
    write(csv_unit,'(a,",",a,",",a,",",5(i0,","),27(es24.16,","),a)') trim(model_name),trim(record%label),trim(record%source), &
      record%rank,record%ispec,record%i,record%j,record%k,record%radius,record%height_km,record%lateral_km,record%weight, &
      rho0,rho1,ratio(1),expected(1),vpv0,vpv1,ratio(2),expected(2),vph0,vph1,ratio(3),expected(3), &
      vsv0,vsv1,ratio(4),expected(4),vsh0,vsh1,ratio(5),expected(5),eta0,eta1,ratio(6),trim(merge('PASS','FAIL',ok))
  end subroutine audit_one_point

  subroutine audit_tiso_component_independence(csv_unit,passed,failed)
    integer, intent(in) :: csv_unit
    integer, intent(inout) :: passed,failed
    double precision :: rho,vpv,vph,vsv,vsh,eta,ratio(6),expected(6)
    logical :: ok
    rho = 5.d0
    vpv = 10.d0
    vph = 11.d0
    vsv = 6.d0
    vsh = 7.d0
    eta = 1.3d0
    call ulvz_apply_prem_overlay((RCMB_M+1000.d0)/EARTH_R,PI_OVER_TWO-ULVZ_CENTER_LATITUDE_RADIANS, &
      ULVZ_CENTER_LONGITUDE_RADIANS,rho,vpv,vph,vsv,vsh)
    ratio = (/rho/5.d0,vpv/10.d0,vph/11.d0,vsv/6.d0,vsh/7.d0,eta/1.3d0/)
    expected = (/1.d0+DRHO,1.d0+DVP,1.d0+DVP,1.d0+DVS,1.d0+DVS,1.d0/)
    ok = maxval(dabs(ratio-expected)) <= TOL
    if (ok) then
      passed = passed + 1
    else
      failed = failed + 1
    endif
    write(csv_unit,'(a,",",a,",",a,",",5(i0,","),27(es24.16,","),a)') &
      'tiso_component_probe','independent_components','exact_probe', &
      -1,-1,-1,-1,-1,(RCMB_M+1000.d0)/EARTH_R,1.d0,0.d0,1.d0,5.d0,rho,ratio(1),expected(1),10.d0,vpv,ratio(2),expected(2), &
      11.d0,vph,ratio(3),expected(3),6.d0,vsv,ratio(4),expected(4),7.d0,vsh,ratio(5),expected(5), &
      1.3d0,eta,ratio(6),trim(merge('PASS','FAIL',ok))
  end subroutine audit_tiso_component_independence

end program audit_prem_ulvz_materials
