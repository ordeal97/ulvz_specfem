#!/usr/bin/env bash
# Read-only pre-application verification for the project-local two-chunk patch.
set -euo pipefail

patch_dir=$(cd "$(dirname "$0")" && pwd)
patch_file="$patch_dir/specfem3d_globe_two_chunk_endpoints.patch"
source_dir=${1:-"$patch_dir/../../../specfem3d_globe"}
target_file="src/meshfem3D/create_chunk_buffers.f90"
expected_base_sha256="fd4137713e55e14ec664a9d55487b64c2b9bf73499c1f82780f1f5a6e63b088f"
expected_candidate_sha256="8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857"

if [[ ! -d "$source_dir/.git" || ! -f "$source_dir/$target_file" ]]; then
  printf 'error: provide a SPECFEM3D_GLOBE Git worktree containing %s\n' "$target_file" >&2
  exit 2
fi

actual_sha256=$(sha256sum "$source_dir/$target_file" | awk '{print $1}')
if [[ "$actual_sha256" != "$expected_base_sha256" ]]; then
  printf 'error: target SHA-256 mismatch\nexpected base: %s\nactual:        %s\n' \
    "$expected_base_sha256" "$actual_sha256" >&2
  printf 'stop: do not apply this project-local patch to unmatched source context\n' >&2
  exit 3
fi

mapfile -t changed_files < <(awk '/^\+\+\+ b\// {print substr($0, 7)}' "$patch_file")
if [[ ${#changed_files[@]} -ne 1 || "${changed_files[0]}" != "$target_file" ]]; then
  printf 'error: patch does not modify exactly %s\n' "$target_file" >&2
  exit 4
fi

if grep -Eq '^[+-][^+-].*DEBUG' "$patch_file"; then
  printf 'error: patch contains a DEBUG change\n' >&2
  exit 5
fi

git -C "$source_dir" apply --check "$patch_file"
printf 'pass: target hash, single-file scope, no DEBUG change, and git apply --check verified\n'
printf 'candidate SHA-256 after manual apply must be: %s\n' "$expected_candidate_sha256"
