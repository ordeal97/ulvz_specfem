# Current SPECFEM Setup Audit

Audit date: 2026-06-26

Scope: read-only inspection of the current repository, except for creating this audit file. No simulation inputs were modified and no expensive calculations were run.

## 1. SPECFEM Version, Compilation Configuration, and Workflow

- SPECFEM tree: `specfem3d_globe/`
- SPECFEM version: `8.1.1`, from `specfem3d_globe/VERSION`.
- Git state of SPECFEM tree at audit time:
  - branch: `devel`
  - commit: `9c312cb2`
- Configure command recorded in `specfem3d_globe/config.log`:
  - `./configure CC=/usr/bin/mpicc FC=/usr/bin/gfortran MPIFC=/usr/bin/mpif90 --with-mpi`
  - `config.log` also reports `WARNING: unrecognized options: --with-mpi`; however the generated `Makefile` still uses MPI compiler wrappers for C and Fortran linking.
- Main compiler settings from `specfem3d_globe/Makefile`:
  - `FC = /usr/bin/gfortran`
  - `MPIFC = /usr/bin/mpif90`
  - `CC = /usr/bin/mpicc`
  - `FCFLAGS = -g -O2`
  - checking flags include `-std=f2008`, `-fimplicit-none`, warnings, floating-point traps, and `-O3 -finline-functions`.
- Acceleration / I/O configuration:
  - CUDA/GPU support disabled in Makefile/config.
  - `GPU_MODE = .false.` in `DATA/Par_file`.
  - `ADIOS_ENABLED = .false.` in `DATA/Par_file`.
  - `HDF5_ENABLED = .false.` in `DATA/Par_file`.
- Built executables currently visible:
  - `specfem3d_globe/bin/xmeshfem3D`
  - `specfem3d_globe/bin/xspecfem3D` was not present during this audit.

Existing workflow appears to be the standard SPECFEM workflow, but not fully materialized as a project-specific run script:

1. Configure and compile SPECFEM.
2. Run the mesher using `bin/xmeshfem3D`.
3. Run the solver using `bin/xspecfem3D`.

The current repository does not contain a root-level project run script or scheduler script. The SPECFEM source tree contains upstream example and cluster scripts under `EXAMPLES/` and `utils/scripts/Cluster/`, but those are generic upstream assets, not clearly the current project workflow.

`DATABASES_MPI/` and `OUTPUT_FILES/` are empty at audit time, so no completed current mesh or solver output was available to verify runtime behavior.

## 2. Current 3-D Model Read or Generated

The current active model in `specfem3d_globe/DATA/Par_file` is:

```text
MODEL = 1D_isotropic_prem
```

Therefore the current setup does not read a project-specific 3-D velocity/density model. The elastic background is generated internally from SPECFEM's built-in isotropic PREM logic during meshing.

3-D effects enabled in `Par_file` are geometry/physics options rather than a user 3-D mantle model:

- `OCEANS = .true.`
- `ELLIPTICITY = .true.`
- `TOPOGRAPHY = .true.`
- `GRAVITY = .true.`
- `ROTATION = .true.`
- `ATTENUATION = .true.`

Relevant existing input-model mechanisms found in the tree:

- `DATA/PPM/`: Point-Profile Model input. This reads `DATA/PPM/model.txt` as lon/lat/depth Vs perturbations and can be selected with `MODEL = PPM`.
- `DATA/heterogen/`: generic `heterogen.dat` input. The README and source show this is a direct-access formatted file read by `model_heterogen_mantle.f90`; default constants and radial bounds are compiled into source.
- Built-in global/regional model datasets exist under `DATA/` (`s20rts`, `s40rts`, `sglobe`, `SEMUCB_A3d`, etc.), but none are selected by the current `Par_file`.

Important limitation for no-source ULVZ work:

- `PPM` can be used without editing SPECFEM source, but in the current source `model_ppm.f90` has `SCALE_MODEL = .false.`, so by default it applies only `dVs`; it does not apply `dVp` or `dRho` unless SPECFEM source is edited and recompiled.
- `heterogen` can read a user model without changing `Par_file` beyond `MODEL`, but its grid dimensions/radial bounds and `dVp/dVs` scaling are source constants. It is not a clean no-source route for arbitrary CMB ULVZ parameters.

## 3. Regional vs Global Configuration

The current setup is a regional one-chunk configuration, not a global six-chunk model.

Confirmed settings in `DATA/Par_file`:

- `NCHUNKS = 1`
- `ANGULAR_WIDTH_XI_IN_DEGREES = 20.d0`
- `ANGULAR_WIDTH_ETA_IN_DEGREES = 20.d0`
- `CENTER_LATITUDE_IN_DEGREES = 40.d0`
- `CENTER_LONGITUDE_IN_DEGREES = 25.d0`
- `GAMMA_ROTATION_AZIMUTH = 0.d0`
- `NEX_XI = 64`
- `NEX_ETA = 64`
- `NPROC_XI = 2`
- `NPROC_ETA = 2`
- `ABSORBING_CONDITIONS = .true.`
- `REGIONAL_MESH_CUTOFF = .false.`

Expected MPI rank count from the current `Par_file`:

```text
NPROC = NCHUNKS * NPROC_XI * NPROC_ETA = 1 * 2 * 2 = 4
```

Because `REGIONAL_MESH_CUTOFF = .false.`, the regional one-chunk mesh is not configured to cut off at one of the listed mantle depths.

## 4. Files Controlling Source, Stations, Mesh, Attenuation, Sampling, and MPI

Primary current input files:

- Source:
  - `specfem3d_globe/DATA/CMTSOLUTION`
  - Current source is the 1994-06-09 Northern Bolivia event, event name `060994A`, depth `647.1000 km`, moment-tensor source.
  - `USE_FORCE_POINT_SOURCE = .false.` in `DATA/Par_file`, so CMTSOLUTION is active rather than FORCESOLUTION.
- Stations:
  - `specfem3d_globe/DATA/STATIONS`
  - 129 station lines were present at audit time.
  - `RECEIVERS_CAN_BE_BURIED = .true.` in `DATA/Par_file`.
- Mesh and model selection:
  - `specfem3d_globe/DATA/Par_file`
  - Key controls: `NCHUNKS`, angular width, chunk center, `NEX_XI`, `NEX_ETA`, `NPROC_XI`, `NPROC_ETA`, `MODEL`, `REGIONAL_MESH_CUTOFF`, `LOCAL_PATH`.
- Attenuation:
  - `specfem3d_globe/DATA/Par_file`
  - `ATTENUATION = .true.`
  - `PARTIAL_PHYS_DISPERSION_ONLY = .true.`
  - `UNDO_ATTENUATION = .false.`
  - No project-specific 3-D attenuation model is selected.
- Output duration and sampling:
  - `RECORD_LENGTH_IN_MINUTES = 2.5d0`
  - `NTSTEP_BETWEEN_OUTPUT_INFO = 500`
  - `NTSTEP_BETWEEN_OUTPUT_SEISMOS = 5000000`
  - `NTSTEP_BETWEEN_OUTPUT_SAMPLE = 1`
  - `OUTPUT_SEISMOS_ASCII_TEXT = .true.`
  - SAC, ASDF, 3-D array, and HDF5 seismogram outputs are disabled.
  - `WRITE_SEISMOGRAMS_BY_MAIN = .false.`
- MPI execution:
  - MPI rank count is controlled by `NCHUNKS`, `NPROC_XI`, and `NPROC_ETA` in `DATA/Par_file`.
  - Current expected run size is 4 MPI ranks.
  - No current project-specific MPI command or scheduler submission file was found at repository root.
  - Upstream examples generally compute `numnodes = NCHUNKS * NPROC_XI * NPROC_ETA` and run `mpiexec -np $numnodes ./bin/xmeshfem3D` or `./bin/xspecfem3D`.
- Runtime database/output directories:
  - `LOCAL_PATH = ./DATABASES_MPI`
  - `LOCAL_TMP_PATH = ./DATABASES_MPI`
  - `OUTPUT_FILES/` exists but was empty during audit.

## 5. Minimal Plan for Adding a Synthetic CMB ULVZ Without Editing SPECFEM Source

Two no-source paths are viable, with different scientific capabilities.

Recommended minimal path for full `dVp`, `dVs`, and `dRho` control:

1. Preserve the current reference case as a separate run directory containing copies of `DATA/Par_file`, `DATA/CMTSOLUTION`, `DATA/STATIONS`, SPECFEM version, git commit, and the MPI command.
2. Build the missing solver executable if needed, but do not change SPECFEM source. This is a compile step, not a source edit.
3. Run only the mesher for the reference case to create `DATABASES_MPI/`.
4. Create a separate ULVZ case directory; copy the reference mesh/database rather than overwriting it.
5. Write a small external model-injection script that:
   - reads each `DATABASES_MPI/proc*_reg1_*` model file needed by the current model parameterization,
   - identifies GLL points inside the desired CMB ULVZ geometry,
   - applies documented fractional perturbations `dVp`, `dVs`, and `dRho`,
   - uses a smooth taper at the ULVZ boundary unless a sharp boundary is explicitly requested,
   - writes a new database into the ULVZ case directory,
   - writes a machine-readable YAML or CSV record with ULVZ center, coordinate convention, radius/depth bounds, thickness, lateral radius, transition width, and perturbation amplitudes.
6. Verify on the generated database before running the solver:
   - perturbation extrema match the requested values,
   - perturbed points lie at the intended CMB location,
   - no NaNs or negative velocities/densities were introduced,
   - the background database remains unchanged.
7. Run a short, cheap solver test before any production run, using the same MPI rank count and input copies.

Alternative minimal path for a Vs-only ULVZ:

1. Generate a regular lon/lat/depth ASCII grid in `DATA/PPM/` describing a localized CMB `dVs` perturbation.
2. Point `DATA/PPM/model.txt` to that file and set `MODEL = PPM` in a copied case `Par_file`.
3. Keep `dVp = 0` and `dRho = 0` as an explicit scientific assumption, because current `PPM` source has `SCALE_MODEL = .false.`.
4. Run mesher and validate that the PPM perturbation is sampled where expected.

The PPM route is simpler operationally but does not satisfy a general ULVZ specification requiring independent `dVp`, `dVs`, and `dRho` without editing SPECFEM source.

## 6. Uncertainties and Missing Information

- No project-specific run script or scheduler file was found at repository root, so the exact intended MPI launch command is not recorded.
- `bin/xspecfem3D` was not present during audit, so the solver was not currently built or not located in `bin/`.
- `DATABASES_MPI/` is empty, so the actual generated model database filenames for this exact current case were not available to inspect.
- Because no mesh has been generated in the current checkout, the exact binary array shape for post-mesher perturbation should be confirmed from generated files before writing any injection script.
- The desired ULVZ physical parameters are not specified yet:
  - center latitude/longitude and whether latitude is geographic or geocentric,
  - CMB radius/depth convention,
  - thickness,
  - lateral radius/shape,
  - `dVp`, `dVs`, `dRho`,
  - taper width,
  - whether perturbations should be isotropic or affect TI components separately.
- The current regional chunk is centered at `40N, 25E`. It is not yet confirmed that the desired source-receiver paths and target CMB ULVZ location fall inside the modeled chunk in a physically useful way.
- Attenuation is enabled, but no decision was found on whether ULVZ cases should keep exactly the same attenuation as the reference. Project rules say not to modify attenuation unless explicitly instructed.
- The current `STATIONS` file contains global II/IU stations; with a regional one-chunk setup, it is not yet confirmed which receivers are inside/usable for this regional domain.
- No baseline reference simulation exists in `OUTPUT_FILES/`, so there is not yet a validated reference waveform set for comparing ULVZ perturbations.
