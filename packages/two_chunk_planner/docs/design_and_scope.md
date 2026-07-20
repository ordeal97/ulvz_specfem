# Design and scope

## Operational authority

The current Python implementation and its successful package-local tests are
the operational authority for this guide. The planner is deliberately **not**
a patch verifier: it bundles accepted-patch provenance as a reference, but
never reads an external manifest, SPECFEM source tree, or source hash. Patch
installation and verification belong to the separate patch package and
regional guide.

## Supported geometry

Only `NCHUNKS=2`, `ANGULAR_WIDTH_XI_IN_DEGREES=90`,
`ANGULAR_WIDTH_ETA_IN_DEGREES=90`, AB central plus AC supported-left, and one
system-wide center/`GAMMA_ROTATION_AZIMUTH` are represented. The planner uses
cubed-sphere Cartesian transforms, not a latitude/longitude rectangle.

`canonical_90deg_fixture_ready=true` and
`general_two_chunk_mode_classification=B`. Non-90-degree or rectangular
chunks, other attachment sides, nonadjacent chunks, independent orientations,
arbitrary two-chunk topology, and three-/multi-chunk configurations are not
exposed by this package.

## Read-only boundary

The tool parses inputs, creates a new planner output directory, and writes
reports there. It does not modify a source `Par_file`, SPECFEM source, build
rules, the accepted patch, or any mesh/database/solver input. Users must run
all downstream mesh, Stacey, decomposition, waveform, and external-return
validation separately.

## Runtime implementation boundary

The public interface is the `plan` CLI documented in the two CLI references.
The internal Python `SearchDiagnostics` and orientation-batch hooks exist only
for test/performance diagnostics and are not CLI options. During a run, TauP
paths are prepared once before the deterministic coarse/local/final search;
continuous NumPy vectors and blocked orientation batches accelerate path
coverage. Compact search evaluations retain only the fields required for
feasibility and ranking, while conservative scalar checks and the final full
`GeometryCandidate` audit preserve the user-visible score, ordering, warnings
and JSON semantics. No runtime cache is written to disk or reused by a later
CLI invocation.
