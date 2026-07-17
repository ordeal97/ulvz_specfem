# Two-chunk build recovery and resumed acceptance — 2026-07-15

## Build recovery result

The requested `obj/binary_c_io.cc.o` is a historical object-name convention,
not a request for a C++ source file.  `src/shared/rules.mk` declares the
explicit pattern rule `$O/%.cc.o: $S/%.c ${SETUP}/config.h`, which invokes
`${CC}` on `src/shared/binary_c_io.c`.  A current-formal-tree dry run and the
fresh optimized build both resolve this prerequisite to the C source and run
`/usr/bin/mpicc`.

The preceding build copy was incomplete: it included `DATA/Par_file` but
omitted `DATA/CMTSOLUTION` and `DATA/STATIONS`.  `config.status` requires all
three inputs before it can generate `setup/config.h`; without that generated
prerequisite, make reported the misleading no-rule error for
`obj/binary_c_io.cc.o`.  This is an acceptance-harness input-copy defect,
pre-existing relative to the two-chunk edit.  No production build rule was
changed.

`results/two_chunk_build_recovery_20260715T153002Z/` preserves the dependency
trace, source/input manifests, configure gates, fresh-object evidence, build
logs, and resumed debug mesh/assembly evidence.

## Fresh build evidence

Both independent, no-prior-object copies passed `configure` and `config.status`
and produced `bin/xmeshfem3D` and `bin/xspecfem3D`.  In each build,
`create_chunk_buffers.f90` was compiled to `obj/create_chunk_buffers.check.o`
and included in the mesher link.  The optimized C object is an ELF relocatable
object compiled from `src/shared/binary_c_io.c`; it is not a C++ source
artifact.  The debug build enables bounds checking, initialized sentinels,
invalid/zero/overflow FPE traps, and backtraces.  The exact command also shows
that this project's make flags append `-O3` after requested `-O0`; the safety
checks remain present and this is recorded rather than being presented as a
strictly unoptimized binary.

## Resumed acceptance status

Fresh debug 2-rank and 8-rank two-chunk meshing completed.  The 8-rank parser
found 24 rank-region databases, 96 directed interface records, zero reciprocal
or buffered-coordinate errors, and endpoint four-owner set `{0,2,5,7}` with
all six direct pairs.  A result-directory-only program linked against the
fresh production `assemble_MPI_scalar` and `assemble_MPI_vector` objects; on
the four owners with contributions `1,2,4,8`, scalar, vector, non-owner, and
reset/repeated-assembly checks passed with sum 15.

A fresh debug non-square 1x2/chunk mesh/database run also completed: its
parser found 12 rank-region files, 36 directed entries, and zero reciprocal,
duplicate, or bad-coordinate issues.  This is mesh communication evidence;
the required non-square solver waveform comparison is still outstanding.

The debug 2-rank fixture also completed a 300-step short solver run with no
bounds, initialized-sentinel, or FPE-trap failure.  Its deliberately coarse
fixture reports source/receiver location errors, so it is a communication and
runtime smoke test rather than locator or physical-waveform acceptance.

This does not yet constitute A acceptance.  The formal optimized waveform,
endpoint illumination, non-square solver, decomposition-invariance, full
Stacey identity mapping, and one-/six-chunk regressions remain to be completed.
Their absence is an evidence gap (B), not evidence of a two-chunk defect.
