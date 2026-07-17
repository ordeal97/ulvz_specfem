# Design and scope

## Operational authority

The current Python implementation and its successful package-local tests are
the operational authority for this guide. The planner reads the project-local
patch manifest and checks the SHA-256 of
`src/meshfem3D/create_chunk_buffers.f90`; it requires the manifest's formal
candidate hash `8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857`.
It does not apply or alter that patch.

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
