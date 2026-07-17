# Canonical 90-degree two-chunk teaching case

This is a project teaching case, not a Kim/Song Hawaiʻi input set and not a
production-resolution recommendation. It uses the accepted geometry:
\`NCHUNKS=2\`, two adjacent 90-degree chunks, chunk 1 central, chunk 2 on the
supported left side, \`NEX_XI=NEX_ETA=96\`, and \`NPROC_XI=NPROC_ETA=2\`. The
total MPI rank count is therefore \(2 * 2 * 2 = 8\).

The mesh/decomposition and accepted patch scope are validated. The mixed
teaching station list is new: it demonstrates points in both chunks but does
not claim a separately accepted production waveform result.

## Before any run

1. Apply and verify the accepted project-local patch as documented in
   [\`../../docs/two_chunk_project_patch.md\`](../../docs/two_chunk_project_patch.md).
2. Use the project Python and run the read-only input/geometry audit:

   \`\`\`bash
   ${ULVZ_PYTHON:-python3} \
     cases/two_chunk_canonical_90deg/audit_geometry.py --validate-only \
     --specfem-root specfem3d_globe
   \`\`\`

3. Write fresh audit reports outside the input directory:

   \`\`\`bash
   ${ULVZ_PYTHON:-python3} \
     cases/two_chunk_canonical_90deg/audit_geometry.py \
     --output-dir results/two_chunk_geometry_audit_<UTC>
   \`\`\`

\`audit_geometry.py\` reads only \`DATA/Par_file\`, \`DATA/CMTSOLUTION\`, and
\`DATA/STATIONS\`. It reports chunk membership plus angular margins to the
shared interface, C1/C2, and external boundaries. These are geometry
quantities, not fixed safety distances; assess a science window using
travel-time estimates and the earliest external-boundary return.

## Run deliberately

The runner refuses an existing run directory, checks the formal candidate
source hash from the patch manifest, copies the three inputs into the new run,
then uses the current executable names:

\`\`\`bash
bash cases/two_chunk_canonical_90deg/run_canonical.sh \
  --specfem-root specfem3d_globe \
  --run-dir results/two_chunk_canonical_run_<UTC> --dry-run
\`\`\`

Remove \`--dry-run\` only after reviewing the command and providing a newly
named result directory. It runs \`mpirun -np 8 bin/xmeshfem3D\` followed by
\`mpirun -np 8 bin/xspecfem3D\`; it never patches, cleans, resets, or overwrites
the SPECFEM tree.

See the bilingual guide index:
[\`../../docs/two_chunk_regional_simulations_guide.md\`](../../docs/two_chunk_regional_simulations_guide.md).
