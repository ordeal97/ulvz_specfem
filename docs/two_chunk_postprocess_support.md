# Canonical two-chunk post-processing support

## Result

The existing `ulvz_model_postprocess` implementation has now been validated
for the accepted canonical two-chunk database layout.  This is evidence for
post-processing only; it neither changes the solver nor expands the accepted
two-chunk topology beyond classification **B**.

The validation used C1 and C2 canonical 90-degree meshes at 2, 8, and 12 MPI
ranks from
`results/two_chunk_waveform_symmetry_closure_20260716T144230Z/`.  All six
complete `DATABASES_MPI` directories passed raw-layout inspection, `reg1`
physical-field extraction, rank-store array validation, `vp` static plotting,
and linear-mesh ParaView export.

The result root is
`results/two_chunk_postprocess_support_20260716T162353Z/`; the machine-readable
decision is in `07_reports/acceptance_matrix.json`.

## What was checked

- Each raw database contained every expected `(rank, region)` tuple for
  regions 1, 2, and 3.
- The extracted `reg1` products had exactly 2, 8, or 12 unique rank stores,
  respectively.  Coordinate arrays, `ibool`, and `rho`/`vp`/`vs` had expected
  dimensions and contained no NaN or Inf values.
- Each linear-mesh ParaView product had one valid VTK piece per rank and a
  valid `.pvtu` wrapper: 2, 8, and 12 pieces for the corresponding fixtures.
- C1 and C2 2-rank self-comparisons both produced exact ratio-one and
  difference-zero fields.  This demonstrates that the comparison command can
  consume a two-chunk rank-store.

## Scope and limitations

Supported here means the package can read and produce rank-local outputs for
the documented canonical two-chunk layout at the validated 2/8/12-rank
fixtures.  The products intentionally retain one piece per MPI rank.  This
does **not** validate or claim global cross-rank/cross-chunk welding or
deduplication.

`compare` requires matching rank inventories.  A deliberate C1 2-rank versus
C1 8-rank invocation was rejected with that documented condition; it is not a
two-chunk extraction failure.

Unverified: non-90-degree widths, unequal chunk widths, other attachment
sides, nonadjacent chunks, independent orientations, arbitrary two-chunk
topologies, and three- or multi-chunk meshes.

## Patch-package location

The two-chunk solver correction is not a post-processing extension.  Its
standalone project-local package is now at
`patches/specfem3d_globe/two_chunk_endpoints/`.  The patch remains byte
identical to the accepted semantic diff and was again verified by clean apply
and reverse dry-run against the documented current source context.  See
`docs/two_chunk_project_patch.md` for application instructions.
