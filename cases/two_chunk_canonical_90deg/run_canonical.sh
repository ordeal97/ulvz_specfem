#!/usr/bin/env bash
# Run only on an explicitly new directory; this script never cleans or patches SPECFEM.
set -euo pipefail

CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${ULVZ_PYTHON:-python3}"
SPECFEM_ROOT=""
RUN_DIR=""
DRY_RUN=false

usage() {
  echo "Usage: $0 --specfem-root PATH --run-dir NEW_PATH [--dry-run]" >&2
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --specfem-root) SPECFEM_ROOT="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done
[[ -n "$SPECFEM_ROOT" && -n "$RUN_DIR" ]] || { usage; exit 2; }
[[ -x "$PYTHON" ]] || { echo "required project Python not found: $PYTHON" >&2; exit 2; }
[[ -d "$SPECFEM_ROOT" ]] || { echo "invalid SPECFEM root: $SPECFEM_ROOT" >&2; exit 2; }
SPECFEM_ROOT="$(cd "$SPECFEM_ROOT" && pwd)"
if [[ ! -x "$SPECFEM_ROOT/bin/xmeshfem3D" || ! -x "$SPECFEM_ROOT/bin/xspecfem3D" ]]; then
  if ! "$DRY_RUN"; then
    echo "SPECFEM root must contain built bin/xmeshfem3D and bin/xspecfem3D" >&2; exit 2
  fi
  echo "note: dry-run only; built xmeshfem3D/xspecfem3D are not both present" >&2
fi
[[ ! -e "$RUN_DIR" ]] || { echo "refusing to overwrite existing run directory: $RUN_DIR" >&2; exit 2; }

"$PYTHON" "$CASE_DIR/audit_geometry.py" --validate-only --specfem-root "$SPECFEM_ROOT"
COMMANDS=(
  "mkdir -p '$RUN_DIR/DATA' '$RUN_DIR/DATABASES_MPI' '$RUN_DIR/OUTPUT_FILES'"
  "cp -R '$CASE_DIR/DATA/.' '$RUN_DIR/DATA/'"
  "cd '$RUN_DIR' && mpirun -np 8 '$SPECFEM_ROOT/bin/xmeshfem3D'"
  "cd '$RUN_DIR' && mpirun -np 8 '$SPECFEM_ROOT/bin/xspecfem3D'"
)
if "$DRY_RUN"; then
  printf 'would run: %s\n' "${COMMANDS[@]}"
  exit 0
fi
mkdir -p "$RUN_DIR/DATA" "$RUN_DIR/DATABASES_MPI" "$RUN_DIR/OUTPUT_FILES"
cp -R "$CASE_DIR/DATA/." "$RUN_DIR/DATA/"
{
  printf 'date_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'mpi_command=mpirun -np 8\n'
  printf 'specfem_root=%s\n' "$SPECFEM_ROOT"
  git -C "$SPECFEM_ROOT" rev-parse HEAD 2>/dev/null || true
  sha256sum "$SPECFEM_ROOT/src/meshfem3D/create_chunk_buffers.f90"
} > "$RUN_DIR/run_provenance.txt"
(cd "$RUN_DIR" && mpirun -np 8 "$SPECFEM_ROOT/bin/xmeshfem3D")
(cd "$RUN_DIR" && mpirun -np 8 "$SPECFEM_ROOT/bin/xspecfem3D")
