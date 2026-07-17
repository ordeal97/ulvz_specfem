# Project-local accepted patch for two 90-degree chunks

This document packages the accepted `create_chunk_buffers.f90` correction for
the current ULVZ project only. It is not an upstream SPECFEM3D_GLOBE proposal.
No build rule is modified by this package.

The package is deliberately stored at
`patches/specfem3d_globe/two_chunk_endpoints/`, outside
`packages/ulvz_model_postprocess/`: it changes forward-mesher corner assembly,
not the post-processing implementation.

## What it fixes

The historical `NCHUNKS=2` path assembled only the eta-max endpoint as a
three-member corner. It omitted C1 at eta-min and retained a BC/rank-zero
third member that is not part of a two-face domain. The accepted patch creates
two two-member messages: C1 at eta-min and C2 at eta-max. It also uses
`NPROC_ETA` for the xi-constant AB--AC interface, protects unused members with
`INVALID_RANK`, bounds corner processing by two members, and permits the two
valid endpoint records per slice.

## Provenance gate

The patch applies only when the target source is exactly the nested HEAD
baseline `9c312cb2c991b47484a7f302775f4f01ed9470f8` context and
`src/meshfem3D/create_chunk_buffers.f90` hashes to:

```text
fd4137713e55e14ec664a9d55487b64c2b9bf73499c1f82780f1f5a6e63b088f
```

After apply, it must hash to:

```text
8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857
```

The isolated runtime source hashes to
`c533c710b213fddd2816b53dee46ef48dcc59992cdb0909b614f8e2a8a91bc31`;
its only difference from the formal candidate is diagnostic `DEBUG=.true.`.
It has no branch, loop-bound, rank-map, buffer, counter, or MPI-cardinality
difference.

Stop when either hash or `git apply --check` differs. Updating
SPECFEM3D_GLOBE requires fresh source-context review and targeted validation.

## Apply, verify, reverse

```bash
PATCH=patches/specfem3d_globe/two_chunk_endpoints/specfem3d_globe_two_chunk_endpoints.patch
patches/specfem3d_globe/two_chunk_endpoints/verify_patch.sh specfem3d_globe
git -C specfem3d_globe apply --check "$PATCH"
git -C specfem3d_globe apply "$PATCH"
sha256sum specfem3d_globe/src/meshfem3D/create_chunk_buffers.f90
git -C specfem3d_globe apply --reverse --check "$PATCH"
git -C specfem3d_globe apply --reverse "$PATCH"
```

Rebuild from clean objects after either source transition. The package neither
provides nor changes build rules.

## Validated scope and limitations

Validated mode: `NCHUNKS=2`, two adjacent 90-degree cubed-sphere chunks, the
first chunk central, the second on the supported left side, positioning via
central coordinates and `GAMMA_ROTATION_AZIMUTH`, with 2-, 8-, and 12-rank
fixtures. `canonical_90deg_fixture_ready=true`; the general classification
remains `B`.

Not established: non-90-degree chunks, unequal widths, other attachment sides,
nonadjacent chunks, independent orientations, arbitrary two-chunk topology,
three-chunk, or general multi-chunk configurations.

## Acceptance evidence

The historical C1 omission/C2 three-member reproduction and patched reciprocal
topology are in
`results/two_chunk_causal_waveform_acceptance_20260716T124432Z/07_topology_analysis/`.
Face-role Stacey acceptance is in `docs/two_chunk_corner_topology_acceptance.md`.
The v3 2/8/12 waveform maximum NRMS `2.92e-6`, maximum relative energy
difference `2.86e-6`, no shifting/NaN/endpoint anomaly, and fresh one-/six-
chunk passes are indexed by
`results/two_chunk_waveform_symmetry_closure_20260716T144230Z/07_reports/acceptance_matrix.json`.
The earlier v2 `[0,25] s` window ended before the approximately 52 s first
physical arrival; its failure is documented in
`results/two_chunk_waveform_symmetry_closure_20260716T144230Z/01_v2_audit/v2_diagnostic_breakdown.json`.
