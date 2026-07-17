# Two-chunk formal integration acceptance — 2026-07-15

## Result

Classification: **B**. The production source patch is present but uncommitted.
It is not a production/Hawai'i ULVZ readiness claim.

The exact patch in
`results/two_chunk_integration_acceptance_20260715T145928Z/01_patch/`
applied cleanly to `specfem3d_globe/src/meshfem3D/create_chunk_buffers.f90`.
There was no fuzz, offset, or manual merge; the resulting source SHA256 is
identical to the isolated final source.

## What was established

- The formal tree was protected with pre-application status, tracked/staged
  diffs, untracked inventory, target-file backup, and SHA256 records.
- The only intended production edit is `create_chunk_buffers.f90`.
- Re-parsing the preserved, source-identical isolated 2x2 database finds 24
  rank-region files, 96 reciprocal interface records, no reciprocal issues,
  no duplicate nodes within a directed interface, and no buffered coordinate
  without both pair owners.
- The expected direct pairs for four-owner set `{0,2,5,7}` remain all six:
  `0-2`, `0-5`, `0-7`, `2-5`, `2-7`, and `5-7`.
- The preserved production scalar/vector assembly test used contributions
  `1,2,4,8` and obtained 15. It is inherited evidence only, not a fresh
  formal-build result.

## Blocking evidence

The fresh optimized build copy was created from the formal HEAD content plus
the exact formal patch, with old `obj/`, `bin/`, databases, and outputs
excluded. `configure` completed, but `make xmeshfem3D` stopped before the
patched mesher object was compiled:

```text
make: *** No rule to make target 'obj/binary_c_io.cc.o', needed by 'bin/xmeshfem3D'.  Stop.
```

The source tree has `src/shared/binary_c_io.c`; no unrelated build-rule or
source workaround was made. Consequently there is no fresh formal mesher or
solver executable, and the following A gates remain unexecuted: debug build,
formal topology/endpoint mesh reconstruction, Stacey identity mapping,
endpoint multi-depth illumination, non-square solver, strict 2-rank/8-rank
comparison, and one-/six-chunk regression.

## Artifacts

The authoritative machine-readable result is
`results/two_chunk_integration_acceptance_20260715T145928Z/11_reports/summary.json`.
It links companion topology, assembly, Stacey, waveform, fingerprint,
manifest, checksum, build, and patch records in the same timestamped tree.

No commit or push was performed. The patch remains in the formal worktree;
it was not restored because no patch-caused topology, assembly, runtime, or
regression failure was observed.

## Build recovery and resumed acceptance — 20260715T153002Z

The earlier build failure is retained above as historical evidence.  New
evidence in `results/two_chunk_build_recovery_20260715T153002Z/` establishes
that its cause was an incomplete acceptance build-copy input set:
`config.status` needs `DATA/Par_file`, `DATA/CMTSOLUTION`, and `DATA/STATIONS`
to generate `setup/config.h`.  The source rule correctly maps the historical
object name `obj/binary_c_io.cc.o` to `src/shared/binary_c_io.c` and compiles it
with `CC`; no production build-rule patch was needed.

Fresh optimized and debug mesher/solver builds now succeed.  Fresh debug
two-chunk 2-rank/8-rank database evidence verifies reciprocal interfaces and
the `{0,2,5,7}` four-owner endpoint set with all six direct pairs.  A fresh
production-object MPI scalar/vector assembly test also passes the `1+2+4+8=15`
and repeated-call checks.  This supplements, but does not replace, the old
blocked acceptance.  The classification remains **B** pending the still
unrun optimized waveform, endpoint, non-square, full Stacey, decomposition,
and one-/six-chunk evidence.

## Formal runtime acceptance continuation — 20260716T085151Z

`results/two_chunk_runtime_acceptance_20260716T085151Z/` supplies fresh formal
optimized 2-rank, 8-rank, and non-square solver evidence. The physical mesh
fingerprints match; formal 2-rank/8-rank NRMS is `1.29e-6`–`3.43e-6`, energy
difference is `5.40e-7`–`1.13e-6`, and strict decomposition invariance passes.
Independent eta-min/eta-max buried endpoint fixtures pass across shallow, mid,
and CMB-near probe groups. Fresh one-/six-chunk solvers complete, with
six-chunk matching the preserved waveform baseline exactly.

Stacey records were parsed through `ispec/ijk -> ibool`. No absorbing AB--AC
face was found, but raw endpoint node intersections remain at external lateral
absorbing edges shared with the MPI interface. The requested node-zero gate is
therefore inconclusive pending a face-only classifier. This is not evidence of
a two-chunk communication failure, and classification remains **B**.
# Corner-topology continuation — 2026-07-16

新增 face-role-aware corner classifier 和新建 12-rank 2×3/chunk canonical mesh evidence 见 [two_chunk_corner_topology_acceptance.md](two_chunk_corner_topology_acceptance.md)。该结果确认 patched canonical database 的 C1/C2 三径向组 reciprocal buffers，并确认端点与外侧 Stacey face 的原始 node overlap 是 face-role 区分后的合法 external-edge coincidence。它没有覆盖既有正式 runtime 报告，也没有将 B 提升为 A：clean/current-reversed controlled runtime 和 C1/C2 对称波形仍未完成。
