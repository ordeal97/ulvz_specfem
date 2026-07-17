# Project-local SPECFEM patch: two chunk endpoints

This directory contains a project-local patch for the ULVZ workflow. It is
not an upstream SPECFEM3D_GLOBE submission and establishes no general
two-chunk support.

## Safe workflow

From a clean-or-dirty SPECFEM worktree whose target file has the documented
baseline SHA-256, run the read-only check first:

```bash
patches/specfem3d_globe/two_chunk_endpoints/verify_patch.sh specfem3d_globe
```

Only after that command succeeds, apply and verify the patch manually:

```bash
git -C specfem3d_globe apply \
  patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch
sha256sum specfem3d_globe/src/meshfem3D/create_chunk_buffers.f90
git -C specfem3d_globe apply --reverse --check \
  patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch
```

The applied file must hash to
`8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857`.
To reverse it after a successful application:

```bash
git -C specfem3d_globe apply --reverse \
  patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch
```

Rebuild SPECFEM from clean objects using the project build procedure after
applying or reversing the patch. The verification script never applies,
reverses, resets, deletes, or overwrites source files.

Use only the documented canonical configuration: two adjacent 90-degree
chunks, central chunk first, supported left-side attachment, central
coordinates plus `GAMMA_ROTATION_AZIMUTH`, and the validated 2-, 8-, or
12-rank decompositions. See `docs/two_chunk_project_patch.md`.
