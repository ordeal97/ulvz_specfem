program inspect_s40rts_ulvz_database

  use constants, only: CUSTOM_REAL,SIZE_REAL,SIZE_DOUBLE,NGLLX,NGLLY,NGLLZ, &
    EARTH_R,PI,GRAV,DEGREES_TO_RADIANS
  use shared_parameters, only: MODEL,MODEL_NAME,R_PLANET,RCMB,RHOAV, &
    TRANSVERSE_ISOTROPY,ANISOTROPIC_3D_MANTLE

  implicit none

  double precision, parameter :: CENTER_LAT_DEG = 45.d0
  double precision, parameter :: CENTER_LON_DEG = 140.d0
  double precision, parameter :: THICKNESS_KM = 80.d0
  double precision, parameter :: LATERAL_RADIUS_KM = 400.d0
  double precision, parameter :: LATERAL_TAPER_KM = 100.d0
  double precision, parameter :: TOP_TAPER_KM = 20.d0
  double precision, parameter :: DVS = -0.20d0
  double precision, parameter :: DVP = -0.10d0
  double precision, parameter :: DRHO = 0.05d0
  double precision, parameter :: GEOMETRY_TOL_KM = 1.d-3
  double precision, parameter :: WEIGHT_EPS = 1.d-7
  integer, parameter :: NPROCTOT_VAL = 2

  type solver_db
    integer :: nspec = 0
    integer :: nglob = 0
    real(kind=CUSTOM_REAL), allocatable :: x(:),y(:),z(:)
    integer, allocatable :: ibool(:,:,:,:)
    integer, allocatable :: idoubling(:)
    logical, allocatable :: ispec_is_tiso(:)
    real(kind=CUSTOM_REAL), allocatable :: xix(:,:,:,:),xiy(:,:,:,:),xiz(:,:,:,:)
    real(kind=CUSTOM_REAL), allocatable :: etax(:,:,:,:),etay(:,:,:,:),etaz(:,:,:,:)
    real(kind=CUSTOM_REAL), allocatable :: gammax(:,:,:,:),gammay(:,:,:,:),gammaz(:,:,:,:)
    real(kind=CUSTOM_REAL), allocatable :: rho(:,:,:,:),kappav(:,:,:,:),muv(:,:,:,:)
    real(kind=CUSTOM_REAL), allocatable :: kappah(:,:,:,:),muh(:,:,:,:),eta(:,:,:,:)
  end type solver_db

  type validation_stats
    integer(kind=8) :: category_count(3) = 0_8
    integer(kind=8) :: changed_outside_geometry = 0_8
    integer(kind=8) :: wrong_sign_count = 0_8
    integer(kind=8) :: material_points_changed = 0_8
    integer(kind=8) :: cmb_boundary_noncomparable = 0_8
    double precision :: min_w(3) = 1.d99
    double precision :: max_w(3) = -1.d99
    double precision :: max_geometry_diff = 0.d0
    double precision :: max_residual(5) = 0.d0
    double precision :: min_ratio(5,3) = 1.d99
    double precision :: max_ratio(5,3) = -1.d99
  end type validation_stats

  type viz_export_stats
    integer(kind=8) :: full_source_count = 0_8
    integer(kind=8) :: exported_count = 0_8
    integer(kind=8) :: retained_count(3) = 0_8
    integer(kind=8) :: outside_stride = 1_8
  end type viz_export_stats

  type paraview_mesh_stats
    integer(kind=8) :: rank_local_nodes = 0_8
    integer(kind=8) :: exported_cells = 0_8
  end type paraview_mesh_stats

  type paraview_model_stats
    integer(kind=8) :: exported_records = 0_8
    integer(kind=8) :: selected_elements = 0_8
    integer(kind=8) :: gll_subcells = 0_8
  end type paraview_model_stats

  character(len=512) :: mode,arg1,arg2,arg3
  double precision :: ratio_tol,rplanet_km,rcmb_km
  logical :: tiso_present

  call get_command_argument(1,mode)
  call get_command_argument(2,arg1)
  call get_command_argument(3,arg2)
  call get_command_argument(4,arg3)

  if (len_trim(mode) == 0) call usage()

  call initialize_model_constants(rplanet_km,rcmb_km,tiso_present)
  ratio_tol = precision_aware_ratio_tolerance()

  if (trim(mode) == '--preflight') then
    if (len_trim(arg1) == 0 .or. len_trim(arg2) == 0) call usage()
    call run_preflight(trim(arg1),trim(arg2),rplanet_km,rcmb_km,ratio_tol)
  else if (trim(mode) == '--compare') then
    if (len_trim(arg1) == 0 .or. len_trim(arg2) == 0 .or. len_trim(arg3) == 0) call usage()
    call run_compare(trim(arg1),trim(arg2),trim(arg3),rplanet_km,rcmb_km,ratio_tol,tiso_present)
  else
    call usage()
  endif

contains

  subroutine usage()
    print *,'Usage: inspect_s40rts_ulvz_database --preflight CASE_DIR REPORT_DIR'
    print *,'   or: inspect_s40rts_ulvz_database --compare DISABLED_DIR ENABLED_DIR REPORT_DIR'
    stop 2
  end subroutine usage

  subroutine initialize_model_constants(rplanet_km,rcmb_km,tiso_present)
    double precision, intent(out) :: rplanet_km,rcmb_km
    logical, intent(out) :: tiso_present

    MODEL = 's40rts'
    call get_model_parameters()
    if (trim(MODEL_NAME) /= 's40rts') then
      print *,'Unsupported model constant setup, MODEL_NAME=',trim(MODEL_NAME)
      stop 2
    endif
    rplanet_km = R_PLANET / 1000.d0
    rcmb_km = RCMB / 1000.d0
    if (dabs(rplanet_km - EARTH_R / 1000.d0) > 1.d-9) then
      print *,'Unexpected S40RTS planet radius km=',rplanet_km
      stop 2
    endif
    if (rplanet_km <= 0.d0 .or. rcmb_km <= 0.d0 .or. rcmb_km >= rplanet_km) then
      print *,'Invalid local radius constants R_PLANET/RCMB km=',rplanet_km,rcmb_km
      stop 2
    endif
    tiso_present = TRANSVERSE_ISOTROPY .and. (.not. ANISOTROPIC_3D_MANTLE)
    if (.not. tiso_present) then
      print *,'Unsupported layout: expected S40RTS TISO fields and no full anisotropic mantle'
      stop 2
    endif
  end subroutine initialize_model_constants

  double precision function precision_aware_ratio_tolerance()
    if (CUSTOM_REAL == SIZE_REAL) then
      precision_aware_ratio_tolerance = 5.d-5
    else if (CUSTOM_REAL == SIZE_DOUBLE) then
      precision_aware_ratio_tolerance = 5.d-10
    else
      print *,'Unsupported CUSTOM_REAL size=',CUSTOM_REAL
      stop 2
    endif
  end function precision_aware_ratio_tolerance

  subroutine run_preflight(case_dir,report_dir,rplanet_km,rcmb_km,ratio_tol)
    character(len=*), intent(in) :: case_dir,report_dir
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    type(solver_db) :: db
    type(validation_stats) :: stats
    integer :: iproc
    character(len=512) :: filename
    double precision :: min_r,max_r

    min_r = 1.d99
    max_r = -1.d99
    do iproc = 0,NPROCTOT_VAL - 1
      call make_solver_filename(case_dir,iproc,filename)
      call read_solver_database(trim(filename),db,.true.)
      call validate_coordinate_units(db,rplanet_km,min_r,max_r)
      call accumulate_categories(db,rplanet_km,rcmb_km,stats)
      call free_solver_database(db)
    enddo

    call write_preflight_report(report_dir,stats,min_r,max_r,rplanet_km,rcmb_km,ratio_tol)
    if (any(stats%category_count(:) == 0_8)) then
      print *,'Preflight failed: missing outside/taper/core ULVZ category samples'
      print *,'  outside/taper/core counts=',stats%category_count
      stop 1
    endif
  end subroutine run_preflight

  subroutine run_compare(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km,ratio_tol,tiso_present)
    character(len=*), intent(in) :: disabled_dir,enabled_dir,report_dir
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    logical, intent(in) :: tiso_present
    type(solver_db) :: ref_db,ulvz_db
    type(validation_stats) :: stats
    integer :: iproc
    character(len=512) :: ref_file,ulvz_file
    double precision :: min_r,max_r
    logical :: ok,rank_geometry_ok

    min_r = 1.d99
    max_r = -1.d99
    ok = .true.

    do iproc = 0,NPROCTOT_VAL - 1
      call make_solver_filename(disabled_dir,iproc,ref_file)
      call make_solver_filename(enabled_dir,iproc,ulvz_file)
      call read_solver_database(trim(ref_file),ref_db,tiso_present)
      call read_solver_database(trim(ulvz_file),ulvz_db,tiso_present)
      call validate_coordinate_units(ref_db,rplanet_km,min_r,max_r)
      rank_geometry_ok = .true.
      call compare_geometry_topology(ref_db,ulvz_db,stats,rank_geometry_ok)
      ok = ok .and. rank_geometry_ok
      if (rank_geometry_ok) call compare_materials(ref_db,ulvz_db,rplanet_km,rcmb_km,ratio_tol,stats,ok)
      call free_solver_database(ref_db)
      call free_solver_database(ulvz_db)
    enddo

    call write_comparison_report(report_dir,stats,min_r,max_r,rplanet_km,rcmb_km,ratio_tol,ok)

    if (export_mesh_viz_enabled()) then
      call write_visualization_exports(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km, &
        ratio_tol,tiso_present,stats)
    endif

    if (export_paraview_mesh_enabled()) then
      call write_paraview_mesh_exports(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km, &
        ratio_tol,tiso_present)
    endif

    if (export_paraview_model_enabled()) then
      call write_paraview_model_exports(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km,tiso_present)
    endif

    if (any(stats%category_count(:) == 0_8)) ok = .false.
    if (stats%material_points_changed == 0_8) ok = .false.
    if (stats%changed_outside_geometry /= 0_8) ok = .false.
    if (stats%wrong_sign_count /= 0_8) ok = .false.
    if (any(stats%max_residual(:) > ratio_tol)) ok = .false.

    if (.not. ok) then
      print *,'S40RTS ULVZ database comparison failed; see comparison_summary.txt'
      stop 1
    endif
  end subroutine run_compare

  subroutine make_solver_filename(case_dir,iproc,filename)
    character(len=*), intent(in) :: case_dir
    integer, intent(in) :: iproc
    character(len=*), intent(out) :: filename
    character(len=32) :: procname

    write(procname,"('proc',i6.6,'_reg1_solver_data.bin')") iproc
    filename = trim(case_dir)//'/DATABASES_MPI/'//trim(procname)
  end subroutine make_solver_filename

  subroutine read_solver_database(filename,db,read_tiso)
    character(len=*), intent(in) :: filename
    type(solver_db), intent(inout) :: db
    logical, intent(in) :: read_tiso
    integer :: unit,ier

    open(newunit=unit,file=trim(filename),status='old',form='unformatted', &
      action='read',iostat=ier)
    if (ier /= 0) then
      print *,'Error opening solver database: ',trim(filename)
      stop 1
    endif

    read(unit) db%nspec
    read(unit) db%nglob
    if (db%nspec <= 0 .or. db%nglob <= 0) then
      print *,'Invalid database dimensions in ',trim(filename),db%nspec,db%nglob
      stop 1
    endif

    allocate(db%x(db%nglob),db%y(db%nglob),db%z(db%nglob))
    allocate(db%ibool(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%idoubling(db%nspec),db%ispec_is_tiso(db%nspec))
    allocate(db%xix(NGLLX,NGLLY,NGLLZ,db%nspec),db%xiy(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%xiz(NGLLX,NGLLY,NGLLZ,db%nspec),db%etax(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%etay(NGLLX,NGLLY,NGLLZ,db%nspec),db%etaz(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%gammax(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%gammay(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%gammaz(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%rho(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%kappav(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%muv(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%kappah(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%muh(NGLLX,NGLLY,NGLLZ,db%nspec))
    allocate(db%eta(NGLLX,NGLLY,NGLLZ,db%nspec))

    read(unit) db%x
    read(unit) db%y
    read(unit) db%z
    read(unit) db%ibool
    read(unit) db%idoubling
    read(unit) db%ispec_is_tiso
    read(unit) db%xix
    read(unit) db%xiy
    read(unit) db%xiz
    read(unit) db%etax
    read(unit) db%etay
    read(unit) db%etaz
    read(unit) db%gammax
    read(unit) db%gammay
    read(unit) db%gammaz
    read(unit) db%rho
    read(unit) db%kappav
    read(unit) db%muv
    if (read_tiso) then
      read(unit) db%kappah
      read(unit) db%muh
      read(unit) db%eta
    else
      db%kappah = db%kappav
      db%muh = db%muv
      db%eta = 1._CUSTOM_REAL
    endif
    close(unit)
  end subroutine read_solver_database

  subroutine free_solver_database(db)
    type(solver_db), intent(inout) :: db
    if (allocated(db%x)) deallocate(db%x)
    if (allocated(db%y)) deallocate(db%y)
    if (allocated(db%z)) deallocate(db%z)
    if (allocated(db%ibool)) deallocate(db%ibool)
    if (allocated(db%idoubling)) deallocate(db%idoubling)
    if (allocated(db%ispec_is_tiso)) deallocate(db%ispec_is_tiso)
    if (allocated(db%xix)) deallocate(db%xix,db%xiy,db%xiz)
    if (allocated(db%etax)) deallocate(db%etax,db%etay,db%etaz)
    if (allocated(db%gammax)) deallocate(db%gammax,db%gammay,db%gammaz)
    if (allocated(db%rho)) deallocate(db%rho,db%kappav,db%muv,db%kappah,db%muh,db%eta)
  end subroutine free_solver_database

  subroutine validate_coordinate_units(db,rplanet_km,min_r,max_r)
    type(solver_db), intent(in) :: db
    double precision, intent(in) :: rplanet_km
    double precision, intent(inout) :: min_r,max_r
    double precision :: rnorm,rmax_local,rmin_local
    integer :: iglob

    rmin_local = 1.d99
    rmax_local = -1.d99
    do iglob = 1,db%nglob
      rnorm = dsqrt(dble(db%x(iglob))**2 + dble(db%y(iglob))**2 + dble(db%z(iglob))**2)
      rmin_local = min(rmin_local,rnorm)
      rmax_local = max(rmax_local,rnorm)
    enddo
    min_r = min(min_r,rmin_local)
    max_r = max(max_r,rmax_local)
    if (rmax_local < 0.90d0 .or. rmax_local > 1.10d0) then
      print *,'Unexpected coordinate radius convention; max normalized radius=',rmax_local
      print *,'Local R_PLANET km used for conversion=',rplanet_km
      stop 1
    endif
  end subroutine validate_coordinate_units

  subroutine accumulate_categories(db,rplanet_km,rcmb_km,stats)
    type(solver_db), intent(in) :: db
    double precision, intent(in) :: rplanet_km,rcmb_km
    type(validation_stats), intent(inout) :: stats
    integer :: ispec,i,j,k,iglob,category
    double precision :: w,height,lateral

    do ispec = 1,db%nspec
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            iglob = db%ibool(i,j,k,ispec)
            call analytical_weight(dble(db%x(iglob)),dble(db%y(iglob)),dble(db%z(iglob)), &
              rplanet_km,rcmb_km,w,height,lateral)
            if (height <= GEOMETRY_TOL_KM) then
              stats%cmb_boundary_noncomparable = stats%cmb_boundary_noncomparable + 1_8
              w = 0.d0
            endif
            category = weight_category(w)
            stats%category_count(category) = stats%category_count(category) + 1_8
            stats%min_w(category) = min(stats%min_w(category),w)
            stats%max_w(category) = max(stats%max_w(category),w)
          enddo
        enddo
      enddo
    enddo
  end subroutine accumulate_categories

  subroutine compare_geometry_topology(ref_db,ulvz_db,stats,ok)
    type(solver_db), intent(in) :: ref_db,ulvz_db
    type(validation_stats), intent(inout) :: stats
    logical, intent(inout) :: ok
    double precision :: diff

    if (ref_db%nspec /= ulvz_db%nspec .or. ref_db%nglob /= ulvz_db%nglob) then
      print *,'Geometry dimensions differ'
      ok = .false.
      return
    endif

    diff = maxval(dabs(dble(ref_db%x) - dble(ulvz_db%x)))
    call update_geometry_diff(diff,stats,ok,'xstore')
    diff = maxval(dabs(dble(ref_db%y) - dble(ulvz_db%y)))
    call update_geometry_diff(diff,stats,ok,'ystore')
    diff = maxval(dabs(dble(ref_db%z) - dble(ulvz_db%z)))
    call update_geometry_diff(diff,stats,ok,'zstore')
    if (any(ref_db%ibool /= ulvz_db%ibool)) ok = .false.
    if (any(ref_db%idoubling /= ulvz_db%idoubling)) ok = .false.
    if (any(ref_db%ispec_is_tiso .neqv. ulvz_db%ispec_is_tiso)) ok = .false.

    call update_geometry_diff(max_abs4(ref_db%xix,ulvz_db%xix),stats,ok,'xix')
    call update_geometry_diff(max_abs4(ref_db%xiy,ulvz_db%xiy),stats,ok,'xiy')
    call update_geometry_diff(max_abs4(ref_db%xiz,ulvz_db%xiz),stats,ok,'xiz')
    call update_geometry_diff(max_abs4(ref_db%etax,ulvz_db%etax),stats,ok,'etax')
    call update_geometry_diff(max_abs4(ref_db%etay,ulvz_db%etay),stats,ok,'etay')
    call update_geometry_diff(max_abs4(ref_db%etaz,ulvz_db%etaz),stats,ok,'etaz')
    call update_geometry_diff(max_abs4(ref_db%gammax,ulvz_db%gammax),stats,ok,'gammax')
    call update_geometry_diff(max_abs4(ref_db%gammay,ulvz_db%gammay),stats,ok,'gammay')
    call update_geometry_diff(max_abs4(ref_db%gammaz,ulvz_db%gammaz),stats,ok,'gammaz')
  end subroutine compare_geometry_topology

  subroutine update_geometry_diff(diff,stats,ok,name)
    double precision, intent(in) :: diff
    type(validation_stats), intent(inout) :: stats
    logical, intent(inout) :: ok
    character(len=*), intent(in) :: name
    stats%max_geometry_diff = max(stats%max_geometry_diff,diff)
    if (diff /= 0.d0) then
      print *,'Geometry/topology record differs: ',trim(name),' maxdiff=',diff
      ok = .false.
    endif
  end subroutine update_geometry_diff

  double precision function max_abs4(a,b)
    real(kind=CUSTOM_REAL), intent(in) :: a(:,:,:,:),b(:,:,:,:)
    max_abs4 = maxval(dabs(dble(a) - dble(b)))
  end function max_abs4

  subroutine compare_materials(ref_db,ulvz_db,rplanet_km,rcmb_km,ratio_tol,stats,ok)
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    type(validation_stats), intent(inout) :: stats
    logical, intent(inout) :: ok
    integer :: ispec,i,j,k,iglob,category
    double precision :: w,height,lateral,expected(5),ratio(5),resid(5)
    double precision :: ref_vpv,ulvz_vpv,ref_vph,ulvz_vph,ref_vsv,ulvz_vsv,ref_vsh,ulvz_vsh

    do ispec = 1,ref_db%nspec
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            iglob = ref_db%ibool(i,j,k,ispec)
            call analytical_weight(dble(ref_db%x(iglob)),dble(ref_db%y(iglob)), &
              dble(ref_db%z(iglob)),rplanet_km,rcmb_km,w,height,lateral)
            if (height <= GEOMETRY_TOL_KM) then
              stats%cmb_boundary_noncomparable = stats%cmb_boundary_noncomparable + 1_8
              w = 0.d0
            endif
            category = weight_category(w)
            stats%category_count(category) = stats%category_count(category) + 1_8
            stats%min_w(category) = min(stats%min_w(category),w)
            stats%max_w(category) = max(stats%max_w(category),w)

            call require_positive(dble(ref_db%rho(i,j,k,ispec)),'rho disabled')
            call require_positive(dble(ulvz_db%rho(i,j,k,ispec)),'rho enabled')
            ref_vsv = dble(ref_db%muv(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vsv = dble(ulvz_db%muv(i,j,k,ispec)) / dble(ulvz_db%rho(i,j,k,ispec))
            ref_vsh = dble(ref_db%muh(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vsh = dble(ulvz_db%muh(i,j,k,ispec)) / dble(ulvz_db%rho(i,j,k,ispec))
            ref_vpv = (dble(ref_db%kappav(i,j,k,ispec)) + 4.d0 * dble(ref_db%muv(i,j,k,ispec)) / 3.d0) &
              / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vpv = (dble(ulvz_db%kappav(i,j,k,ispec)) + 4.d0 * dble(ulvz_db%muv(i,j,k,ispec)) / 3.d0) &
              / dble(ulvz_db%rho(i,j,k,ispec))
            ref_vph = (dble(ref_db%kappah(i,j,k,ispec)) + 4.d0 * dble(ref_db%muh(i,j,k,ispec)) / 3.d0) &
              / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vph = (dble(ulvz_db%kappah(i,j,k,ispec)) + 4.d0 * dble(ulvz_db%muh(i,j,k,ispec)) / 3.d0) &
              / dble(ulvz_db%rho(i,j,k,ispec))
            call require_positive(ref_vsv,'vsv disabled')
            call require_positive(ulvz_vsv,'vsv enabled')
            call require_positive(ref_vsh,'vsh disabled')
            call require_positive(ulvz_vsh,'vsh enabled')
            call require_positive(ref_vpv,'vpv disabled')
            call require_positive(ulvz_vpv,'vpv enabled')
            call require_positive(ref_vph,'vph disabled')
            call require_positive(ulvz_vph,'vph enabled')

            ratio(1) = dble(ulvz_db%rho(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
            ratio(2) = dsqrt(ulvz_vsv / ref_vsv)
            ratio(3) = dsqrt(ulvz_vsh / ref_vsh)
            ratio(4) = dsqrt(ulvz_vpv / ref_vpv)
            ratio(5) = dsqrt(ulvz_vph / ref_vph)
            expected = (/1.d0 + w * DRHO,1.d0 + w * DVS,1.d0 + w * DVS, &
              1.d0 + w * DVP,1.d0 + w * DVP/)
            resid = dabs(ratio - expected)
            stats%max_residual = max(stats%max_residual,resid)
            stats%min_ratio(:,category) = min(stats%min_ratio(:,category),ratio)
            stats%max_ratio(:,category) = max(stats%max_ratio(:,category),ratio)

            if (any(dabs(ratio - 1.d0) > ratio_tol)) stats%material_points_changed = &
              stats%material_points_changed + 1_8
            if ((height < -GEOMETRY_TOL_KM .or. lateral > LATERAL_RADIUS_KM + GEOMETRY_TOL_KM) &
              .and. any(dabs(ratio - 1.d0) > ratio_tol)) stats%changed_outside_geometry = &
              stats%changed_outside_geometry + 1_8
            if (w > WEIGHT_EPS) call check_wrong_sign(ratio,ratio_tol,stats)
            if (any(resid > ratio_tol)) ok = .false.
          enddo
        enddo
      enddo
    enddo
  end subroutine compare_materials

  subroutine require_positive(value,name)
    double precision, intent(in) :: value
    character(len=*), intent(in) :: name
    if (value <= 0.d0) then
      print *,'Non-positive reconstructed material value: ',trim(name),value
      stop 1
    endif
  end subroutine require_positive

  subroutine check_wrong_sign(ratio,ratio_tol,stats)
    double precision, intent(in) :: ratio(5),ratio_tol
    type(validation_stats), intent(inout) :: stats
    if (ratio(1) < 1.d0 - ratio_tol) stats%wrong_sign_count = stats%wrong_sign_count + 1_8
    if (ratio(2) > 1.d0 + ratio_tol) stats%wrong_sign_count = stats%wrong_sign_count + 1_8
    if (ratio(3) > 1.d0 + ratio_tol) stats%wrong_sign_count = stats%wrong_sign_count + 1_8
    if (ratio(4) > 1.d0 + ratio_tol) stats%wrong_sign_count = stats%wrong_sign_count + 1_8
    if (ratio(5) > 1.d0 + ratio_tol) stats%wrong_sign_count = stats%wrong_sign_count + 1_8
  end subroutine check_wrong_sign

  subroutine analytical_weight(x,y,z,rplanet_km,rcmb_km,w,height,lateral)
    double precision, intent(in) :: x,y,z,rplanet_km,rcmb_km
    double precision, intent(out) :: w,height,lateral
    double precision :: rnorm,lat,lon,cosang,lat0,lon0,lw,tw,xx,yy

    rnorm = dsqrt(x*x + y*y + z*z)
    if (rnorm <= 0.d0) then
      w = 0.d0
      height = -1.d99
      lateral = 1.d99
      return
    endif

    height = rnorm * rplanet_km - rcmb_km
    lat = dasin(max(-1.d0,min(1.d0,z / rnorm)))
    lon = datan2(y,x)
    lat0 = CENTER_LAT_DEG * DEGREES_TO_RADIANS
    lon0 = CENTER_LON_DEG * DEGREES_TO_RADIANS
    cosang = dsin(lat) * dsin(lat0) + dcos(lat) * dcos(lat0) * dcos(lon - lon0)
    cosang = max(-1.d0,min(1.d0,cosang))
    lateral = rcmb_km * dacos(cosang)

    if (height < 0.d0 .or. height > THICKNESS_KM .or. lateral > LATERAL_RADIUS_KM) then
      w = 0.d0
      return
    endif

    if (LATERAL_TAPER_KM == 0.d0 .or. lateral <= LATERAL_RADIUS_KM - LATERAL_TAPER_KM) then
      lw = 1.d0
    else
      xx = (lateral - (LATERAL_RADIUS_KM - LATERAL_TAPER_KM)) / LATERAL_TAPER_KM
      lw = 0.5d0 * (1.d0 + dcos(PI * xx))
    endif

    if (TOP_TAPER_KM == 0.d0 .or. height <= THICKNESS_KM - TOP_TAPER_KM) then
      tw = 1.d0
    else
      yy = (height - (THICKNESS_KM - TOP_TAPER_KM)) / TOP_TAPER_KM
      tw = 0.5d0 * (1.d0 + dcos(PI * yy))
    endif

    w = lw * tw
  end subroutine analytical_weight

  integer function weight_category(w)
    double precision, intent(in) :: w
    if (w <= WEIGHT_EPS) then
      weight_category = 1
    else if (w >= 1.d0 - WEIGHT_EPS) then
      weight_category = 3
    else
      weight_category = 2
    endif
  end function weight_category

  subroutine write_preflight_report(report_dir,stats,min_r,max_r,rplanet_km,rcmb_km,ratio_tol)
    character(len=*), intent(in) :: report_dir
    type(validation_stats), intent(in) :: stats
    double precision, intent(in) :: min_r,max_r,rplanet_km,rcmb_km,ratio_tol
    integer :: unit

    open(newunit=unit,file=trim(report_dir)//'/preflight_summary.txt',status='replace',action='write')
    write(unit,'(a)') 'S40RTS ULVZ mesh preflight'
    write(unit,'(a,a)') 'MODEL_NAME: ',trim(MODEL_NAME)
    write(unit,'(a,i0)') 'CUSTOM_REAL bytes: ',CUSTOM_REAL
    write(unit,'(a,es16.8)') 'ratio tolerance: ',ratio_tol
    write(unit,'(a,es16.8)') 'geometry tolerance km: ',GEOMETRY_TOL_KM
    write(unit,'(a,2es16.8)') 'normalized radius min/max: ',min_r,max_r
    write(unit,'(a,2es16.8)') 'R_PLANET_km RCMB_km: ',rplanet_km,rcmb_km
    write(unit,'(a,3i16)') 'outside taper core counts: ',stats%category_count
    write(unit,'(a,i16)') 'CMB boundary non-comparable count: ',stats%cmb_boundary_noncomparable
    write(unit,'(a,3es16.8)') 'min w outside/taper/core: ',stats%min_w
    write(unit,'(a,3es16.8)') 'max w outside/taper/core: ',stats%max_w
    if (any(stats%category_count(:) == 0_8)) then
      write(unit,'(a)') 'status: FAIL missing one or more categories'
    else
      write(unit,'(a)') 'status: PASS'
    endif
    close(unit)

    open(newunit=unit,file=trim(report_dir)//'/preflight_summary.csv',status='replace',action='write')
    write(unit,'(a)') 'metric,outside,taper,core'
    write(unit,'(a,3(",",i0))') 'count',stats%category_count
    write(unit,'(a,3(",",es16.8))') 'min_w',stats%min_w
    write(unit,'(a,3(",",es16.8))') 'max_w',stats%max_w
    close(unit)
  end subroutine write_preflight_report

  subroutine write_comparison_report(report_dir,stats,min_r,max_r,rplanet_km,rcmb_km,ratio_tol,ok)
    character(len=*), intent(in) :: report_dir
    type(validation_stats), intent(in) :: stats
    double precision, intent(in) :: min_r,max_r,rplanet_km,rcmb_km,ratio_tol
    logical, intent(in) :: ok
    integer :: unit,ifield,icat
    character(len=8), parameter :: field_names(5) = (/ 'rho     ','vsv     ','vsh     ','vpv     ','vph     ' /)
    character(len=8), parameter :: cat_names(3) = (/ 'outside ','taper   ','core    ' /)

    open(newunit=unit,file=trim(report_dir)//'/comparison_summary.txt',status='replace',action='write')
    write(unit,'(a)') 'S40RTS ULVZ mesh database comparison'
    write(unit,'(a,a)') 'MODEL_NAME: ',trim(MODEL_NAME)
    write(unit,'(a,i0)') 'CUSTOM_REAL bytes: ',CUSTOM_REAL
    write(unit,'(a,es16.8)') 'ratio tolerance: ',ratio_tol
    write(unit,'(a,es16.8)') 'geometry tolerance km: ',GEOMETRY_TOL_KM
    write(unit,'(a,2es16.8)') 'normalized radius min/max: ',min_r,max_r
    write(unit,'(a,2es16.8)') 'R_PLANET_km RCMB_km: ',rplanet_km,rcmb_km
    write(unit,'(a,3i16)') 'outside taper core counts: ',stats%category_count
    write(unit,'(a,i16)') 'CMB boundary non-comparable count: ',stats%cmb_boundary_noncomparable
    write(unit,'(a,3es16.8)') 'min w outside/taper/core: ',stats%min_w
    write(unit,'(a,3es16.8)') 'max w outside/taper/core: ',stats%max_w
    write(unit,'(a,es16.8)') 'max geometry/topology real-record difference: ',stats%max_geometry_diff
    write(unit,'(a,i16)') 'material points changed: ',stats%material_points_changed
    write(unit,'(a,i16)') 'outside-geometry changed count: ',stats%changed_outside_geometry
    write(unit,'(a,i16)') 'wrong-sign material response count: ',stats%wrong_sign_count
    write(unit,'(a)') 'field formulas:'
    write(unit,'(a)') 'rho=rho_enabled/rho_disabled'
    write(unit,'(a)') 'vsv=sqrt((muv/rho)_enabled/(muv/rho)_disabled)'
    write(unit,'(a)') 'vsh=sqrt((muh/rho)_enabled/(muh/rho)_disabled)'
    write(unit,'(a)') 'vpv=sqrt(((kappav+4/3*muv)/rho)_enabled/same_disabled)'
    write(unit,'(a)') 'vph=sqrt(((kappah+4/3*muh)/rho)_enabled/same_disabled)'
    do ifield = 1,5
      write(unit,'(a,a,a,es16.8)') 'max residual ',trim(field_names(ifield)),': ', &
        stats%max_residual(ifield)
      do icat = 1,3
        write(unit,'(a,a,a,a,2es16.8)') 'ratio min/max ',trim(field_names(ifield)), &
          ' ',trim(cat_names(icat)),stats%min_ratio(ifield,icat),stats%max_ratio(ifield,icat)
      enddo
    enddo
    if (ok) then
      write(unit,'(a)') 'status: PASS'
    else
      write(unit,'(a)') 'status: FAIL'
    endif
    close(unit)

    open(newunit=unit,file=trim(report_dir)//'/comparison_summary.csv',status='replace',action='write')
    write(unit,'(a)') 'record,field,category,value'
    write(unit,'(a,",",a,",",a,",",es16.8)') 'tolerance','ratio','all',ratio_tol
    write(unit,'(a,",",a,",",a,",",es16.8)') 'geometry_tolerance_km','geometry','all',GEOMETRY_TOL_KM
    do icat = 1,3
      write(unit,'(a,",",a,",",a,",",i0)') 'category_count','w',trim(cat_names(icat)), &
        stats%category_count(icat)
    enddo
    do ifield = 1,5
      write(unit,'(a,",",a,",",a,",",es16.8)') 'max_residual',trim(field_names(ifield)), &
        'all',stats%max_residual(ifield)
      do icat = 1,3
        write(unit,'(a,",",a,",",a,",",es16.8)') 'min_ratio',trim(field_names(ifield)), &
          trim(cat_names(icat)),stats%min_ratio(ifield,icat)
        write(unit,'(a,",",a,",",a,",",es16.8)') 'max_ratio',trim(field_names(ifield)), &
          trim(cat_names(icat)),stats%max_ratio(ifield,icat)
      enddo
    enddo
    close(unit)
  end subroutine write_comparison_report

  logical function export_mesh_viz_enabled()
    character(len=32) :: value
    integer :: length,status
    value = ''
    call get_environment_variable('EXPORT_MESH_VIZ_DATA',value,length,status)
    export_mesh_viz_enabled = .false.
    if (status == 0 .and. length > 0) export_mesh_viz_enabled = (trim(value(1:length)) == '1')
  end function export_mesh_viz_enabled

  logical function export_paraview_mesh_enabled()
    character(len=32) :: value
    integer :: length,status
    value = ''
    call get_environment_variable('EXPORT_PARAVIEW_MESH_DATA',value,length,status)
    export_paraview_mesh_enabled = .false.
    if (status == 0 .and. length > 0) export_paraview_mesh_enabled = (trim(value(1:length)) == '1')
  end function export_paraview_mesh_enabled

  logical function export_paraview_model_enabled()
    character(len=32) :: value
    integer :: length,status
    value = ''
    call get_environment_variable('EXPORT_PARAVIEW_MODEL_DATA',value,length,status)
    export_paraview_model_enabled = .false.
    if (status == 0 .and. length > 0) export_paraview_model_enabled = (trim(value(1:length)) == '1')
  end function export_paraview_model_enabled

  subroutine write_paraview_model_exports(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km,tiso_present)
    character(len=*), intent(in) :: disabled_dir,enabled_dir,report_dir
    double precision, intent(in) :: rplanet_km,rcmb_km
    logical, intent(in) :: tiso_present
    type(solver_db) :: ref_db,ulvz_db
    type(paraview_model_stats) :: model_stats,rank_stats
    integer :: iproc,max_cells
    character(len=512) :: ref_file,ulvz_file,region
    double precision :: context_margin_km

    call get_env_or_default('PARAVIEW_MODEL_EXPORT_REGION','ulvz-window',region)
    max_cells = get_env_int_default('PARAVIEW_MODEL_EXPORT_MAX_CELLS',1600000)
    context_margin_km = get_env_double_default('PARAVIEW_MODEL_EXPORT_CONTEXT_MARGIN_KM',-1.d0)
    if (trim(region) /= 'all' .and. trim(region) /= 'near-cmb' .and. &
        trim(region) /= 'ulvz-window') then
      print *,'Unsupported PARAVIEW_MODEL_EXPORT_REGION=',trim(region)
      stop 2
    endif

    do iproc = 0,NPROCTOT_VAL - 1
      call make_solver_filename(disabled_dir,iproc,ref_file)
      call make_solver_filename(enabled_dir,iproc,ulvz_file)
      call read_solver_database(trim(ref_file),ref_db,tiso_present)
      call read_solver_database(trim(ulvz_file),ulvz_db,tiso_present)
      call validate_paraview_model_pairing(iproc,ref_db,ulvz_db,rplanet_km)
      call write_rank_paraview_model_records(report_dir,iproc,ref_db,ulvz_db,rplanet_km,rcmb_km, &
        trim(region),context_margin_km,rank_stats)
      model_stats%exported_records = model_stats%exported_records + rank_stats%exported_records
      model_stats%selected_elements = model_stats%selected_elements + rank_stats%selected_elements
      model_stats%gll_subcells = model_stats%gll_subcells + rank_stats%gll_subcells
      if (model_stats%gll_subcells > int(max_cells,kind=8)) then
        print *,'PARAVIEW_MODEL_EXPORT_MAX_CELLS exceeded: ',model_stats%gll_subcells,max_cells
        stop 1
      endif
      call free_solver_database(ref_db)
      call free_solver_database(ulvz_db)
    enddo
    call write_paraview_model_metadata(report_dir,rplanet_km,rcmb_km,trim(region), &
      context_margin_km,max_cells,tiso_present,model_stats)
  end subroutine write_paraview_model_exports

  subroutine validate_paraview_model_pairing(iproc,ref_db,ulvz_db,rplanet_km)
    integer, intent(in) :: iproc
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km
    integer :: ispec,i,j,k,iglob_ref,iglob_ulvz
    double precision :: dx,dy,dz

    if (ref_db%nspec /= ulvz_db%nspec .or. ref_db%nglob /= ulvz_db%nglob) then
      print *,'ParaView model pairing mismatch dimensions rank=',iproc, &
        ' ref nspec/nglob=',ref_db%nspec,ref_db%nglob, &
        ' enabled nspec/nglob=',ulvz_db%nspec,ulvz_db%nglob
      stop 1
    endif
    if (any(ref_db%idoubling /= ulvz_db%idoubling)) then
      print *,'ParaView model pairing mismatch idoubling rank=',iproc
      stop 1
    endif
    if (any(ref_db%ispec_is_tiso .neqv. ulvz_db%ispec_is_tiso)) then
      print *,'ParaView model pairing mismatch ispec_is_tiso rank=',iproc
      stop 1
    endif
    if (any(ref_db%ibool /= ulvz_db%ibool)) then
      print *,'ParaView model pairing mismatch ibool rank=',iproc
      stop 1
    endif

    do ispec = 1,ref_db%nspec
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            iglob_ref = ref_db%ibool(i,j,k,ispec)
            iglob_ulvz = ulvz_db%ibool(i,j,k,ispec)
            if (iglob_ref /= iglob_ulvz) then
              print *,'ParaView model pairing iglob mismatch rank/ispec/i/j/k=', &
                iproc,ispec,i,j,k,' ref/enabled=',iglob_ref,iglob_ulvz
              stop 1
            endif
            dx = dabs(dble(ref_db%x(iglob_ref)) - dble(ulvz_db%x(iglob_ulvz))) * rplanet_km
            dy = dabs(dble(ref_db%y(iglob_ref)) - dble(ulvz_db%y(iglob_ulvz))) * rplanet_km
            dz = dabs(dble(ref_db%z(iglob_ref)) - dble(ulvz_db%z(iglob_ulvz))) * rplanet_km
            if (max(dx,dy,dz) > 1.d-9) then
              print *,'ParaView model pairing coordinate mismatch km rank/ispec/i/j/k/iglob=', &
                iproc,ispec,i,j,k,iglob_ref,' maxdiff=',max(dx,dy,dz)
              stop 1
            endif
          enddo
        enddo
      enddo
    enddo
  end subroutine validate_paraview_model_pairing

  subroutine write_rank_paraview_model_records(report_dir,iproc,ref_db,ulvz_db,rplanet_km,rcmb_km, &
      region,context_margin_km,rank_stats)
    character(len=*), intent(in) :: report_dir,region
    integer, intent(in) :: iproc
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km,rcmb_km,context_margin_km
    type(paraview_model_stats), intent(out) :: rank_stats
    logical, allocatable :: selected(:)
    integer :: unit,ispec,i,j,k
    character(len=512) :: records_file

    rank_stats%exported_records = 0_8
    rank_stats%selected_elements = 0_8
    rank_stats%gll_subcells = 0_8
    allocate(selected(ref_db%nspec))
    selected = .false.

    do ispec = 1,ref_db%nspec
      selected(ispec) = paraview_cell_selected(ref_db,ispec,rplanet_km,rcmb_km,region,context_margin_km)
      if (selected(ispec)) then
        rank_stats%selected_elements = rank_stats%selected_elements + 1_8
        rank_stats%gll_subcells = rank_stats%gll_subcells + &
          int((NGLLX - 1) * (NGLLY - 1) * (NGLLZ - 1),kind=8)
      endif
    enddo

    write(records_file,"(a,'/paraview_model_records_rank',i6.6,'.csv')") trim(report_dir),iproc
    open(newunit=unit,file=trim(records_file),status='replace',action='write')
    call write_paraview_model_header(unit)
    do ispec = 1,ref_db%nspec
      if (.not. selected(ispec)) cycle
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            call write_paraview_model_record(unit,iproc,ispec,i,j,k,ref_db,ulvz_db,rplanet_km,rcmb_km)
            rank_stats%exported_records = rank_stats%exported_records + 1_8
          enddo
        enddo
      enddo
    enddo
    close(unit)
    deallocate(selected)
  end subroutine write_rank_paraview_model_records

  subroutine write_paraview_model_header(unit)
    integer, intent(in) :: unit
    write(unit,'(a)') 'rank,ispec,i,j,k,iglob,x_norm,y_norm,z_norm,'// &
      'radius_km,depth_km,height_above_cmb_km,latitude_deg,longitude_deg,'// &
      'vp,vs,rho,vpv,vph,vsv,vsh,eta,'// &
      'vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio,is_tiso'
  end subroutine write_paraview_model_header

  subroutine write_paraview_model_record(unit,iproc,ispec,i,j,k,ref_db,ulvz_db,rplanet_km,rcmb_km)
    integer, intent(in) :: unit,iproc,ispec,i,j,k
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km,rcmb_km
    integer :: iglob
    double precision :: radius_norm,radius_km,depth_km,lat_deg,lon_deg
    double precision :: point_azimuth_deg,angular_distance_deg,section_distance_km,cross_offset_km
    double precision :: ref_vp,ref_vs,ref_rho,ref_vpv,ref_vph,ref_vsv,ref_vsh,ref_eta
    double precision :: vp,vs,rho,vpv,vph,vsv,vsh,eta
    double precision :: vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio

    iglob = ulvz_db%ibool(i,j,k,ispec)
    call point_coordinates(dble(ulvz_db%x(iglob)),dble(ulvz_db%y(iglob)),dble(ulvz_db%z(iglob)), &
      rplanet_km,rcmb_km,radius_norm,radius_km,depth_km,lat_deg,lon_deg, &
      point_azimuth_deg,angular_distance_deg,section_distance_km,cross_offset_km)
    call final_model_values(ref_db,iproc,ispec,i,j,k,'disabled', &
      ref_vp,ref_vs,ref_rho,ref_vpv,ref_vph,ref_vsv,ref_vsh,ref_eta)
    call final_model_values(ulvz_db,iproc,ispec,i,j,k,'enabled', &
      vp,vs,rho,vpv,vph,vsv,vsh,eta)
    call compute_model_ratios(iproc,ispec,i,j,k,iglob, &
      ref_vp,ref_vs,ref_rho,ref_vpv,ref_vph,ref_vsv,ref_vsh, &
      vp,vs,rho,vpv,vph,vsv,vsh, &
      vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio)
    write(unit,'(i0,",",i0,",",i0,",",i0,",",i0,",",i0,23(",",es24.16),",",a)') &
      iproc,ispec,i,j,k,iglob, &
      dble(ulvz_db%x(iglob)),dble(ulvz_db%y(iglob)),dble(ulvz_db%z(iglob)),radius_km,depth_km, &
      radius_km - rcmb_km,lat_deg,lon_deg,vp,vs,rho,vpv,vph,vsv,vsh,eta, &
      vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio, &
      trim(logical_string(ulvz_db%ispec_is_tiso(ispec)))
  end subroutine write_paraview_model_record

  subroutine final_model_values(db,iproc,ispec,i,j,k,label,vp,vs,rho,vpv,vph,vsv,vsh,eta)
    type(solver_db), intent(in) :: db
    integer, intent(in) :: iproc,ispec,i,j,k
    character(len=*), intent(in) :: label
    double precision, intent(out) :: vp,vs,rho,vpv,vph,vsv,vsh,eta
    double precision :: rho_solver,kappav,kappah,muv,muh,scale_velocity,scale_density
    integer :: iglob

    iglob = db%ibool(i,j,k,ispec)
    rho_solver = dble(db%rho(i,j,k,ispec))
    kappav = dble(db%kappav(i,j,k,ispec))
    kappah = dble(db%kappah(i,j,k,ispec))
    muv = dble(db%muv(i,j,k,ispec))
    muh = dble(db%muh(i,j,k,ispec))
    eta = dble(db%eta(i,j,k,ispec))
    call require_positive_model(rho_solver,'rho solver',trim(label),iproc,ispec,i,j,k,iglob)
    call require_positive_model(muv / rho_solver,'vsv solver',trim(label),iproc,ispec,i,j,k,iglob)
    call require_positive_model(muh / rho_solver,'vsh solver',trim(label),iproc,ispec,i,j,k,iglob)
    call require_positive_model((kappav + 4.d0 * muv / 3.d0) / rho_solver, &
      'vpv solver',trim(label),iproc,ispec,i,j,k,iglob)
    call require_positive_model((kappah + 4.d0 * muh / 3.d0) / rho_solver, &
      'vph solver',trim(label),iproc,ispec,i,j,k,iglob)

    scale_velocity = dsqrt(PI * GRAV * RHOAV) * (R_PLANET / 1000.d0)
    scale_density = RHOAV / 1000.d0
    vsv = dsqrt(muv / rho_solver) * scale_velocity
    vsh = dsqrt(muh / rho_solver) * scale_velocity
    vpv = dsqrt((kappav + 4.d0 * muv / 3.d0) / rho_solver) * scale_velocity
    vph = dsqrt((kappah + 4.d0 * muh / 3.d0) / rho_solver) * scale_velocity
    rho = rho_solver * scale_density
    vp = vpv
    vs = vsv
  end subroutine final_model_values

  subroutine compute_model_ratios(iproc,ispec,i,j,k,iglob, &
      ref_vp,ref_vs,ref_rho,ref_vpv,ref_vph,ref_vsv,ref_vsh, &
      vp,vs,rho,vpv,vph,vsv,vsh, &
      vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio)
    integer, intent(in) :: iproc,ispec,i,j,k,iglob
    double precision, intent(in) :: ref_vp,ref_vs,ref_rho,ref_vpv,ref_vph,ref_vsv,ref_vsh
    double precision, intent(in) :: vp,vs,rho,vpv,vph,vsv,vsh
    double precision, intent(out) :: vp_ratio,vs_ratio,rho_ratio,vpv_ratio,vph_ratio,vsv_ratio,vsh_ratio

    call require_positive_model(ref_vp,'vp denominator','disabled',iproc,ispec,i,j,k,iglob)
    call require_positive_model(ref_vs,'vs denominator','disabled',iproc,ispec,i,j,k,iglob)
    call require_positive_model(ref_rho,'rho denominator','disabled',iproc,ispec,i,j,k,iglob)
    call require_positive_model(ref_vpv,'vpv denominator','disabled',iproc,ispec,i,j,k,iglob)
    call require_positive_model(ref_vph,'vph denominator','disabled',iproc,ispec,i,j,k,iglob)
    call require_positive_model(ref_vsv,'vsv denominator','disabled',iproc,ispec,i,j,k,iglob)
    call require_positive_model(ref_vsh,'vsh denominator','disabled',iproc,ispec,i,j,k,iglob)
    vp_ratio = vp / ref_vp
    vs_ratio = vs / ref_vs
    rho_ratio = rho / ref_rho
    vpv_ratio = vpv / ref_vpv
    vph_ratio = vph / ref_vph
    vsv_ratio = vsv / ref_vsv
    vsh_ratio = vsh / ref_vsh
  end subroutine compute_model_ratios

  subroutine require_positive_model(value,field,label,iproc,ispec,i,j,k,iglob)
    double precision, intent(in) :: value
    character(len=*), intent(in) :: field,label
    integer, intent(in) :: iproc,ispec,i,j,k,iglob
    if (.not. (value > 0.d0) .or. dabs(value) >= huge(value)) then
      print *,'ParaView model export non-positive/invalid value field=',trim(field), &
        ' case=',trim(label),' rank/ispec/i/j/k/iglob=',iproc,ispec,i,j,k,iglob,' value=',value
      stop 1
    endif
  end subroutine require_positive_model

  subroutine write_paraview_model_metadata(report_dir,rplanet_km,rcmb_km,region,context_margin_km, &
      max_cells,tiso_present,model_stats)
    character(len=*), intent(in) :: report_dir,region
    double precision, intent(in) :: rplanet_km,rcmb_km,context_margin_km
    integer, intent(in) :: max_cells
    logical, intent(in) :: tiso_present
    type(paraview_model_stats), intent(in) :: model_stats
    integer :: unit
    double precision :: scale_velocity,scale_density

    scale_velocity = dsqrt(PI * GRAV * RHOAV) * (R_PLANET / 1000.d0)
    scale_density = RHOAV / 1000.d0
    open(newunit=unit,file=trim(report_dir)//'/paraview_model_metadata.json',status='replace',action='write')
    write(unit,'(a)') '{'
    write(unit,'(a)') '  "schema_version": "ulvz_paraview_model.v1",'
    write(unit,'(a)') '  "producer": "inspect_s40rts_ulvz_database.f90",'
    write(unit,'(a)') '  "source": "proc*_reg1_solver_data.bin",'
    write(unit,'(a)') '  "coordinate_units": "km",'
    write(unit,'(a)') '  "coordinate_conversion": "x/y/z = x_norm/y_norm/z_norm * r_planet_km",'
    write(unit,'(a,es16.8,a)') '  "r_planet_km": ',rplanet_km,','
    write(unit,'(a,es16.8,a)') '  "rcmb_km": ',rcmb_km,','
    write(unit,'(a)') '  "model_field_units": {"vp": "km/s", "vs": "km/s", "rho": "g/cm^3"},'
    write(unit,'(a)') '  "ratio_field_units": "dimensionless",'
    write(unit,'(a)') '  "ratio_fields": ["vp_ratio", "vs_ratio", "rho_ratio",'
    write(unit,'(a)') '    "vpv_ratio", "vph_ratio", "vsv_ratio", "vsh_ratio"],'
    write(unit,'(a)') '  "ratio_pairing": "element-local by identical rank,ispec,i,j,k; '// &
      'iglob and coordinates must also match",'
    write(unit,'(a)') '  "ratio_velocity_rule": "enabled and disabled physical velocities are derived '// &
      'with the same solver definitions before division",'
    write(unit,'(a)') '  "cell_ratio_summary_rule": "arithmetic mean of the eight corner ratio values '// &
      'for each exported linear GLL subcell",'
    write(unit,'(a)') '  "solver_fields": ["rhostore", "kappavstore", "muvstore",'
    write(unit,'(a)') '    "kappahstore", "muhstore", "eta_anisostore"],'
    write(unit,'(a,es16.8,a)') '  "velocity_scale_to_km_per_s": ',scale_velocity,','
    write(unit,'(a,es16.8,a)') '  "density_scale_to_g_per_cm3": ',scale_density,','
    write(unit,'(a,i0,a,i0,a,i0,a)') '  "ngll": {"x": ',NGLLX,', "y": ',NGLLY,', "z": ',NGLLZ,'},'
    write(unit,'(a)') '  "cell_type": "VTK_HEXAHEDRON",'
    write(unit,'(a)') '  "geometry_note": "GLL-node-resolved linear subcell visualization '// &
      'of the computational spectral-element mesh",'
    write(unit,'(a)') '  "subcell_ordering": ['
    write(unit,'(a)') '    "(i,j,k)", "(i+1,j,k)", "(i+1,j+1,k)", "(i,j+1,k)",'
    write(unit,'(a)') '    "(i,j,k+1)", "(i+1,j,k+1)", "(i+1,j+1,k+1)", "(i,j+1,k+1)"'
    write(unit,'(a)') '  ],'
    write(unit,'(a,a,a)') '  "region": "',trim(region),'",'
    write(unit,'(a,i0,a)') '  "max_cells": ',max_cells,','
    if (context_margin_km >= 0.d0) then
      write(unit,'(a,es16.8,a)') '  "context_margin_km": ',context_margin_km,','
    else
      write(unit,'(a)') '  "context_margin_km": null,'
    endif
    write(unit,'(a)') '  "selection_rule": "export an element when any GLL point is inside the requested region",'
    write(unit,'(a)') '  "node_merge_policy": "rank-local-field-aware",'
    write(unit,'(a)') '  "merge_tolerances": {"coordinate_abs_km": 1.0e-9, "field_abs": 1.0e-8},'
    write(unit,'(a)') '  "pointdata_ownership_note": "PointData does not claim unique ispec/i/j/k ownership",'
    write(unit,'(a,a,a)') '  "tiso_present": ',trim(logical_string(tiso_present)),','
    write(unit,'(a,i0,a)') '  "number_of_ranks": ',NPROCTOT_VAL,','
    write(unit,'(a,i0,a)') '  "number_of_spectral_elements": ',model_stats%selected_elements,','
    write(unit,'(a,i0,a)') '  "number_of_gll_subcells": ',model_stats%gll_subcells,','
    write(unit,'(a,i0)') '  "number_of_raw_records": ',model_stats%exported_records
    write(unit,'(a)') '}'
    close(unit)
  end subroutine write_paraview_model_metadata

  subroutine write_paraview_mesh_exports(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km, &
      ratio_tol,tiso_present)
    character(len=*), intent(in) :: disabled_dir,enabled_dir,report_dir
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    logical, intent(in) :: tiso_present
    type(solver_db) :: ref_db,ulvz_db
    type(paraview_mesh_stats) :: mesh_stats,rank_stats
    integer :: iproc,max_cells
    character(len=512) :: ref_file,ulvz_file,region
    double precision :: context_margin_km

    call get_env_or_default('PARAVIEW_MESH_REGION','ulvz-window',region)
    max_cells = get_env_int_default('PARAVIEW_MESH_MAX_CELLS',200000)
    context_margin_km = get_env_double_default('PARAVIEW_MESH_CONTEXT_MARGIN_KM',-1.d0)
    if (trim(region) /= 'all' .and. trim(region) /= 'near-cmb' .and. &
        trim(region) /= 'ulvz-window') then
      print *,'Unsupported PARAVIEW_MESH_REGION=',trim(region)
      stop 2
    endif

    do iproc = 0,NPROCTOT_VAL - 1
      call make_solver_filename(disabled_dir,iproc,ref_file)
      call make_solver_filename(enabled_dir,iproc,ulvz_file)
      call read_solver_database(trim(ref_file),ref_db,tiso_present)
      call read_solver_database(trim(ulvz_file),ulvz_db,tiso_present)
      call write_rank_paraview_mesh(report_dir,iproc,ref_db,ulvz_db,rplanet_km,rcmb_km, &
        ratio_tol,trim(region),context_margin_km,rank_stats)
      mesh_stats%rank_local_nodes = mesh_stats%rank_local_nodes + rank_stats%rank_local_nodes
      mesh_stats%exported_cells = mesh_stats%exported_cells + rank_stats%exported_cells
      if (mesh_stats%exported_cells > int(max_cells,kind=8)) then
        print *,'PARAVIEW_MESH_MAX_CELLS exceeded: ',mesh_stats%exported_cells,max_cells
        stop 1
      endif
      call free_solver_database(ref_db)
      call free_solver_database(ulvz_db)
    enddo
    call write_paraview_mesh_metadata(report_dir,rplanet_km,rcmb_km,trim(region), &
      context_margin_km,max_cells,mesh_stats)
  end subroutine write_paraview_mesh_exports

  subroutine write_rank_paraview_mesh(report_dir,iproc,ref_db,ulvz_db,rplanet_km,rcmb_km, &
      ratio_tol,region,context_margin_km,rank_stats)
    character(len=*), intent(in) :: report_dir,region
    integer, intent(in) :: iproc
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol,context_margin_km
    type(paraview_mesh_stats), intent(out) :: rank_stats
    logical, allocatable :: selected(:),used_iglob(:)
    integer, allocatable :: node_id(:)
    integer :: ispec,iglob,next_node,nodes_unit,cells_unit
    character(len=512) :: nodes_file,cells_file

    rank_stats%rank_local_nodes = 0_8
    rank_stats%exported_cells = 0_8
    allocate(selected(ref_db%nspec),used_iglob(ref_db%nglob),node_id(ref_db%nglob))
    selected = .false.
    used_iglob = .false.
    node_id = 0

    do ispec = 1,ref_db%nspec
      selected(ispec) = paraview_cell_selected(ref_db,ispec,rplanet_km,rcmb_km, &
        region,context_margin_km)
      if (selected(ispec)) then
        rank_stats%exported_cells = rank_stats%exported_cells + 1_8
        call mark_cell_corner_nodes(ref_db,ispec,used_iglob)
      endif
    enddo

    next_node = 0
    do iglob = 1,ref_db%nglob
      if (used_iglob(iglob)) then
        next_node = next_node + 1
        node_id(iglob) = next_node
      endif
    enddo
    rank_stats%rank_local_nodes = int(next_node,kind=8)

    write(nodes_file,"(a,'/paraview_mesh_nodes_rank',i6.6,'.csv')") trim(report_dir),iproc
    open(newunit=nodes_unit,file=trim(nodes_file),status='replace',action='write')
    call write_paraview_nodes_header(nodes_unit)
    do iglob = 1,ref_db%nglob
      if (used_iglob(iglob)) call write_paraview_node_record(nodes_unit,iproc,node_id(iglob), &
        iglob,dble(ref_db%x(iglob)),dble(ref_db%y(iglob)),dble(ref_db%z(iglob)), &
        rplanet_km,rcmb_km)
    enddo
    close(nodes_unit)

    write(cells_file,"(a,'/paraview_mesh_cells_rank',i6.6,'.csv')") trim(report_dir),iproc
    open(newunit=cells_unit,file=trim(cells_file),status='replace',action='write')
    call write_paraview_cells_header(cells_unit)
    do ispec = 1,ref_db%nspec
      if (selected(ispec)) call write_paraview_cell_record(cells_unit,iproc,ispec, &
        ref_db,ulvz_db,node_id,rplanet_km,rcmb_km,ratio_tol)
    enddo
    close(cells_unit)

    deallocate(selected,used_iglob,node_id)
  end subroutine write_rank_paraview_mesh

  logical function paraview_cell_selected(db,ispec,rplanet_km,rcmb_km,region,context_margin_km)
    type(solver_db), intent(in) :: db
    integer, intent(in) :: ispec
    double precision, intent(in) :: rplanet_km,rcmb_km,context_margin_km
    character(len=*), intent(in) :: region
    integer :: i,j,k,iglob
    double precision :: w,height,lateral,cx,cy,cz,center_radius,center_height

    if (trim(region) == 'all') then
      paraview_cell_selected = .true.
      return
    endif

    if (trim(region) == 'near-cmb') then
      cx = 0.d0
      cy = 0.d0
      cz = 0.d0
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            iglob = db%ibool(i,j,k,ispec)
            cx = cx + dble(db%x(iglob))
            cy = cy + dble(db%y(iglob))
            cz = cz + dble(db%z(iglob))
          enddo
        enddo
      enddo
      cx = cx / dble(NGLLX * NGLLY * NGLLZ)
      cy = cy / dble(NGLLX * NGLLY * NGLLZ)
      cz = cz / dble(NGLLX * NGLLY * NGLLZ)
      center_radius = dsqrt(cx*cx + cy*cy + cz*cz) * rplanet_km
      center_height = center_radius - rcmb_km
      paraview_cell_selected = (center_height >= 0.d0 .and. center_height <= 160.d0)
      return
    endif

    paraview_cell_selected = .false.
    do k = 1,NGLLZ
      do j = 1,NGLLY
        do i = 1,NGLLX
          iglob = db%ibool(i,j,k,ispec)
          call analytical_weight(dble(db%x(iglob)),dble(db%y(iglob)),dble(db%z(iglob)), &
            rplanet_km,rcmb_km,w,height,lateral)
          if (w > 0.d0) then
            paraview_cell_selected = .true.
            return
          endif
          if (context_margin_km >= 0.d0) then
            if (height >= -context_margin_km .and. height <= THICKNESS_KM + context_margin_km .and. &
                lateral <= LATERAL_RADIUS_KM + context_margin_km) then
              paraview_cell_selected = .true.
              return
            endif
          endif
        enddo
      enddo
    enddo
  end function paraview_cell_selected

  subroutine mark_cell_corner_nodes(db,ispec,used_iglob)
    type(solver_db), intent(in) :: db
    integer, intent(in) :: ispec
    logical, intent(inout) :: used_iglob(:)
    used_iglob(db%ibool(1,1,1,ispec)) = .true.
    used_iglob(db%ibool(NGLLX,1,1,ispec)) = .true.
    used_iglob(db%ibool(NGLLX,NGLLY,1,ispec)) = .true.
    used_iglob(db%ibool(1,NGLLY,1,ispec)) = .true.
    used_iglob(db%ibool(1,1,NGLLZ,ispec)) = .true.
    used_iglob(db%ibool(NGLLX,1,NGLLZ,ispec)) = .true.
    used_iglob(db%ibool(NGLLX,NGLLY,NGLLZ,ispec)) = .true.
    used_iglob(db%ibool(1,NGLLY,NGLLZ,ispec)) = .true.
  end subroutine mark_cell_corner_nodes

  subroutine write_paraview_nodes_header(unit)
    integer, intent(in) :: unit
    write(unit,'(a)') 'rank,node_id,iglob,x_km,y_km,z_km,x_norm,y_norm,z_norm,'// &
      'radius_km,height_above_cmb_km,latitude_deg,longitude_deg'
  end subroutine write_paraview_nodes_header

  subroutine write_paraview_node_record(unit,iproc,node_id,iglob,x,y,z,rplanet_km,rcmb_km)
    integer, intent(in) :: unit,iproc,node_id,iglob
    double precision, intent(in) :: x,y,z,rplanet_km,rcmb_km
    double precision :: radius_norm,radius_km,lat_deg,lon_deg
    radius_norm = dsqrt(x*x + y*y + z*z)
    radius_km = radius_norm * rplanet_km
    if (radius_norm > 0.d0) then
      lat_deg = dasin(max(-1.d0,min(1.d0,z / radius_norm))) / DEGREES_TO_RADIANS
      lon_deg = datan2(y,x) / DEGREES_TO_RADIANS
    else
      lat_deg = 0.d0
      lon_deg = 0.d0
    endif
    write(unit,'(i0,",",i0,",",i0,10(",",es24.16))') iproc,node_id,iglob, &
      x * rplanet_km,y * rplanet_km,z * rplanet_km,x,y,z,radius_km, &
      radius_km - rcmb_km,lat_deg,lon_deg
  end subroutine write_paraview_node_record

  subroutine write_paraview_cells_header(unit)
    integer, intent(in) :: unit
    write(unit,'(a)') 'rank,cell_id,ispec,node0,node1,node2,node3,node4,node5,node6,node7,'// &
      'cell_center_radius_km,cell_center_height_above_cmb_km,'// &
      'cell_w_expected_mean,cell_w_expected_min,cell_w_expected_max,'// &
      'cell_has_outside,cell_has_taper,cell_has_core,cell_category_code,'// &
      'material_changed_fraction,'// &
      'rho_ratio_mean,rho_ratio_min,rho_ratio_max,'// &
      'vsv_ratio_mean,vsv_ratio_min,vsv_ratio_max,'// &
      'vsh_ratio_mean,vsh_ratio_min,vsh_ratio_max,'// &
      'vpv_ratio_mean,vpv_ratio_min,vpv_ratio_max,'// &
      'vph_ratio_mean,vph_ratio_min,vph_ratio_max'
  end subroutine write_paraview_cells_header

  subroutine write_paraview_cell_record(unit,iproc,ispec,ref_db,ulvz_db,node_id,rplanet_km,rcmb_km,ratio_tol)
    integer, intent(in) :: unit,iproc,ispec,node_id(:)
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    integer :: i,j,k,iglob,category,npts,has_outside,has_taper,has_core,category_code,changed_count
    integer :: corner_nodes(8)
    double precision :: w,height,lateral,ratio(5),ratio_sum(5),ratio_min(5),ratio_max(5)
    double precision :: ref_vpv,ulvz_vpv,ref_vph,ulvz_vph,ref_vsv,ulvz_vsv,ref_vsh,ulvz_vsh
    double precision :: w_sum,w_min,w_max,cx,cy,cz,center_radius,material_fraction

    corner_nodes = (/ node_id(ref_db%ibool(1,1,1,ispec)), &
      node_id(ref_db%ibool(NGLLX,1,1,ispec)), &
      node_id(ref_db%ibool(NGLLX,NGLLY,1,ispec)), &
      node_id(ref_db%ibool(1,NGLLY,1,ispec)), &
      node_id(ref_db%ibool(1,1,NGLLZ,ispec)), &
      node_id(ref_db%ibool(NGLLX,1,NGLLZ,ispec)), &
      node_id(ref_db%ibool(NGLLX,NGLLY,NGLLZ,ispec)), &
      node_id(ref_db%ibool(1,NGLLY,NGLLZ,ispec)) /)

    npts = 0
    has_outside = 0
    has_taper = 0
    has_core = 0
    changed_count = 0
    w_sum = 0.d0
    w_min = 1.d99
    w_max = -1.d99
    ratio_sum = 0.d0
    ratio_min = 1.d99
    ratio_max = -1.d99
    cx = 0.d0
    cy = 0.d0
    cz = 0.d0

    do k = 1,NGLLZ
      do j = 1,NGLLY
        do i = 1,NGLLX
          iglob = ref_db%ibool(i,j,k,ispec)
          call analytical_weight(dble(ref_db%x(iglob)),dble(ref_db%y(iglob)), &
            dble(ref_db%z(iglob)),rplanet_km,rcmb_km,w,height,lateral)
          if (height <= GEOMETRY_TOL_KM) w = 0.d0
          category = weight_category(w)
          if (category == 1) has_outside = 1
          if (category == 2) has_taper = 1
          if (category == 3) has_core = 1

          ref_vsv = dble(ref_db%muv(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
          ulvz_vsv = dble(ulvz_db%muv(i,j,k,ispec)) / dble(ulvz_db%rho(i,j,k,ispec))
          ref_vsh = dble(ref_db%muh(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
          ulvz_vsh = dble(ulvz_db%muh(i,j,k,ispec)) / dble(ulvz_db%rho(i,j,k,ispec))
          ref_vpv = (dble(ref_db%kappav(i,j,k,ispec)) + 4.d0 * dble(ref_db%muv(i,j,k,ispec)) / 3.d0) &
            / dble(ref_db%rho(i,j,k,ispec))
          ulvz_vpv = (dble(ulvz_db%kappav(i,j,k,ispec)) + 4.d0 * dble(ulvz_db%muv(i,j,k,ispec)) / 3.d0) &
            / dble(ulvz_db%rho(i,j,k,ispec))
          ref_vph = (dble(ref_db%kappah(i,j,k,ispec)) + 4.d0 * dble(ref_db%muh(i,j,k,ispec)) / 3.d0) &
            / dble(ref_db%rho(i,j,k,ispec))
          ulvz_vph = (dble(ulvz_db%kappah(i,j,k,ispec)) + 4.d0 * dble(ulvz_db%muh(i,j,k,ispec)) / 3.d0) &
            / dble(ulvz_db%rho(i,j,k,ispec))

          ratio(1) = dble(ulvz_db%rho(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
          ratio(2) = dsqrt(ulvz_vsv / ref_vsv)
          ratio(3) = dsqrt(ulvz_vsh / ref_vsh)
          ratio(4) = dsqrt(ulvz_vpv / ref_vpv)
          ratio(5) = dsqrt(ulvz_vph / ref_vph)
          if (any(dabs(ratio - 1.d0) > ratio_tol)) changed_count = changed_count + 1
          npts = npts + 1
          w_sum = w_sum + w
          w_min = min(w_min,w)
          w_max = max(w_max,w)
          ratio_sum = ratio_sum + ratio
          ratio_min = min(ratio_min,ratio)
          ratio_max = max(ratio_max,ratio)
          cx = cx + dble(ref_db%x(iglob))
          cy = cy + dble(ref_db%y(iglob))
          cz = cz + dble(ref_db%z(iglob))
        enddo
      enddo
    enddo

    cx = cx / dble(npts)
    cy = cy / dble(npts)
    cz = cz / dble(npts)
    center_radius = dsqrt(cx*cx + cy*cy + cz*cz) * rplanet_km
    material_fraction = dble(changed_count) / dble(npts)
    if (has_outside + has_taper + has_core > 1) then
      category_code = 3
    else if (has_core == 1) then
      category_code = 2
    else if (has_taper == 1) then
      category_code = 1
    else
      category_code = 0
    endif

    write(unit,'(i0,",",i0,",",i0,8(",",i0),5(",",es24.16),4(",",i0),16(",",es24.16))') &
      iproc,ispec,ispec,corner_nodes,center_radius,center_radius - rcmb_km, &
      w_sum / dble(npts),w_min,w_max,has_outside,has_taper,has_core,category_code, &
      material_fraction,ratio_sum(1) / dble(npts),ratio_min(1),ratio_max(1), &
      ratio_sum(2) / dble(npts),ratio_min(2),ratio_max(2), &
      ratio_sum(3) / dble(npts),ratio_min(3),ratio_max(3), &
      ratio_sum(4) / dble(npts),ratio_min(4),ratio_max(4), &
      ratio_sum(5) / dble(npts),ratio_min(5),ratio_max(5)
  end subroutine write_paraview_cell_record

  subroutine write_paraview_mesh_metadata(report_dir,rplanet_km,rcmb_km,region,context_margin_km, &
      max_cells,mesh_stats)
    character(len=*), intent(in) :: report_dir,region
    double precision, intent(in) :: rplanet_km,rcmb_km,context_margin_km
    integer, intent(in) :: max_cells
    type(paraview_mesh_stats), intent(in) :: mesh_stats
    integer :: unit

    open(newunit=unit,file=trim(report_dir)//'/paraview_mesh_metadata.json',status='replace',action='write')
    write(unit,'(a)') '{'
    write(unit,'(a)') '  "schema_version": "ulvz_paraview_mesh.v1",'
    write(unit,'(a)') '  "producer": "inspect_s40rts_ulvz_database.f90",'
    write(unit,'(a)') '  "coordinate_units": "km",'
    write(unit,'(a,es16.8,a)') '  "r_planet_km": ',rplanet_km,','
    write(unit,'(a,es16.8,a)') '  "rcmb_km": ',rcmb_km,','
    write(unit,'(a)') '  "cell_type": "VTK_HEXAHEDRON",'
    write(unit,'(a)') '  "geometry_note": "8-corner linearized hexahedra; high-order curved geometry is not preserved",'
    write(unit,'(a)') '  "corner_ordering": ['
    write(unit,'(a)') '    "ibool(1,1,1)", "ibool(NGLLX,1,1)", "ibool(NGLLX,NGLLY,1)",'
    write(unit,'(a)') '    "ibool(1,NGLLY,1)", "ibool(1,1,NGLLZ)", "ibool(NGLLX,1,NGLLZ)",'
    write(unit,'(a)') '    "ibool(NGLLX,NGLLY,NGLLZ)", "ibool(1,NGLLY,NGLLZ)"'
    write(unit,'(a)') '  ],'
    write(unit,'(a,a,a)') '  "region": "',trim(region),'",'
    write(unit,'(a,i0,a)') '  "max_cells": ',max_cells,','
    if (context_margin_km >= 0.d0) then
      write(unit,'(a,es16.8,a)') '  "context_margin_km": ',context_margin_km,','
    else
      write(unit,'(a)') '  "context_margin_km": null,'
    endif
    write(unit,'(a)') '  "selection_rule": "ulvz-window inspects all GLL points and selects cells with any w_expected > 0",'
    write(unit,'(a)') '  "node_merge_policy": "rank-local",'
    write(unit,'(a)') '  "weld_tolerance": null,'
    write(unit,'(a,i0,a)') '  "number_of_rank_local_nodes": ',mesh_stats%rank_local_nodes,','
    write(unit,'(a)') '  "number_of_welded_nodes": null,'
    write(unit,'(a,i0)') '  "number_of_exported_cells": ',mesh_stats%exported_cells
    write(unit,'(a)') '}'
    close(unit)
  end subroutine write_paraview_mesh_metadata

  integer function get_env_int_default(name,default_value)
    character(len=*), intent(in) :: name
    integer, intent(in) :: default_value
    character(len=64) :: value
    integer :: length,status,ier
    get_env_int_default = default_value
    call get_environment_variable(name,value,length,status)
    if (status == 0 .and. length > 0) then
      read(value(1:length),*,iostat=ier) get_env_int_default
      if (ier /= 0) then
        print *,'Invalid integer environment value for ',trim(name),': ',trim(value(1:length))
        stop 2
      endif
    endif
  end function get_env_int_default

  double precision function get_env_double_default(name,default_value)
    character(len=*), intent(in) :: name
    double precision, intent(in) :: default_value
    character(len=64) :: value
    integer :: length,status,ier
    get_env_double_default = default_value
    call get_environment_variable(name,value,length,status)
    if (status == 0 .and. length > 0) then
      read(value(1:length),*,iostat=ier) get_env_double_default
      if (ier /= 0) then
        print *,'Invalid real environment value for ',trim(name),': ',trim(value(1:length))
        stop 2
      endif
    endif
  end function get_env_double_default

  subroutine write_visualization_exports(disabled_dir,enabled_dir,report_dir,rplanet_km,rcmb_km, &
      ratio_tol,tiso_present,stats)
    character(len=*), intent(in) :: disabled_dir,enabled_dir,report_dir
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    logical, intent(in) :: tiso_present
    type(validation_stats), intent(in) :: stats
    type(viz_export_stats) :: export_stats
    type(solver_db) :: ref_db,ulvz_db
    integer :: iproc,unit
    character(len=512) :: ref_file,ulvz_file,csv_file

    export_stats%full_source_count = sum(stats%category_count)
    if (stats%category_count(1) > 50000_8) then
      export_stats%outside_stride = (stats%category_count(1) + 50000_8 - 1_8) / 50000_8
    else
      export_stats%outside_stride = 1_8
    endif

    csv_file = trim(report_dir)//'/mesh_gll_points.csv'
    open(newunit=unit,file=trim(csv_file),status='replace',action='write')
    call write_viz_csv_header(unit)
    do iproc = 0,NPROCTOT_VAL - 1
      call make_solver_filename(disabled_dir,iproc,ref_file)
      call make_solver_filename(enabled_dir,iproc,ulvz_file)
      call read_solver_database(trim(ref_file),ref_db,tiso_present)
      call read_solver_database(trim(ulvz_file),ulvz_db,tiso_present)
      call write_rank_viz_points(unit,iproc,ref_db,ulvz_db,rplanet_km,rcmb_km,ratio_tol, &
        export_stats)
      call free_solver_database(ref_db)
      call free_solver_database(ulvz_db)
    enddo
    close(unit)
    call write_viz_metadata(report_dir,rplanet_km,rcmb_km,ratio_tol,export_stats)
  end subroutine write_visualization_exports

  subroutine write_viz_csv_header(unit)
    integer, intent(in) :: unit
    write(unit,'(a)') 'record_id,record_kind,rank,ispec,i,j,k,iglob,is_shared_duplicate,'// &
      'x_norm,y_norm,z_norm,radius_norm,radius_km,depth_km,height_above_cmb_km,'// &
      'latitude_deg,longitude_deg,point_azimuth_deg,angular_distance_deg,lateral_distance_km,'// &
      'section_azimuth_deg,section_distance_km,cross_section_offset_km,w_expected,category,'// &
      'rho_expected,rho_ratio,rho_residual,vsv_expected,vsv_ratio,vsv_residual,'// &
      'vsh_expected,vsh_ratio,vsh_residual,vpv_expected,vpv_ratio,vpv_residual,'// &
      'vph_expected,vph_ratio,vph_residual,cmb_boundary_noncomparable,material_changed,is_tiso'
  end subroutine write_viz_csv_header

  subroutine write_rank_viz_points(unit,iproc,ref_db,ulvz_db,rplanet_km,rcmb_km,ratio_tol, &
      export_stats)
    integer, intent(in) :: unit,iproc
    type(solver_db), intent(in) :: ref_db,ulvz_db
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    type(viz_export_stats), intent(inout) :: export_stats
    logical, allocatable :: seen_iglob(:)
    integer :: ispec,i,j,k,iglob,category
    integer(kind=8) :: outside_seen
    double precision :: w,height,lateral,expected(5),ratio(5),resid(5)
    double precision :: ref_vpv,ulvz_vpv,ref_vph,ulvz_vph,ref_vsv,ulvz_vsv,ref_vsh,ulvz_vsh
    double precision :: radius_norm,radius_km,depth_km,lat_deg,lon_deg
    double precision :: point_azimuth_deg,angular_distance_deg,section_distance_km,cross_offset_km
    logical :: cmb_boundary,material_changed,is_shared_duplicate,write_row

    outside_seen = 0_8
    allocate(seen_iglob(ref_db%nglob))
    seen_iglob = .false.

    do ispec = 1,ref_db%nspec
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            iglob = ref_db%ibool(i,j,k,ispec)
            call analytical_weight(dble(ref_db%x(iglob)),dble(ref_db%y(iglob)), &
              dble(ref_db%z(iglob)),rplanet_km,rcmb_km,w,height,lateral)
            cmb_boundary = (height <= GEOMETRY_TOL_KM)
            if (cmb_boundary) w = 0.d0
            category = weight_category(w)

            if (category == 1) then
              outside_seen = outside_seen + 1_8
              write_row = (mod(outside_seen - 1_8,export_stats%outside_stride) == 0_8)
            else
              write_row = .true.
            endif
            if (.not. write_row) cycle

            ref_vsv = dble(ref_db%muv(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vsv = dble(ulvz_db%muv(i,j,k,ispec)) / dble(ulvz_db%rho(i,j,k,ispec))
            ref_vsh = dble(ref_db%muh(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vsh = dble(ulvz_db%muh(i,j,k,ispec)) / dble(ulvz_db%rho(i,j,k,ispec))
            ref_vpv = (dble(ref_db%kappav(i,j,k,ispec)) + 4.d0 * dble(ref_db%muv(i,j,k,ispec)) / 3.d0) &
              / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vpv = (dble(ulvz_db%kappav(i,j,k,ispec)) + 4.d0 * dble(ulvz_db%muv(i,j,k,ispec)) / 3.d0) &
              / dble(ulvz_db%rho(i,j,k,ispec))
            ref_vph = (dble(ref_db%kappah(i,j,k,ispec)) + 4.d0 * dble(ref_db%muh(i,j,k,ispec)) / 3.d0) &
              / dble(ref_db%rho(i,j,k,ispec))
            ulvz_vph = (dble(ulvz_db%kappah(i,j,k,ispec)) + 4.d0 * dble(ulvz_db%muh(i,j,k,ispec)) / 3.d0) &
              / dble(ulvz_db%rho(i,j,k,ispec))

            ratio(1) = dble(ulvz_db%rho(i,j,k,ispec)) / dble(ref_db%rho(i,j,k,ispec))
            ratio(2) = dsqrt(ulvz_vsv / ref_vsv)
            ratio(3) = dsqrt(ulvz_vsh / ref_vsh)
            ratio(4) = dsqrt(ulvz_vpv / ref_vpv)
            ratio(5) = dsqrt(ulvz_vph / ref_vph)
            expected = (/1.d0 + w * DRHO,1.d0 + w * DVS,1.d0 + w * DVS, &
              1.d0 + w * DVP,1.d0 + w * DVP/)
            resid = dabs(ratio - expected)

            call point_coordinates(dble(ref_db%x(iglob)),dble(ref_db%y(iglob)),dble(ref_db%z(iglob)), &
              rplanet_km,rcmb_km,radius_norm,radius_km,depth_km,lat_deg,lon_deg, &
              point_azimuth_deg,angular_distance_deg,section_distance_km,cross_offset_km)
            material_changed = any(dabs(ratio - 1.d0) > ratio_tol)
            is_shared_duplicate = seen_iglob(iglob)
            seen_iglob(iglob) = .true.
            export_stats%exported_count = export_stats%exported_count + 1_8
            export_stats%retained_count(category) = export_stats%retained_count(category) + 1_8
            call write_viz_csv_record(unit,export_stats%exported_count,iproc,ispec,i,j,k,iglob, &
              is_shared_duplicate,dble(ref_db%x(iglob)),dble(ref_db%y(iglob)),dble(ref_db%z(iglob)), &
              radius_norm,radius_km,depth_km,height,lat_deg,lon_deg,point_azimuth_deg, &
              angular_distance_deg,lateral,section_distance_km,cross_offset_km,w,category, &
              expected,ratio,resid,cmb_boundary,material_changed,ref_db%ispec_is_tiso(ispec))
          enddo
        enddo
      enddo
    enddo
    deallocate(seen_iglob)
  end subroutine write_rank_viz_points

  subroutine point_coordinates(x,y,z,rplanet_km,rcmb_km,radius_norm,radius_km,depth_km, &
      lat_deg,lon_deg,point_azimuth_deg,angular_distance_deg,section_distance_km,cross_offset_km)
    double precision, intent(in) :: x,y,z,rplanet_km,rcmb_km
    double precision, intent(out) :: radius_norm,radius_km,depth_km,lat_deg,lon_deg
    double precision, intent(out) :: point_azimuth_deg,angular_distance_deg,section_distance_km,cross_offset_km
    double precision :: lat,lon,lat0,lon0,dlon,cosang,ang,lateral,north,east,bearing_x,bearing_y,az

    radius_norm = dsqrt(x*x + y*y + z*z)
    radius_km = radius_norm * rplanet_km
    depth_km = rplanet_km - radius_km
    if (radius_norm <= 0.d0) then
      lat = 0.d0
      lon = 0.d0
    else
      lat = dasin(max(-1.d0,min(1.d0,z / radius_norm)))
      lon = datan2(y,x)
    endif
    lat_deg = lat / DEGREES_TO_RADIANS
    lon_deg = lon / DEGREES_TO_RADIANS
    lat0 = CENTER_LAT_DEG * DEGREES_TO_RADIANS
    lon0 = CENTER_LON_DEG * DEGREES_TO_RADIANS
    dlon = lon - lon0
    cosang = dsin(lat) * dsin(lat0) + dcos(lat) * dcos(lat0) * dcos(dlon)
    cosang = max(-1.d0,min(1.d0,cosang))
    ang = dacos(cosang)
    angular_distance_deg = ang / DEGREES_TO_RADIANS
    lateral = rcmb_km * ang
    bearing_y = dsin(dlon) * dcos(lat)
    bearing_x = dcos(lat0) * dsin(lat) - dsin(lat0) * dcos(lat) * dcos(dlon)
    az = datan2(bearing_y,bearing_x)
    if (az < 0.d0) az = az + 2.d0 * PI
    point_azimuth_deg = az / DEGREES_TO_RADIANS
    north = lateral * dcos(az)
    east = lateral * dsin(az)
    section_distance_km = north
    cross_offset_km = dabs(east)
  end subroutine point_coordinates

  subroutine write_viz_csv_record(unit,record_id,iproc,ispec,i,j,k,iglob,is_shared_duplicate, &
      x,y,z,radius_norm,radius_km,depth_km,height,lat_deg,lon_deg,point_azimuth_deg, &
      angular_distance_deg,lateral,section_distance_km,cross_offset_km,w,category,expected,ratio,resid, &
      cmb_boundary,material_changed,is_tiso)
    integer, intent(in) :: unit,iproc,ispec,i,j,k,iglob,category
    integer(kind=8), intent(in) :: record_id
    logical, intent(in) :: is_shared_duplicate,cmb_boundary,material_changed,is_tiso
    double precision, intent(in) :: x,y,z,radius_norm,radius_km,depth_km,height,lat_deg,lon_deg
    double precision, intent(in) :: point_azimuth_deg,angular_distance_deg,lateral,section_distance_km
    double precision, intent(in) :: cross_offset_km,w,expected(5),ratio(5),resid(5)

    write(unit,'(i0,",element_gll,",i0,",",i0,",",i0,",",i0,",",i0,",",i0,",",a, &
      & ",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16, &
      & ",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16, &
      & ",",es24.16,",",es24.16,",",a, &
      & ",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16, &
      & ",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16,",",es24.16, &
      & ",",es24.16,",",es24.16,",",es24.16,",",a,",",a,",",a)') &
      record_id,iproc,ispec,i,j,k,iglob,trim(logical_string(is_shared_duplicate)), &
      x,y,z,radius_norm,radius_km,depth_km,height,lat_deg,lon_deg,point_azimuth_deg, &
      angular_distance_deg,lateral,0.d0,section_distance_km,cross_offset_km,w,trim(category_name(category)), &
      expected(1),ratio(1),resid(1),expected(2),ratio(2),resid(2), &
      expected(3),ratio(3),resid(3),expected(4),ratio(4),resid(4), &
      expected(5),ratio(5),resid(5),trim(logical_string(cmb_boundary)), &
      trim(logical_string(material_changed)),trim(logical_string(is_tiso))
  end subroutine write_viz_csv_record

  character(len=7) function category_name(category)
    integer, intent(in) :: category
    if (category == 1) then
      category_name = 'outside'
    else if (category == 2) then
      category_name = 'taper'
    else
      category_name = 'core'
    endif
  end function category_name

  character(len=5) function logical_string(value)
    logical, intent(in) :: value
    if (value) then
      logical_string = 'true'
    else
      logical_string = 'false'
    endif
  end function logical_string

  subroutine write_viz_metadata(report_dir,rplanet_km,rcmb_km,ratio_tol,export_stats)
    character(len=*), intent(in) :: report_dir
    double precision, intent(in) :: rplanet_km,rcmb_km,ratio_tol
    type(viz_export_stats), intent(in) :: export_stats
    integer :: unit
    character(len=512) :: mpi_command,specfem_version,git_commit,created_utc,omp_num_threads

    call get_env_or_default('ULVZ_MESH_VIZ_MPI_COMMAND','unknown',mpi_command)
    call get_env_or_default('ULVZ_MESH_VIZ_SPECFEM_VERSION','unknown',specfem_version)
    call get_env_or_default('ULVZ_MESH_VIZ_GIT_COMMIT','unknown',git_commit)
    call get_env_or_default('ULVZ_MESH_VIZ_CREATED_UTC','unknown',created_utc)
    call get_env_or_default('ULVZ_MESH_VIZ_OMP_NUM_THREADS','1',omp_num_threads)

    open(newunit=unit,file=trim(report_dir)//'/mesh_visualization_metadata.json',status='replace',action='write')
    write(unit,'(a)') '{'
    write(unit,'(a)') '  "schema_version": "ulvz_mesh_viz.v1",'
    write(unit,'(a)') '  "producer": "inspect_s40rts_ulvz_database.f90",'
    write(unit,'(a,a,a)') '  "created_utc": "',trim(created_utc),'",'
    write(unit,'(a,a,a)') '  "specfem_version": "',trim(specfem_version),'",'
    write(unit,'(a,a,a)') '  "git_commit": "',trim(git_commit),'",'
    write(unit,'(a,a,a)') '  "mpi_command": "',trim(mpi_command),'",'
    write(unit,'(a,i0,a)') '  "nproc": ',NPROCTOT_VAL,','
    write(unit,'(a,a,a)') '  "omp_num_threads": ',trim(omp_num_threads),','
    write(unit,'(a,es16.8,a)') '  "r_planet_km": ',rplanet_km,','
    write(unit,'(a,es16.8,a)') '  "rcmb_km": ',rcmb_km,','
    write(unit,'(a)') '  "coordinate_convention": {'
    write(unit,'(a)') '    "cartesian": "SPECFEM normalized x/y/z",'
    write(unit,'(a)') '    "latitude": "geographic degrees",'
    write(unit,'(a)') '    "longitude": "degrees east from atan2, [-180, 180]"'
    write(unit,'(a)') '  },'
    write(unit,'(a)') '  "ulvz": {'
    write(unit,'(a,es16.8,a)') '    "center_latitude_deg": ',CENTER_LAT_DEG,','
    write(unit,'(a,es16.8,a)') '    "center_longitude_deg": ',CENTER_LON_DEG,','
    write(unit,'(a,es16.8,a)') '    "thickness_km": ',THICKNESS_KM,','
    write(unit,'(a,es16.8,a)') '    "lateral_radius_km": ',LATERAL_RADIUS_KM,','
    write(unit,'(a,es16.8,a)') '    "lateral_taper_km": ',LATERAL_TAPER_KM,','
    write(unit,'(a,es16.8,a)') '    "top_taper_km": ',TOP_TAPER_KM,','
    write(unit,'(a,es16.8,a)') '    "dVp": ',DVP,','
    write(unit,'(a,es16.8,a)') '    "dVs": ',DVS,','
    write(unit,'(a,es16.8)') '    "dRho": ',DRHO
    write(unit,'(a)') '  },'
    write(unit,'(a)') '  "fields_present": {"rho": true, "vsv": true, "vsh": true, "vpv": true, "vph": true},'
    write(unit,'(a)') '  "sampling_rule": {'
    write(unit,'(a,i0,a)') '    "full_source_count": ',export_stats%full_source_count,','
    write(unit,'(a,i0,a)') '    "exported_count": ',export_stats%exported_count,','
    write(unit,'(a,i0,a)') '    "outside_stride": ',export_stats%outside_stride,','
    write(unit,'(a,i0,a,i0,a,i0,a)') '    "retained_counts_by_category": {"outside": ', &
      export_stats%retained_count(1),', "taper": ',export_stats%retained_count(2), &
      ', "core": ',export_stats%retained_count(3),'}'
    write(unit,'(a)') '  },'
    write(unit,'(a)') '  "duplicate_policy": {"unique_plotting_key": ["rank", "iglob"]},'
    write(unit,'(a)',advance='no') '  "fixture_disclaimer": "S40RTS ULVZ mesher validation fixture; '
    write(unit,'(a)') 'NEX_XI=32, NEX_ETA=32, NPROC=2; Not a production waveform-resolution mesh",'
    write(unit,'(a)') '  "tolerances": {'
    write(unit,'(a)') '    "coordinate_abs": 1.0e-9,'
    write(unit,'(a)') '    "w_expected_abs": 1.0e-9,'
    write(unit,'(a,es16.8,a)') '    "ratio_abs": ',ratio_tol,','
    write(unit,'(a,es16.8)') '    "residual_abs": ',ratio_tol
    write(unit,'(a)') '  },'
    write(unit,'(a)') '  "default_section_azimuth_deg": 0.0'
    write(unit,'(a)') '}'
    close(unit)
  end subroutine write_viz_metadata

  subroutine get_env_or_default(name,default,value)
    character(len=*), intent(in) :: name,default
    character(len=*), intent(out) :: value
    integer :: length,status
    value = default
    call get_environment_variable(name,value,length,status)
    if (status /= 0 .or. length == 0) value = default
  end subroutine get_env_or_default

end program inspect_s40rts_ulvz_database
