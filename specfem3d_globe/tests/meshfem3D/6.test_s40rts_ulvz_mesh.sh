#!/bin/bash

set -euo pipefail

testdir=$(pwd)
var=inspect_s40rts_ulvz_database

if [ -z "${ROOT:-}" ]; then export ROOT=../../ ; fi
root_abs=$(cd "$ROOT" && pwd)
specfem_version=$(sed -n '1p' "$root_abs/VERSION" 2>/dev/null || echo "unknown")
start_seconds=$SECONDS

MPIEXEC=${MPIEXEC:-mpirun}
MPI_NPROC_FLAG=${MPI_NPROC_FLAG:--np}
NPROC=${NPROC:-2}
OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
export OMP_NUM_THREADS
EXPORT_MESH_VIZ_DATA=${EXPORT_MESH_VIZ_DATA:-0}
EXPORT_PARAVIEW_MESH_DATA=${EXPORT_PARAVIEW_MESH_DATA:-0}
KEEP_TEST_WORKDIR=${KEEP_TEST_WORKDIR:-0}

if [ "$EXPORT_MESH_VIZ_DATA" = "1" ] && [ "$KEEP_TEST_WORKDIR" != "1" ]; then
  echo "EXPORT_MESH_VIZ_DATA=1 requires KEEP_TEST_WORKDIR=1 so plot exports are preserved" >&2
  exit 1
fi
if [ "$EXPORT_PARAVIEW_MESH_DATA" = "1" ] && [ "$KEEP_TEST_WORKDIR" != "1" ]; then
  echo "EXPORT_PARAVIEW_MESH_DATA=1 requires KEEP_TEST_WORKDIR=1 so ParaView mesh exports are preserved" >&2
  exit 1
fi

if [ "$NPROC" != "2" ]; then
  echo "Task 3D fixture requires NPROC=2, got NPROC=$NPROC" >&2
  exit 1
fi

fixture_dir="$testdir/s40rts_ulvz_mesh_fixture"
workdir="$testdir/s40rts_ulvz_mesh_work_$(date +%Y%m%d_%H%M%S)_$$"
report_dir="$workdir/reports"
disabled_case="$workdir/reference_disabled"
enabled_case="$workdir/ulvz_enabled"
results_log="$testdir/results.log"

mkdir -p "$report_dir"

echo >> "$results_log"
echo "test: s40rts_ulvz_mesh" >> "$results_log"
echo "workdir: $workdir" >> "$results_log"
echo "MPIEXEC: $MPIEXEC" >> "$results_log"
echo "MPI_NPROC_FLAG: $MPI_NPROC_FLAG" >> "$results_log"
echo "NPROC: $NPROC" >> "$results_log"
echo "OMP_NUM_THREADS: $OMP_NUM_THREADS" >> "$results_log"
echo "SPECFEM_VERSION: $specfem_version" >> "$results_log"

if [ -f Makefile ]; then
  make -f test_models.makefile "$var" >> "$results_log" 2>&1
  inspector="$testdir/bin/$var"
else
  make -C "$ROOT" -f tests/meshfem3D/test_models.makefile \
    TEST_SRCDIR=tests/meshfem3D "$var" >> "$results_log" 2>&1
  inspector="$root_abs/bin/$var"
fi

xmesh="$root_abs/bin/xmeshfem3D"
if [ ! -x "$xmesh" ]; then
  echo "missing executable: $xmesh" >&2
  exit 1
fi
if [ ! -x "$inspector" ]; then
  echo "missing executable: $inspector" >&2
  exit 1
fi

run_mpi_mesher() {
  case_dir=$1
  log_file=$2
  (
    cd "$case_dir"
    if [ -n "$MPI_NPROC_FLAG" ]; then
      "$MPIEXEC" "$MPI_NPROC_FLAG" "$NPROC" "$xmesh"
    else
      "$MPIEXEC" "$xmesh"
    fi
  ) >> "$log_file" 2>&1
}

write_ulvz_file() {
  outfile=$1
  enabled=$2
  cat > "$outfile" <<EOF
ENABLED = $enabled
CENTER_LATITUDE_DEGREES = 45.0
CENTER_LONGITUDE_DEGREES = 140.0
THICKNESS_KM = 80.0
LATERAL_RADIUS_KM = 400.0
LATERAL_TAPER_KM = 100.0
TOP_TAPER_KM = 20.0
DVS = -0.20
DVP = -0.10
DRHO = 0.05
EOF
}

stage_case() {
  case_dir=$1
  enabled=$2
  mkdir -p "$case_dir/DATA" "$case_dir/OUTPUT_FILES" "$case_dir/DATABASES_MPI"
  cp "$fixture_dir/DATA/Par_file" "$case_dir/DATA/Par_file"
  write_ulvz_file "$case_dir/DATA/ulvz_s40rts.par" "$enabled"

  for dep in s40rts s20rts crust2.0; do
    if [ ! -d "$root_abs/DATA/$dep" ]; then
      echo "missing required DATA dependency: DATA/$dep" >&2
      exit 1
    fi
    ln -s "$root_abs/DATA/$dep" "$case_dir/DATA/$dep"
  done
}

write_manifest() {
  case_dir=$1
  manifest=$2
  {
    echo "case_dir=$case_dir"
    echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "mpi_command=$MPIEXEC $MPI_NPROC_FLAG $NPROC $xmesh"
    echo "omp_num_threads=$OMP_NUM_THREADS"
    echo "specfem_version=$specfem_version"
    echo "fixture=$fixture_dir/DATA/Par_file"
    if git -C "$root_abs" rev-parse HEAD >/dev/null 2>&1; then
      echo "git_commit=$(git -C "$root_abs" rev-parse HEAD)"
    else
      echo "git_commit=unknown"
    fi
    echo "data_dependencies=DATA/s40rts DATA/s20rts DATA/crust2.0"
    echo "checksums:"
    sha256sum "$case_dir/DATA/Par_file"
    sha256sum "$case_dir/DATA/ulvz_s40rts.par"
    sha256sum "$case_dir/DATA/s40rts/S40RTS.dat"
    sha256sum "$case_dir/DATA/s20rts/P12.dat"
    sha256sum "$case_dir/DATA/crust2.0/CNtype2.txt"
    sha256sum "$case_dir/DATA/crust2.0/CNtype2_key_modif.txt"
    sha256sum "$case_dir/DATA/crust2.0/CNelevatio2.txt"
  } > "$manifest"
}

stage_case "$disabled_case" ".false."
stage_case "$enabled_case" ".true."

cmp -s "$disabled_case/DATA/Par_file" "$enabled_case/DATA/Par_file"
write_manifest "$disabled_case" "$disabled_case/manifest.txt"
write_manifest "$enabled_case" "$enabled_case/manifest.txt"

run_mpi_mesher "$disabled_case" "$disabled_case/xmeshfem3D.log"
"$inspector" --preflight "$disabled_case" "$report_dir" >> "$results_log" 2>&1

run_mpi_mesher "$enabled_case" "$enabled_case/xmeshfem3D.log"
export ULVZ_MESH_VIZ_MPI_COMMAND="$MPIEXEC $MPI_NPROC_FLAG $NPROC $xmesh"
export ULVZ_MESH_VIZ_SPECFEM_VERSION="$specfem_version"
export ULVZ_MESH_VIZ_OMP_NUM_THREADS="$OMP_NUM_THREADS"
if git -C "$root_abs" rev-parse HEAD >/dev/null 2>&1; then
  export ULVZ_MESH_VIZ_GIT_COMMIT
  ULVZ_MESH_VIZ_GIT_COMMIT=$(git -C "$root_abs" rev-parse HEAD)
else
  export ULVZ_MESH_VIZ_GIT_COMMIT=unknown
fi
export ULVZ_MESH_VIZ_CREATED_UTC
ULVZ_MESH_VIZ_CREATED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$inspector" --compare "$disabled_case" "$enabled_case" "$report_dir" >> "$results_log" 2>&1

if [ "$EXPORT_MESH_VIZ_DATA" = "1" ]; then
  if [ ! -f "$report_dir/mesh_gll_points.csv" ]; then
    echo "missing expected visualization export: $report_dir/mesh_gll_points.csv" >&2
    exit 1
  fi
  gzip -n -f "$report_dir/mesh_gll_points.csv"
fi

if [ "$EXPORT_PARAVIEW_MESH_DATA" = "1" ]; then
  if [ ! -f "$report_dir/paraview_mesh_metadata.json" ]; then
    echo "missing expected ParaView mesh metadata: $report_dir/paraview_mesh_metadata.json" >&2
    exit 1
  fi
  for rank in 000000 000001; do
    if [ ! -f "$report_dir/paraview_mesh_nodes_rank${rank}.csv" ]; then
      echo "missing expected ParaView mesh nodes: $report_dir/paraview_mesh_nodes_rank${rank}.csv" >&2
      exit 1
    fi
    if [ ! -f "$report_dir/paraview_mesh_cells_rank${rank}.csv" ]; then
      echo "missing expected ParaView mesh cells: $report_dir/paraview_mesh_cells_rank${rank}.csv" >&2
      exit 1
    fi
    gzip -n -f "$report_dir/paraview_mesh_nodes_rank${rank}.csv"
    gzip -n -f "$report_dir/paraview_mesh_cells_rank${rank}.csv"
  done
fi

elapsed_seconds=$((SECONDS - start_seconds))
artifact_kib=$(du -sk "$workdir" | awk '{print $1}')

{
  echo
  echo "Harness metadata"
  cat "$disabled_case/manifest.txt"
  echo
  cat "$enabled_case/manifest.txt"
} >> "$report_dir/comparison_summary.txt"

{
  echo "metadata,mpi_command,all,$MPIEXEC $MPI_NPROC_FLAG $NPROC $xmesh"
  echo "metadata,omp_num_threads,all,$OMP_NUM_THREADS"
  echo "metadata,specfem_version,all,$specfem_version"
  echo "metadata,elapsed_seconds,all,$elapsed_seconds"
  echo "metadata,artifact_kib,all,$artifact_kib"
  echo "metadata,data_dependencies,all,DATA/s40rts DATA/s20rts DATA/crust2.0"
} >> "$report_dir/comparison_summary.csv"

{
  echo
  echo "Run summary"
  echo "specfem_version=$specfem_version"
  echo "elapsed_seconds=$elapsed_seconds"
  echo "artifact_kib=$artifact_kib"
} >> "$report_dir/comparison_summary.txt"

echo "Task 3D S40RTS ULVZ mesh test passed"
echo "workdir: $workdir"
echo "successfully tested: $(date)" >> "$results_log"
