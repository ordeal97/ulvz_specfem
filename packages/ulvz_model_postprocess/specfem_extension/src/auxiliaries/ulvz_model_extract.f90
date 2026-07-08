!=====================================================================
!
!  ULVZ model post-processing database extractor.
!
!  This auxiliary is intentionally separate from the forward solver.  It
!  provides a SPECFEM-compiled boundary for inspecting and extracting solver
!  database layouts before Python post-processing reads portable products.
!
!=====================================================================

program ulvz_model_extract

  use constants, only: CUSTOM_REAL,SIZE_REAL,SIZE_DOUBLE,NGLLX,NGLLY,NGLLZ,MAX_STRING_LEN, &
    PI,GRAV,EARTH_R,EARTH_RHOAV
  use iso_fortran_env, only: int8,int16,int32,int64,real64

  implicit none

  integer, parameter :: MAX_FILES = 100000
  integer, parameter :: RECORD_MARKER_BYTES = 4
  character(len=MAX_STRING_LEN) :: mode,database_dir,out_dir,label,extract_mode,arg
  integer :: memory_limit_mb,ier

  call get_command_argument(1,mode)
  call get_command_argument(2,database_dir)
  call get_command_argument(3,out_dir)

  if (len_trim(mode) == 0 .or. trim(mode) == '--help') call usage()

  if (trim(mode) == '--inspect') then
    if (len_trim(database_dir) == 0 .or. len_trim(out_dir) == 0) call usage()
    call inspect_database_directory(trim(database_dir),trim(out_dir))
  else if (trim(mode) == '--extract-reg1') then
    call get_command_argument(4,label)
    call get_command_argument(5,extract_mode)
    call get_command_argument(6,arg)
    if (len_trim(database_dir) == 0 .or. len_trim(out_dir) == 0 .or. len_trim(label) == 0 .or. &
        len_trim(extract_mode) == 0 .or. len_trim(arg) == 0) call usage()
    read(arg,*,iostat=ier) memory_limit_mb
    if (ier /= 0 .or. memory_limit_mb <= 0) then
      print *,'Unsupported memory limit: ',trim(arg)
      stop 1
    endif
    call extract_reg1_database(trim(database_dir),trim(out_dir),trim(label),trim(extract_mode),memory_limit_mb)
  else
    print *,'Unsupported mode: ',trim(mode)
    call usage()
  endif

contains

  subroutine usage()
    print *,'Usage: xulvz_model_extract --inspect DATABASES_MPI OUT_DIR'
    print *,'   or: xulvz_model_extract --extract-reg1 DATABASES_MPI OUT_DIR LABEL EXTRACT_MODE MEMORY_LIMIT_MB'
    print *,''
    print *,'This v1 utility supports local sequential proc*_reg1_solver_data.bin extraction'
    print *,'for isotropic or TISO crust/mantle databases compatible with this SPECFEM build.'
    stop 2
  end subroutine usage

  subroutine inspect_database_directory(db_dir,output_dir)
    character(len=*), intent(in) :: db_dir,output_dir
    integer :: unit,ier,iproc,iregion,count
    integer :: nspec,nglob
    character(len=MAX_STRING_LEN) :: filename,manifest
    logical :: exists

    call make_output_directory(output_dir)
    manifest = trim(output_dir)//'/extractor_layout_manifest.json'
    open(newunit=unit,file=trim(manifest),status='replace',action='write',iostat=ier)
    if (ier /= 0) then
      print *,'Error opening manifest: ',trim(manifest)
      stop 1
    endif

    write(unit,'(a)') '{'
    write(unit,'(a)') '  "schema_version": "ulvz_model_postprocess.extractor_layout.v1",'
    write(unit,'(a)') '  "producer": "xulvz_model_extract",'
    write(unit,'(a,a,a)') '  "database_dir": "',trim(json_escape(db_dir)),'",'
    write(unit,'(a,i0,a)') '  "custom_real_bytes": ',CUSTOM_REAL,','
    write(unit,'(a,a,a)') '  "custom_real_representation": "',trim(custom_real_name()),'",'
    write(unit,'(a,i0,a,i0,a,i0,a)') '  "gll_dimensions": {"x": ',NGLLX,', "y": ',NGLLY,', "z": ',NGLLZ,'},'
    write(unit,'(a)') '  "record_layout_signature": "local-sequential-solver_data-v1-prefix",'
    write(unit,'(a)') '  "layout_policy": "inspect nspec/nglob before any model-array reads",'
    write(unit,'(a)') '  "files": ['

    count = 0
    do iproc = 0,MAX_FILES - 1
      do iregion = 1,3
        call make_solver_filename(db_dir,iproc,iregion,filename)
        inquire(file=trim(filename),exist=exists)
        if (.not. exists) cycle
        call read_solver_dimensions(trim(filename),nspec,nglob)
        if (count > 0) write(unit,'(a)') ','
        write(unit,'(a)',advance='no') '    {'
        write(unit,'(a,i0,a)',advance='no') '"rank": ',iproc,', '
        write(unit,'(a,i0,a)',advance='no') '"region": ',iregion,', '
        write(unit,'(a,a,a)',advance='no') '"path": "',trim(json_escape(filename)),'", '
        write(unit,'(a,i0,a)',advance='no') '"nspec": ',nspec,', '
        write(unit,'(a,i0,a)',advance='no') '"nglob": ',nglob,', '
        write(unit,'(a)',advance='no') '"observed_prefix_records": ["nspec", "nglob"], '
        write(unit,'(a)',advance='no') '"expected_prefix_record_types": ["integer", "integer"]'
        write(unit,'(a)',advance='no') '}'
        count = count + 1
      enddo
      if (iproc > 0 .and. count == 0) exit
      if (iproc > 0 .and. no_more_rank_files(db_dir,iproc + 1)) exit
    enddo

    write(unit,'(a)') ''
    write(unit,'(a)') '  ],'
    write(unit,'(a,i0)') '  "file_count": ',count
    write(unit,'(a)') '}'
    close(unit)

    if (count == 0) then
      print *,'No proc*_reg*_solver_data.bin files found in ',trim(db_dir)
      stop 1
    endif
    print *,'Wrote ',trim(manifest)
  end subroutine inspect_database_directory

  subroutine extract_reg1_database(db_dir,output_dir,model_label,mode_name,memory_limit_mb)
    character(len=*), intent(in) :: db_dir,output_dir,model_label,mode_name
    integer, intent(in) :: memory_limit_mb
    integer :: iproc,rank_count,unit,ier
    integer, allocatable :: ranks(:),nspecs(:),nglobs(:)
    integer(int64), allocatable :: estimated_peak_bytes(:),source_payload_bytes(:)
    integer(int64), allocatable :: geometry_topology_bytes(:),physical_field_bytes(:)
    integer(int64), allocatable :: output_buffer_bytes(:),safety_margin_bytes(:)
    logical, allocatable :: tiso_flags(:)
    character(len=MAX_STRING_LEN) :: filename,manifest
    logical :: exists,first

    if (trim(mode_name) /= 'selected' .and. trim(mode_name) /= 'full') then
      print *,'Unsupported extract mode for physical extraction: ',trim(mode_name)
      stop 1
    endif
    if (CUSTOM_REAL /= SIZE_REAL .and. CUSTOM_REAL /= SIZE_DOUBLE) then
      print *,'Unsupported CUSTOM_REAL size=',CUSTOM_REAL
      stop 1
    endif
    call reject_explicit_full_anisotropy(db_dir)

    allocate(ranks(MAX_FILES),nspecs(MAX_FILES),nglobs(MAX_FILES),tiso_flags(MAX_FILES))
    allocate(estimated_peak_bytes(MAX_FILES),source_payload_bytes(MAX_FILES),geometry_topology_bytes(MAX_FILES))
    allocate(physical_field_bytes(MAX_FILES),output_buffer_bytes(MAX_FILES),safety_margin_bytes(MAX_FILES))
    rank_count = 0
    do iproc = 0,MAX_FILES - 1
      call make_solver_filename(db_dir,iproc,1,filename)
      inquire(file=trim(filename),exist=exists)
      if (.not. exists) then
        if (iproc > 0) exit
        cycle
      endif
      ranks(rank_count + 1) = iproc
      rank_count = rank_count + 1
    enddo

    if (rank_count == 0) then
      print *,'Unsupported DATABASES_MPI layout: no proc*_reg1_solver_data.bin files found'
      stop 1
    endif

    call make_output_directory(output_dir)
    call make_output_directory(trim(output_dir)//'/ranks')

    do iproc = 1,rank_count
      call make_solver_filename(db_dir,ranks(iproc),1,filename)
      call extract_one_rank(trim(filename),trim(output_dir),ranks(iproc),memory_limit_mb,nspecs(iproc),nglobs(iproc), &
        tiso_flags(iproc),estimated_peak_bytes(iproc),source_payload_bytes(iproc), &
        geometry_topology_bytes(iproc),physical_field_bytes(iproc),output_buffer_bytes(iproc),safety_margin_bytes(iproc))
    enddo

    manifest = trim(output_dir)//'/model_manifest.json'
    open(newunit=unit,file=trim(manifest),status='replace',action='write',iostat=ier)
    if (ier /= 0) then
      print *,'Error opening model manifest: ',trim(manifest)
      stop 1
    endif

    write(unit,'(a)') '{'
    write(unit,'(a)') '  "schema_version": "ulvz_model_postprocess.v1",'
    write(unit,'(a,a,a)') '  "model_label": "',trim(json_escape(model_label)),'",'
    write(unit,'(a,a,a)') '  "extraction_mode": "',trim(json_escape(mode_name)),'",'
    write(unit,'(a)') '  "roi": {"kind": "none"},'
    write(unit,'(a)') '  "sampling_rule": {"kind": "none"},'
    write(unit,'(a)') '  "selection_fingerprint": "reg1-all-ranks-no-sampling-v1",'
    write(unit,'(a)') '  "coordinate_units": {"x_km": "km", "y_km": "km", "z_km": "km"},'
    write(unit,'(a)',advance='no') '  "normalized_coordinate_units": {"x_norm": "dimensionless", '
    write(unit,'(a)') '"y_norm": "dimensionless", "z_norm": "dimensionless"},'
    call write_field_units(unit,any(tiso_flags(1:rank_count)))
    call write_field_derivations(unit,any(tiso_flags(1:rank_count)))
    call write_scaling_convention(unit,'  ')
    write(unit,'(a)') '  "rank_store": {"layout": "rank-local-directory-npy-v1", "ranks": ['
    do iproc = 1,rank_count
      if (iproc > 1) write(unit,'(a)') ','
      call write_rank_manifest_entry(unit,ranks(iproc),nspecs(iproc),nglobs(iproc),tiso_flags(iproc),.false.)
    enddo
    write(unit,'(a)') ''
    write(unit,'(a)') '  ]},'
    write(unit,'(a,a,a)') '  "compatibility_fingerprint": "',trim(compatibility_fingerprint(rank_count,nspecs,nglobs, &
      tiso_flags,mode_name)),'",'
    write(unit,'(a)') '  "compatibility_fingerprint_contents": {'
    write(unit,'(a)') '    "schema_version": "ulvz_model_postprocess.v1",'
    write(unit,'(a,a,a)') '    "extraction_mode": "',trim(json_escape(mode_name)),'",'
    write(unit,'(a)') '    "roi": {"kind": "none"},'
    write(unit,'(a)') '    "sampling_rule": {"kind": "none"},'
    write(unit,'(a)') '    "selection_fingerprint": "reg1-all-ranks-no-sampling-v1",'
    write(unit,'(a)') '    "rank_inventory": ['
    do iproc = 1,rank_count
      if (iproc > 1) write(unit,'(a)') ','
      write(unit,'(a)',advance='no') '      {'
      write(unit,'(a,i0,a)',advance='no') '"rank": ',ranks(iproc),', '
      write(unit,'(a)',advance='no') '"region": 1, '
      write(unit,'(a,i0,a)',advance='no') '"nspec": ',nspecs(iproc),', '
      write(unit,'(a,i0,a)',advance='no') '"nglob": ',nglobs(iproc)
      write(unit,'(a)',advance='no') '}'
    enddo
    write(unit,'(a)') ''
    write(unit,'(a)') '    ],'
    call write_field_units_nested(unit,any(tiso_flags(1:rank_count)))
    write(unit,'(a)') '    "coordinate_units": {"x_km": "km", "y_km": "km", "z_km": "km"},'
    call write_scaling_convention(unit,'    ')
    write(unit,'(a,a,a)') '    "topology_fingerprint": "', &
      trim(global_topology_fingerprint(rank_count,ranks,nspecs,nglobs,tiso_flags)),'",'
    write(unit,'(a,a,a)') '    "geometry_fingerprint": "', &
      trim(global_geometry_fingerprint(rank_count,ranks,nspecs,nglobs,tiso_flags)),'"'
    write(unit,'(a)') '  },'
    write(unit,'(a)') '  "provenance": {'
    write(unit,'(a)') '    "producer": "xulvz_model_extract",'
    write(unit,'(a,a,a)') '    "database_dir": "',trim(json_escape(db_dir)),'",'
    write(unit,'(a)') '    "source_database_paths": ['
    first = .true.
    do iproc = 1,rank_count
      call make_solver_filename(db_dir,ranks(iproc),1,filename)
      if (.not. first) write(unit,'(a)') ','
      write(unit,'(a,a,a)',advance='no') '      "',trim(json_escape(filename)),'"'
      first = .false.
    enddo
    write(unit,'(a)') ''
    write(unit,'(a)') '    ],'
    write(unit,'(a)') '    "extractor_build": {'
    write(unit,'(a)') '      "name": "xulvz_model_extract",'
    write(unit,'(a)') '      "record_layout_signature": "local-sequential-reg1-solver_data-v1",'
    write(unit,'(a,i0,a)') '      "custom_real_bytes": ',CUSTOM_REAL,','
    write(unit,'(a,a,a)') '      "custom_real_representation": "',trim(custom_real_name()),'",'
    write(unit,'(a,i0,a,i0,a,i0)') '      "gll_dimensions": [',NGLLX,', ',NGLLY,', ',NGLLZ,']'
    write(unit,'(a)') '    },'
    write(unit,'(a)') '    "scaling": {'
    write(unit,'(a,es24.16,a)') '      "R_PLANET_m": ',EARTH_R,','
    write(unit,'(a,es24.16,a)') '      "RHOAV_kg_m-3": ',EARTH_RHOAV,','
    write(unit,'(a,es24.16,a)') '      "density_scale_to_kg_m-3": ',EARTH_RHOAV,','
    write(unit,'(a,es24.16)') '      "velocity_scale_to_m_s-1": ',velocity_scale()
    write(unit,'(a)') '    },'
    write(unit,'(a)') '    "limits": {'
    write(unit,'(a,i0)') '      "memory_limit_mb": ',memory_limit_mb
    write(unit,'(a)') '    },'
    write(unit,'(a)') '    "memory_estimates": ['
    do iproc = 1,rank_count
      if (iproc > 1) write(unit,'(a)') ','
      call write_memory_estimate_entry(unit,ranks(iproc),memory_limit_mb,estimated_peak_bytes(iproc), &
        source_payload_bytes(iproc),geometry_topology_bytes(iproc),physical_field_bytes(iproc), &
        output_buffer_bytes(iproc),safety_margin_bytes(iproc),.false.)
    enddo
    write(unit,'(a)') ''
    write(unit,'(a)') '    ]'
    write(unit,'(a)') '  }'
    write(unit,'(a)') '}'
    close(unit)
    print *,'Wrote ',trim(manifest)
  end subroutine extract_reg1_database

  subroutine extract_one_rank(filename,output_dir,rank,memory_limit_mb,nspec,nglob,is_tiso, &
    estimated_peak_bytes,source_payload_bytes,geometry_topology_bytes,physical_field_bytes, &
    output_buffer_bytes,safety_margin_bytes)
    character(len=*), intent(in) :: filename,output_dir
    integer, intent(in) :: rank,memory_limit_mb
    integer, intent(out) :: nspec,nglob
    logical, intent(out) :: is_tiso
    integer(int64), intent(out) :: estimated_peak_bytes,source_payload_bytes,geometry_topology_bytes
    integer(int64), intent(out) :: physical_field_bytes,output_buffer_bytes,safety_margin_bytes
    integer :: unit,ier,ispec,i,j,k
    integer(int64) :: npoints
    integer(int64) :: pos
    character(len=MAX_STRING_LEN) :: rank_dir,fields_dir,metadata
    character(len=256) :: iomsg
    real(kind=CUSTOM_REAL), allocatable :: x(:),y(:),z(:),metric(:,:,:,:)
    real(kind=CUSTOM_REAL), allocatable :: rho_s(:,:,:,:),kappav(:,:,:,:),muv(:,:,:,:)
    real(kind=CUSTOM_REAL), allocatable :: kappah(:,:,:,:),muh(:,:,:,:),eta_s(:,:,:,:)
    integer, allocatable :: ibool(:,:,:,:),idoubling(:)
    logical, allocatable :: ispec_bool(:)
    integer(int32), allocatable :: ispec_i32(:)
    real(real64), allocatable :: x_norm(:),y_norm(:),z_norm(:),x_km(:),y_km(:),z_km(:)
    real(real64), allocatable :: rho(:,:,:,:),vp(:,:,:,:),vs(:,:,:,:)
    real(real64), allocatable :: vpv(:,:,:,:),vph(:,:,:,:),vsv(:,:,:,:),vsh(:,:,:,:),eta(:,:,:,:)

    open(newunit=unit,file=trim(filename),status='old',access='stream',form='unformatted', &
      action='read',iostat=ier,iomsg=iomsg)
    if (ier /= 0) then
      print *,'Unsupported or incompatible solver_data.bin layout before model-array extraction.'
      print *,'  file: ',trim(filename)
      print *,'  open_iostat=',ier
      print *,'  open_iomsg=',trim(iomsg)
      stop 1
    endif

    pos = 1_int64
    call read_int_scalar_record(unit,filename,pos,'nspec',nspec)
    call read_int_scalar_record(unit,filename,pos,'nglob',nglob)
    if (nspec <= 0 .or. nglob <= 0) then
      print *,'Invalid solver dimensions in ',trim(filename),nspec,nglob
      stop 1
    endif
    npoints = int(NGLLX,int64) * int(NGLLY,int64) * int(NGLLZ,int64) * int(nspec,int64)

    allocate(x(nglob),y(nglob),z(nglob),stat=ier)
    if (ier /= 0) call allocation_failed('coordinate arrays')
    allocate(ibool(NGLLX,NGLLY,NGLLZ,nspec),idoubling(nspec),ispec_bool(nspec),ispec_i32(nspec),stat=ier)
    if (ier /= 0) call allocation_failed('topology arrays')

    call read_real1_record(unit,filename,pos,'xstore',x,nglob)
    call read_real1_record(unit,filename,pos,'ystore',y,nglob)
    call read_real1_record(unit,filename,pos,'zstore',z,nglob)
    call read_int4_record(unit,filename,pos,'ibool',ibool,NGLLX,NGLLY,NGLLZ,nspec)
    call read_int1_record(unit,filename,pos,'idoubling',idoubling,nspec)
    call read_logical1_record(unit,filename,pos,'ispec_is_tiso',ispec_bool,nspec)
    is_tiso = any(ispec_bool)
    do ispec = 1,nspec
      if (ispec_bool(ispec)) then
        ispec_i32(ispec) = 1_int32
      else
        ispec_i32(ispec) = 0_int32
      endif
    enddo

    call compute_rank_memory_estimate(nspec,nglob,is_tiso,estimated_peak_bytes,source_payload_bytes, &
      geometry_topology_bytes,physical_field_bytes,output_buffer_bytes,safety_margin_bytes)
    call check_rank_memory_limit(trim(filename),memory_limit_mb,estimated_peak_bytes,source_payload_bytes, &
      geometry_topology_bytes,physical_field_bytes,output_buffer_bytes,safety_margin_bytes)

    allocate(metric(NGLLX,NGLLY,NGLLZ,nspec),stat=ier)
    if (ier /= 0) call allocation_failed('metric array')
    allocate(rho_s(NGLLX,NGLLY,NGLLZ,nspec),kappav(NGLLX,NGLLY,NGLLZ,nspec), &
      muv(NGLLX,NGLLY,NGLLZ,nspec),stat=ier)
    if (ier /= 0) call allocation_failed('model arrays')

    do i = 1,9
      call read_real4_record(unit,filename,pos,'metric record',metric,NGLLX,NGLLY,NGLLZ,nspec)
    enddo
    call read_real4_record(unit,filename,pos,'rhostore',rho_s,NGLLX,NGLLY,NGLLZ,nspec)
    call read_real4_record(unit,filename,pos,'kappavstore',kappav,NGLLX,NGLLY,NGLLZ,nspec)
    call read_real4_record(unit,filename,pos,'muvstore',muv,NGLLX,NGLLY,NGLLZ,nspec)

    if (is_tiso) then
      allocate(kappah(NGLLX,NGLLY,NGLLZ,nspec),muh(NGLLX,NGLLY,NGLLZ,nspec), &
        eta_s(NGLLX,NGLLY,NGLLZ,nspec),stat=ier)
      if (ier /= 0) call allocation_failed('TISO model arrays')
      call read_real4_record(unit,filename,pos,'kappahstore',kappah,NGLLX,NGLLY,NGLLZ,nspec)
      call read_real4_record(unit,filename,pos,'muhstore',muh,NGLLX,NGLLY,NGLLZ,nspec)
      call read_real4_record(unit,filename,pos,'eta_anisostore',eta_s,NGLLX,NGLLY,NGLLZ,nspec)
    endif
    close(unit)

    allocate(x_norm(nglob),y_norm(nglob),z_norm(nglob),x_km(nglob),y_km(nglob),z_km(nglob),stat=ier)
    if (ier /= 0) call allocation_failed('coordinate output arrays')
    do i = 1,nglob
      x_norm(i) = dble(x(i))
      y_norm(i) = dble(y(i))
      z_norm(i) = dble(z(i))
      x_km(i) = dble(x(i)) * EARTH_R / 1000.d0
      y_km(i) = dble(y(i)) * EARTH_R / 1000.d0
      z_km(i) = dble(z(i)) * EARTH_R / 1000.d0
    enddo

    rank_dir = trim(output_dir)//'/ranks/'//trim(rank_dir_name(rank))
    fields_dir = trim(rank_dir)//'/fields'
    call make_output_directory(trim(fields_dir))
    call write_npy_real64_1d(trim(rank_dir)//'/x_norm.npy',x_norm,nglob)
    call write_npy_real64_1d(trim(rank_dir)//'/y_norm.npy',y_norm,nglob)
    call write_npy_real64_1d(trim(rank_dir)//'/z_norm.npy',z_norm,nglob)
    call write_npy_real64_1d(trim(rank_dir)//'/x_km.npy',x_km,nglob)
    call write_npy_real64_1d(trim(rank_dir)//'/y_km.npy',y_km,nglob)
    call write_npy_real64_1d(trim(rank_dir)//'/z_km.npy',z_km,nglob)
    call write_npy_int32_4d(trim(rank_dir)//'/ibool.npy',ibool,NGLLX,NGLLY,NGLLZ,nspec)
    call write_npy_int32_1d(trim(rank_dir)//'/idoubling.npy',idoubling,nspec)
    call write_npy_int32_1d(trim(rank_dir)//'/ispec_is_tiso.npy',ispec_i32,nspec)

    allocate(rho(NGLLX,NGLLY,NGLLZ,nspec),stat=ier)
    if (ier /= 0) call allocation_failed('rho output array')
    do ispec = 1,nspec
      do k = 1,NGLLZ
        do j = 1,NGLLY
          do i = 1,NGLLX
            rho(i,j,k,ispec) = dble(rho_s(i,j,k,ispec)) * EARTH_RHOAV
          enddo
        enddo
      enddo
    enddo
    call write_npy_real64_4d(trim(fields_dir)//'/rho.npy',rho,NGLLX,NGLLY,NGLLZ,nspec)

    if (is_tiso) then
      allocate(vpv(NGLLX,NGLLY,NGLLZ,nspec),vph(NGLLX,NGLLY,NGLLZ,nspec), &
        vsv(NGLLX,NGLLY,NGLLZ,nspec),vsh(NGLLX,NGLLY,NGLLZ,nspec),eta(NGLLX,NGLLY,NGLLZ,nspec),stat=ier)
      if (ier /= 0) call allocation_failed('TISO output arrays')
      do ispec = 1,nspec
        do k = 1,NGLLZ
          do j = 1,NGLLY
            do i = 1,NGLLX
              vpv(i,j,k,ispec) = dsqrt((dble(kappav(i,j,k,ispec)) + 4.d0*dble(muv(i,j,k,ispec))/3.d0) / &
                dble(rho_s(i,j,k,ispec))) * velocity_scale()
              vph(i,j,k,ispec) = dsqrt((dble(kappah(i,j,k,ispec)) + 4.d0*dble(muh(i,j,k,ispec))/3.d0) / &
                dble(rho_s(i,j,k,ispec))) * velocity_scale()
              vsv(i,j,k,ispec) = dsqrt(dble(muv(i,j,k,ispec)) / dble(rho_s(i,j,k,ispec))) * velocity_scale()
              vsh(i,j,k,ispec) = dsqrt(dble(muh(i,j,k,ispec)) / dble(rho_s(i,j,k,ispec))) * velocity_scale()
              eta(i,j,k,ispec) = dble(eta_s(i,j,k,ispec))
            enddo
          enddo
        enddo
      enddo
      call write_npy_real64_4d(trim(fields_dir)//'/vpv.npy',vpv,NGLLX,NGLLY,NGLLZ,nspec)
      call write_npy_real64_4d(trim(fields_dir)//'/vph.npy',vph,NGLLX,NGLLY,NGLLZ,nspec)
      call write_npy_real64_4d(trim(fields_dir)//'/vsv.npy',vsv,NGLLX,NGLLY,NGLLZ,nspec)
      call write_npy_real64_4d(trim(fields_dir)//'/vsh.npy',vsh,NGLLX,NGLLY,NGLLZ,nspec)
      call write_npy_real64_4d(trim(fields_dir)//'/eta.npy',eta,NGLLX,NGLLY,NGLLZ,nspec)
    else
      allocate(vp(NGLLX,NGLLY,NGLLZ,nspec),vs(NGLLX,NGLLY,NGLLZ,nspec),stat=ier)
      if (ier /= 0) call allocation_failed('isotropic output arrays')
      do ispec = 1,nspec
        do k = 1,NGLLZ
          do j = 1,NGLLY
            do i = 1,NGLLX
              vp(i,j,k,ispec) = dsqrt((dble(kappav(i,j,k,ispec)) + 4.d0*dble(muv(i,j,k,ispec))/3.d0) / &
                dble(rho_s(i,j,k,ispec))) * velocity_scale()
              vs(i,j,k,ispec) = dsqrt(dble(muv(i,j,k,ispec)) / dble(rho_s(i,j,k,ispec))) * velocity_scale()
            enddo
          enddo
        enddo
      enddo
      call write_npy_real64_4d(trim(fields_dir)//'/vp.npy',vp,NGLLX,NGLLY,NGLLZ,nspec)
      call write_npy_real64_4d(trim(fields_dir)//'/vs.npy',vs,NGLLX,NGLLY,NGLLZ,nspec)
    endif

    metadata = trim(rank_dir)//'/metadata.json'
    call write_rank_metadata(trim(metadata),rank,nspec,nglob,is_tiso,topology_fingerprint(rank,nspec,nglob,is_tiso), &
      geometry_fingerprint(rank,nspec,nglob,is_tiso))
  end subroutine extract_one_rank

  subroutine read_int_scalar_record(unit,filename,pos,record_name,value)
    integer, intent(in) :: unit
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    integer, intent(out) :: value
    integer :: ier
    call read_record_prefix(unit,filename,pos,record_name,4_int64)
    read(unit,pos=pos,iostat=ier) value
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,4_int64)
    pos = pos + 4_int64
    call read_record_suffix(unit,filename,pos,record_name,4_int64)
  end subroutine read_int_scalar_record

  subroutine read_real1_record(unit,filename,pos,record_name,array,n1)
    integer, intent(in) :: unit,n1
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    real(kind=CUSTOM_REAL), intent(out) :: array(n1)
    integer(int64) :: expected
    integer :: ier
    expected = int(n1,int64) * int(CUSTOM_REAL,int64)
    call read_record_prefix(unit,filename,pos,record_name,expected)
    read(unit,pos=pos,iostat=ier) array
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    pos = pos + expected
    call read_record_suffix(unit,filename,pos,record_name,expected)
  end subroutine read_real1_record

  subroutine read_real4_record(unit,filename,pos,record_name,array,n1,n2,n3,n4)
    integer, intent(in) :: unit,n1,n2,n3,n4
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    real(kind=CUSTOM_REAL), intent(out) :: array(n1,n2,n3,n4)
    integer(int64) :: expected
    integer :: ier
    expected = int(n1,int64) * int(n2,int64) * int(n3,int64) * int(n4,int64) * int(CUSTOM_REAL,int64)
    call read_record_prefix(unit,filename,pos,record_name,expected)
    read(unit,pos=pos,iostat=ier) array
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    pos = pos + expected
    call read_record_suffix(unit,filename,pos,record_name,expected)
  end subroutine read_real4_record

  subroutine read_int1_record(unit,filename,pos,record_name,array,n1)
    integer, intent(in) :: unit,n1
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    integer, intent(out) :: array(n1)
    integer(int64) :: expected
    integer :: ier
    expected = int(n1,int64) * 4_int64
    call read_record_prefix(unit,filename,pos,record_name,expected)
    read(unit,pos=pos,iostat=ier) array
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    pos = pos + expected
    call read_record_suffix(unit,filename,pos,record_name,expected)
  end subroutine read_int1_record

  subroutine read_int4_record(unit,filename,pos,record_name,array,n1,n2,n3,n4)
    integer, intent(in) :: unit,n1,n2,n3,n4
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    integer, intent(out) :: array(n1,n2,n3,n4)
    integer(int64) :: expected
    integer :: ier
    expected = int(n1,int64) * int(n2,int64) * int(n3,int64) * int(n4,int64) * 4_int64
    call read_record_prefix(unit,filename,pos,record_name,expected)
    read(unit,pos=pos,iostat=ier) array
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    pos = pos + expected
    call read_record_suffix(unit,filename,pos,record_name,expected)
  end subroutine read_int4_record

  subroutine read_logical1_record(unit,filename,pos,record_name,array,n1)
    integer, intent(in) :: unit,n1
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    logical, intent(out) :: array(n1)
    integer(int64) :: expected
    integer :: ier
    expected = int(n1,int64) * int(storage_size(.false.) / 8,int64)
    call read_record_prefix(unit,filename,pos,record_name,expected)
    read(unit,pos=pos,iostat=ier) array
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    pos = pos + expected
    call read_record_suffix(unit,filename,pos,record_name,expected)
  end subroutine read_logical1_record

  subroutine read_record_prefix(unit,filename,pos,record_name,expected)
    integer, intent(in) :: unit
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    integer(int64), intent(in) :: expected
    integer(int32) :: marker
    integer :: ier
    read(unit,pos=pos,iostat=ier) marker
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    if (int(marker,int64) /= expected) call unsupported_layout(filename,record_name,-1,int(marker,int64),expected)
    pos = pos + int(RECORD_MARKER_BYTES,int64)
  end subroutine read_record_prefix

  subroutine read_record_suffix(unit,filename,pos,record_name,expected)
    integer, intent(in) :: unit
    character(len=*), intent(in) :: filename,record_name
    integer(int64), intent(inout) :: pos
    integer(int64), intent(in) :: expected
    integer(int32) :: marker
    integer :: ier
    read(unit,pos=pos,iostat=ier) marker
    if (ier /= 0) call unsupported_layout(filename,record_name,-1,-1_int64,expected)
    if (int(marker,int64) /= expected) call unsupported_layout(filename,record_name,-1,int(marker,int64),expected)
    pos = pos + int(RECORD_MARKER_BYTES,int64)
  end subroutine read_record_suffix

  subroutine unsupported_layout(filename,context,irec,observed,expected)
    character(len=*), intent(in) :: filename,context
    integer, intent(in) :: irec
    integer(int64), intent(in) :: observed,expected
    print *,'Unsupported or incompatible solver_data.bin layout before model-array extraction.'
    print *,'  file: ',trim(filename)
    print *,'  context: ',trim(context)
    print *,'  record: ',irec
    print *,'  observed_record_length: ',observed
    print *,'  expected_record_length: ',expected
    stop 1
  end subroutine unsupported_layout

  subroutine compute_rank_memory_estimate(nspec,nglob,is_tiso,estimated_peak_bytes,source_payload_bytes, &
    geometry_topology_bytes,physical_field_bytes,output_buffer_bytes,safety_margin_bytes)
    integer, intent(in) :: nspec,nglob
    logical, intent(in) :: is_tiso
    integer(int64), intent(out) :: estimated_peak_bytes,source_payload_bytes,geometry_topology_bytes
    integer(int64), intent(out) :: physical_field_bytes,output_buffer_bytes,safety_margin_bytes
    integer(int64) :: npoints,model_records,field_count

    npoints = int(NGLLX,int64) * int(NGLLY,int64) * int(NGLLZ,int64) * int(nspec,int64)
    if (is_tiso) then
      model_records = 6_int64
      field_count = 6_int64
    else
      model_records = 3_int64
      field_count = 3_int64
    endif

    geometry_topology_bytes = 6_int64 * int(nglob,int64) * 8_int64
    geometry_topology_bytes = geometry_topology_bytes + npoints * 4_int64
    geometry_topology_bytes = geometry_topology_bytes + int(nspec,int64) * 12_int64

    source_payload_bytes = npoints * int(CUSTOM_REAL,int64) * (9_int64 + model_records)
    physical_field_bytes = npoints * 8_int64 * field_count
    output_buffer_bytes = 6_int64 * int(nglob,int64) * 8_int64 + npoints * 4_int64 + int(nspec,int64) * 8_int64
    safety_margin_bytes = 64_int64 * 1024_int64 * 1024_int64
    estimated_peak_bytes = geometry_topology_bytes + source_payload_bytes + physical_field_bytes + &
      output_buffer_bytes + safety_margin_bytes
  end subroutine compute_rank_memory_estimate

  subroutine check_rank_memory_limit(filename,memory_limit_mb,estimated_peak_bytes,source_payload_bytes, &
    geometry_topology_bytes,physical_field_bytes,output_buffer_bytes,safety_margin_bytes)
    character(len=*), intent(in) :: filename
    integer, intent(in) :: memory_limit_mb
    integer(int64), intent(in) :: estimated_peak_bytes,source_payload_bytes,geometry_topology_bytes
    integer(int64), intent(in) :: physical_field_bytes,output_buffer_bytes,safety_margin_bytes
    integer(int64) :: limit_bytes
    limit_bytes = int(memory_limit_mb,int64) * 1024_int64 * 1024_int64
    if (estimated_peak_bytes > limit_bytes) then
      print *,'Per-rank memory estimate exceeds --memory-limit-mb before model-array reads.'
      print *,'  file: ',trim(filename)
      print *,'  estimated_peak_memory_bytes: ',estimated_peak_bytes
      print *,'  estimated_peak_memory_mb: ',dble(estimated_peak_bytes) / 1024.d0 / 1024.d0
      print *,'  memory_limit_mb: ',memory_limit_mb
      print *,'  source_record_payload_bytes: ',source_payload_bytes
      print *,'  geometry_topology_bytes: ',geometry_topology_bytes
      print *,'  physical_field_array_bytes: ',physical_field_bytes
      print *,'  output_buffer_bytes: ',output_buffer_bytes
      print *,'  safety_margin_bytes: ',safety_margin_bytes
      stop 1
    endif
  end subroutine check_rank_memory_limit

  subroutine reject_explicit_full_anisotropy(db_dir)
    character(len=*), intent(in) :: db_dir
    character(len=MAX_STRING_LEN) :: values_file,line
    integer :: unit,ier
    values_file = trim(db_dir)//'/../OUTPUT_FILES/values_from_mesher.h'
    open(newunit=unit,file=trim(values_file),status='old',action='read',iostat=ier)
    if (ier /= 0) return
    do
      read(unit,'(a)',iostat=ier) line
      if (ier /= 0) exit
      if (index(line,'ANISOTROPIC_3D_MANTLE_VAL') > 0 .and. index(line,'.true.') > 0) then
        close(unit)
        print *,'Unsupported full anisotropic mantle layout: ANISOTROPIC_3D_MANTLE_VAL = .true.'
        print *,'  file: ',trim(values_file)
        print *,'  Task 4C v1 supports isotropic and TISO reg1 physical-field extraction only.'
        stop 1
      endif
    enddo
    close(unit)
  end subroutine reject_explicit_full_anisotropy

  subroutine make_output_directory(output_dir)
    character(len=*), intent(in) :: output_dir
    character(len=MAX_STRING_LEN) :: command
    integer :: status
    command = 'mkdir -p "'//trim(output_dir)//'"'
    call execute_command_line(trim(command),exitstat=status)
    if (status /= 0) then
      print *,'Could not create output directory: ',trim(output_dir)
      stop 1
    endif
  end subroutine make_output_directory

  subroutine make_solver_filename(db_dir,iproc,iregion,filename)
    character(len=*), intent(in) :: db_dir
    integer, intent(in) :: iproc,iregion
    character(len=*), intent(out) :: filename
    character(len=64) :: procname
    write(procname,"('/proc',i6.6,'_reg',i1,'_solver_data.bin')") iproc,iregion
    filename = trim(db_dir)//trim(procname)
  end subroutine make_solver_filename

  subroutine read_solver_dimensions(filename,nspec,nglob)
    character(len=*), intent(in) :: filename
    integer, intent(out) :: nspec,nglob
    integer :: unit,ier
    open(newunit=unit,file=trim(filename),status='old',form='unformatted',action='read',iostat=ier)
    if (ier /= 0) then
      print *,'Error opening solver database: ',trim(filename)
      stop 1
    endif
    read(unit,iostat=ier) nspec
    if (ier /= 0) then
      print *,'Error reading nspec record from ',trim(filename)
      stop 1
    endif
    read(unit,iostat=ier) nglob
    if (ier /= 0) then
      print *,'Error reading nglob record from ',trim(filename)
      stop 1
    endif
    close(unit)
    if (nspec <= 0 .or. nglob <= 0) then
      print *,'Invalid solver dimensions in ',trim(filename),nspec,nglob
      stop 1
    endif
  end subroutine read_solver_dimensions

  logical function no_more_rank_files(db_dir,iproc)
    character(len=*), intent(in) :: db_dir
    integer, intent(in) :: iproc
    integer :: iregion
    character(len=MAX_STRING_LEN) :: filename
    logical :: exists
    no_more_rank_files = .true.
    do iregion = 1,3
      call make_solver_filename(db_dir,iproc,iregion,filename)
      inquire(file=trim(filename),exist=exists)
      if (exists) no_more_rank_files = .false.
    enddo
  end function no_more_rank_files

  subroutine write_npy_real64_1d(filename,array,n1)
    character(len=*), intent(in) :: filename
    integer, intent(in) :: n1
    real(real64), intent(in) :: array(n1)
    call write_npy_header_and_real64_1d(filename,array,n1)
  end subroutine write_npy_real64_1d

  subroutine write_npy_real64_4d(filename,array,n1,n2,n3,n4)
    character(len=*), intent(in) :: filename
    integer, intent(in) :: n1,n2,n3,n4
    real(real64), intent(in) :: array(n1,n2,n3,n4)
    integer :: unit,ier
    call open_npy(unit,filename,'<f8',.true.,shape4(n1,n2,n3,n4),ier)
    if (ier /= 0) stop 1
    write(unit) array
    close(unit)
  end subroutine write_npy_real64_4d

  subroutine write_npy_int32_1d(filename,array,n1)
    character(len=*), intent(in) :: filename
    integer, intent(in) :: n1
    integer(int32), intent(in) :: array(n1)
    integer :: unit,ier
    call open_npy(unit,filename,'<i4',.false.,shape1(n1),ier)
    if (ier /= 0) stop 1
    write(unit) array
    close(unit)
  end subroutine write_npy_int32_1d

  subroutine write_npy_int32_4d(filename,array,n1,n2,n3,n4)
    character(len=*), intent(in) :: filename
    integer, intent(in) :: n1,n2,n3,n4
    integer, intent(in) :: array(n1,n2,n3,n4)
    integer(int32), allocatable :: converted(:,:,:,:)
    integer :: unit,ier
    allocate(converted(n1,n2,n3,n4),stat=ier)
    if (ier /= 0) call allocation_failed('int32 output conversion')
    converted = int(array,int32)
    call open_npy(unit,filename,'<i4',.true.,shape4(n1,n2,n3,n4),ier)
    if (ier /= 0) stop 1
    write(unit) converted
    close(unit)
  end subroutine write_npy_int32_4d

  subroutine write_npy_header_and_real64_1d(filename,array,n1)
    character(len=*), intent(in) :: filename
    integer, intent(in) :: n1
    real(real64), intent(in) :: array(n1)
    integer :: unit,ier
    call open_npy(unit,filename,'<f8',.false.,shape1(n1),ier)
    if (ier /= 0) stop 1
    write(unit) array
    close(unit)
  end subroutine write_npy_header_and_real64_1d

  subroutine open_npy(unit,filename,descr,fortran_order,shape_text,ier)
    integer, intent(out) :: unit,ier
    character(len=*), intent(in) :: filename,descr,shape_text
    logical, intent(in) :: fortran_order
    character(len=:), allocatable :: dict,header
    integer :: header_len,padding
    integer(int16) :: header_len_i16
    open(newunit=unit,file=trim(filename),status='replace',access='stream',form='unformatted', &
      action='write',iostat=ier)
    if (ier /= 0) then
      print *,'Error opening npy output: ',trim(filename)
      return
    endif
    if (fortran_order) then
      dict = "{'descr': '"//trim(descr)//"', 'fortran_order': True, 'shape': "//trim(shape_text)//", }"
    else
      dict = "{'descr': '"//trim(descr)//"', 'fortran_order': False, 'shape': "//trim(shape_text)//", }"
    endif
    padding = modulo(16 - modulo(10 + len(dict) + 1,16),16)
    header = dict//repeat(' ',padding)//achar(10)
    header_len = len(header)
    header_len_i16 = int(header_len,int16)
    call write_npy_magic(unit)
    write(unit) achar(1)
    write(unit) achar(0)
    write(unit) header_len_i16
    write(unit) header
  end subroutine open_npy

  subroutine write_npy_magic(unit)
    integer, intent(in) :: unit
    integer(int8), dimension(6) :: magic
    magic = [int(-109,int8), int(78,int8), int(85,int8), int(77,int8), int(80,int8), int(89,int8)]
    write(unit) magic
  end subroutine write_npy_magic

  character(len=64) function shape1(n1)
    integer, intent(in) :: n1
    write(shape1,"('(',i0,',)')") n1
  end function shape1

  character(len=96) function shape4(n1,n2,n3,n4)
    integer, intent(in) :: n1,n2,n3,n4
    write(shape4,"('(',i0,', ',i0,', ',i0,', ',i0,')')") n1,n2,n3,n4
  end function shape4

  subroutine write_rank_metadata(path,rank,nspec,nglob,is_tiso,topology_fp,geometry_fp)
    character(len=*), intent(in) :: path,topology_fp,geometry_fp
    integer, intent(in) :: rank,nspec,nglob
    logical, intent(in) :: is_tiso
    integer :: unit,ier
    open(newunit=unit,file=trim(path),status='replace',action='write',iostat=ier)
    if (ier /= 0) then
      print *,'Error opening rank metadata: ',trim(path)
      stop 1
    endif
    write(unit,'(a)') '{'
    write(unit,'(a)') '  "schema_version": "ulvz_model_postprocess.v1",'
    write(unit,'(a,i0,a)') '  "rank": ',rank,','
    write(unit,'(a)') '  "region": 1,'
    write(unit,'(a,i0,a)') '  "nglob": ',nglob,','
    write(unit,'(a,i0,a)') '  "nspec": ',nspec,','
    write(unit,'(a,i0,a,i0,a,i0,a)') '  "gll_dimensions": [',NGLLX,', ',NGLLY,', ',NGLLZ,'],'
    write(unit,'(a)') '  "coordinate_units": {"x_km": "km", "y_km": "km", "z_km": "km"},'
    call write_field_units(unit,is_tiso)
    write(unit,'(a)',advance='no') '  "array_files": {"ibool": "ibool.npy", "idoubling": "idoubling.npy", '
    write(unit,'(a)',advance='no') '"ispec_is_tiso": "ispec_is_tiso.npy", "x_km": "x_km.npy", '
    write(unit,'(a)',advance='no') '"x_norm": "x_norm.npy", "y_km": "y_km.npy", '
    write(unit,'(a)') '"y_norm": "y_norm.npy", "z_km": "z_km.npy", "z_norm": "z_norm.npy"},'
    if (is_tiso) then
      write(unit,'(a)',advance='no') '  "field_files": {"eta": "fields/eta.npy", '
      write(unit,'(a)',advance='no') '"rho": "fields/rho.npy", "vph": "fields/vph.npy", '
      write(unit,'(a)') '"vsh": "fields/vsh.npy", "vpv": "fields/vpv.npy", "vsv": "fields/vsv.npy"},'
    else
      write(unit,'(a)') '  "field_files": {"rho": "fields/rho.npy", "vp": "fields/vp.npy", "vs": "fields/vs.npy"},'
    endif
    write(unit,'(a,a,a)') '  "topology_fingerprint": "',trim(topology_fp),'",'
    write(unit,'(a,a,a)') '  "geometry_fingerprint": "',trim(geometry_fp),'"'
    write(unit,'(a)') '}'
    close(unit)
  end subroutine write_rank_metadata

  subroutine write_rank_manifest_entry(unit,rank,nspec,nglob,is_tiso,nested)
    integer, intent(in) :: unit,rank,nspec,nglob
    logical, intent(in) :: is_tiso,nested
    if (nested) continue
    write(unit,'(a)',advance='no') '    {'
    write(unit,'(a,i0,a)',advance='no') '"rank": ',rank,', '
    write(unit,'(a)',advance='no') '"region": 1, '
    write(unit,'(a,a,a)',advance='no') '"path": "ranks/',trim(rank_dir_name(rank)),'", '
    write(unit,'(a,i0,a)',advance='no') '"nglob": ',nglob,', '
    write(unit,'(a,i0,a)',advance='no') '"nspec": ',nspec,', '
    write(unit,'(a,i0,a,i0,a,i0,a)',advance='no') '"gll_dimensions": [',NGLLX,', ',NGLLY,', ',NGLLZ,'], '
    if (is_tiso) then
      write(unit,'(a)',advance='no') '"fields": ["eta", "rho", "vph", "vsh", "vpv", "vsv"], '
    else
      write(unit,'(a)',advance='no') '"fields": ["rho", "vp", "vs"], '
    endif
    write(unit,'(a,a,a)',advance='no') '"topology_fingerprint": "', &
      trim(topology_fingerprint(rank,nspec,nglob,is_tiso)),'", '
    write(unit,'(a,a,a)',advance='no') '"geometry_fingerprint": "', &
      trim(geometry_fingerprint(rank,nspec,nglob,is_tiso)),'"'
    write(unit,'(a)',advance='no') '}'
  end subroutine write_rank_manifest_entry

  subroutine write_memory_estimate_entry(unit,rank,memory_limit_mb,estimated_peak_bytes,source_payload_bytes, &
    geometry_topology_bytes,physical_field_bytes,output_buffer_bytes,safety_margin_bytes,nested)
    integer, intent(in) :: unit,rank,memory_limit_mb
    integer(int64), intent(in) :: estimated_peak_bytes,source_payload_bytes,geometry_topology_bytes
    integer(int64), intent(in) :: physical_field_bytes,output_buffer_bytes,safety_margin_bytes
    logical, intent(in) :: nested
    if (nested) continue
    write(unit,'(a)',advance='no') '      {'
    write(unit,'(a,i0,a)',advance='no') '"rank": ',rank,', '
    write(unit,'(a)',advance='no') '"region": 1, '
    write(unit,'(a,i0,a)',advance='no') '"estimated_peak_memory_bytes": ',estimated_peak_bytes,', '
    write(unit,'(a,f12.6,a)',advance='no') '"estimated_peak_memory_mb": ', &
      dble(estimated_peak_bytes) / 1024.d0 / 1024.d0,', '
    write(unit,'(a,i0,a)',advance='no') '"memory_limit_mb": ',memory_limit_mb,', '
    write(unit,'(a,i0,a)',advance='no') '"source_record_payload_bytes": ',source_payload_bytes,', '
    write(unit,'(a,i0,a)',advance='no') '"geometry_topology_bytes": ',geometry_topology_bytes,', '
    write(unit,'(a,i0,a)',advance='no') '"physical_field_array_bytes": ',physical_field_bytes,', '
    write(unit,'(a,i0,a)',advance='no') '"output_buffer_bytes": ',output_buffer_bytes,', '
    write(unit,'(a,i0,a)',advance='no') '"safety_margin_bytes": ',safety_margin_bytes,', '
    write(unit,'(a)',advance='no') '"safety_margin_policy": "fixed 64 MiB conservative overhead", '
    write(unit,'(a)',advance='no') '"decision": "accepted"'
    write(unit,'(a)',advance='no') '}'
  end subroutine write_memory_estimate_entry

  subroutine write_field_units(unit,is_tiso)
    integer, intent(in) :: unit
    logical, intent(in) :: is_tiso
    if (is_tiso) then
      write(unit,'(a)',advance='no') '  "field_units": {"eta": "dimensionless", "rho": "kg m^-3", '
      write(unit,'(a)') '"vph": "m s^-1", "vsh": "m s^-1", "vpv": "m s^-1", "vsv": "m s^-1"},'
    else
      write(unit,'(a)') '  "field_units": {"rho": "kg m^-3", "vp": "m s^-1", "vs": "m s^-1"},'
    endif
  end subroutine write_field_units

  subroutine write_field_units_nested(unit,is_tiso)
    integer, intent(in) :: unit
    logical, intent(in) :: is_tiso
    if (is_tiso) then
      write(unit,'(a)',advance='no') '    "field_units": {"eta": "dimensionless", "rho": "kg m^-3", '
      write(unit,'(a)') '"vph": "m s^-1", "vsh": "m s^-1", "vpv": "m s^-1", "vsv": "m s^-1"},'
    else
      write(unit,'(a)') '    "field_units": {"rho": "kg m^-3", "vp": "m s^-1", "vs": "m s^-1"},'
    endif
  end subroutine write_field_units_nested

  subroutine write_field_derivations(unit,is_tiso)
    integer, intent(in) :: unit
    logical, intent(in) :: is_tiso
    if (is_tiso) then
      write(unit,'(a)',advance='no') '  "field_derivations": {"eta": "TISO eta copied from eta_anisostore", '
      write(unit,'(a)',advance='no') '"rho": "rho = rhostore * density_scale_to_kg_m-3", '
      write(unit,'(a)',advance='no') '"vph": "TISO vph = sqrt((kappah + 4*muh/3) / rhostore) * velocity_scale_to_m_s-1", '
      write(unit,'(a)',advance='no') '"vsh": "TISO vsh = sqrt(muh / rhostore) * velocity_scale_to_m_s-1", '
      write(unit,'(a)',advance='no') '"vpv": "TISO vpv = sqrt((kappav + 4*muv/3) / rhostore) * velocity_scale_to_m_s-1", '
      write(unit,'(a)') '"vsv": "TISO vsv = sqrt(muv / rhostore) * velocity_scale_to_m_s-1"},'
    else
      write(unit,'(a)',advance='no') '  "field_derivations": {"rho": "rho = rhostore * density_scale_to_kg_m-3", '
      write(unit,'(a)',advance='no') '"vp": "isotropic vp = sqrt((kappav + 4*muv/3) / rhostore) * velocity_scale_to_m_s-1", '
      write(unit,'(a)') '"vs": "isotropic vs = sqrt(muv / rhostore) * velocity_scale_to_m_s-1"},'
    endif
  end subroutine write_field_derivations

  subroutine write_scaling_convention(unit,indent)
    integer, intent(in) :: unit
    character(len=*), intent(in) :: indent
    write(unit,'(a)',advance='no') trim(indent)//'"model_field_scaling_convention": '
    write(unit,'(a)',advance='no') '"stored physical SI model fields; velocities are m s^-1, '
    write(unit,'(a)') 'density is kg m^-3; plotting may display velocities in km s^-1",'
  end subroutine write_scaling_convention

  character(len=64) function rank_dir_name(rank)
    integer, intent(in) :: rank
    write(rank_dir_name,"('rank',i6.6,'_reg1')") rank
  end function rank_dir_name

  character(len=128) function topology_fingerprint(rank,nspec,nglob,is_tiso)
    integer, intent(in) :: rank,nspec,nglob
    logical, intent(in) :: is_tiso
    write(topology_fingerprint,"('topology-r',i0,'-n',i0,'-g',i0,'-t',l1)") rank,nspec,nglob,is_tiso
  end function topology_fingerprint

  character(len=128) function geometry_fingerprint(rank,nspec,nglob,is_tiso)
    integer, intent(in) :: rank,nspec,nglob
    logical, intent(in) :: is_tiso
    write(geometry_fingerprint,"('geometry-r',i0,'-n',i0,'-g',i0,'-t',l1)") rank,nspec,nglob,is_tiso
  end function geometry_fingerprint

  character(len=256) function global_topology_fingerprint(rank_count,ranks,nspecs,nglobs,tiso_flags)
    integer, intent(in) :: rank_count
    integer, intent(in) :: ranks(:),nspecs(:),nglobs(:)
    logical, intent(in) :: tiso_flags(:)
    write(global_topology_fingerprint, &
      "('global-topology-count',i0,'-first',i0,'-last',i0,'-nspec',i0,'-nglob',i0,'-t',l1)") &
      rank_count,ranks(1),ranks(rank_count),nspecs(1),nglobs(1),any(tiso_flags(1:rank_count))
  end function global_topology_fingerprint

  character(len=256) function global_geometry_fingerprint(rank_count,ranks,nspecs,nglobs,tiso_flags)
    integer, intent(in) :: rank_count
    integer, intent(in) :: ranks(:),nspecs(:),nglobs(:)
    logical, intent(in) :: tiso_flags(:)
    write(global_geometry_fingerprint, &
      "('global-geometry-count',i0,'-first',i0,'-last',i0,'-nspec',i0,'-nglob',i0,'-t',l1)") &
      rank_count,ranks(1),ranks(rank_count),nspecs(1),nglobs(1),any(tiso_flags(1:rank_count))
  end function global_geometry_fingerprint

  character(len=256) function compatibility_fingerprint(rank_count,nspecs,nglobs,tiso_flags,mode_name)
    integer, intent(in) :: rank_count
    integer, intent(in) :: nspecs(:),nglobs(:)
    logical, intent(in) :: tiso_flags(:)
    character(len=*), intent(in) :: mode_name
    write(compatibility_fingerprint,"('compat-',a,'-count',i0,'-nspec',i0,'-nglob',i0,'-t',l1)") &
      trim(mode_name),rank_count,nspecs(1),nglobs(1),any(tiso_flags(1:rank_count))
  end function compatibility_fingerprint

  double precision function velocity_scale()
    velocity_scale = EARTH_R * dsqrt(PI * GRAV * EARTH_RHOAV)
  end function velocity_scale

  subroutine allocation_failed(context)
    character(len=*), intent(in) :: context
    print *,'Allocation failed for ',trim(context)
    stop 1
  end subroutine allocation_failed

  character(len=32) function custom_real_name()
    if (CUSTOM_REAL == SIZE_REAL) then
      custom_real_name = 'SIZE_REAL'
    else if (CUSTOM_REAL == SIZE_DOUBLE) then
      custom_real_name = 'SIZE_DOUBLE'
    else
      custom_real_name = 'UNSUPPORTED'
    endif
  end function custom_real_name

  character(len=MAX_STRING_LEN) function json_escape(value)
    character(len=*), intent(in) :: value
    integer :: i,n
    json_escape = ''
    n = 0
    do i = 1,len_trim(value)
      if (value(i:i) == '"') then
        if (n + 2 <= len(json_escape)) then
          json_escape(n+1:n+2) = '\"'
          n = n + 2
        endif
      else if (value(i:i) == '\') then
        if (n + 2 <= len(json_escape)) then
          json_escape(n+1:n+2) = '\\'
          n = n + 2
        endif
      else
        if (n + 1 <= len(json_escape)) then
          json_escape(n+1:n+1) = value(i:i)
          n = n + 1
        endif
      endif
    enddo
  end function json_escape

end program ulvz_model_extract
