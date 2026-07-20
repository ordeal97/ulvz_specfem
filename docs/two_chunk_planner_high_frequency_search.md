# two_chunk_planner Event 1 high-frequency search performance record

Status: **end-to-end correctness and reproducibility accepted; the 10-minute
performance target was not met.**

The real Event 1 input has 127 stations and requests S and Sdiff with partial
coverage. TauP supplied 127 S paths (66,650 total points) and reported 127
unavailable Sdiff pairs. NEX=448 affects resource suggestions only; it does
not change orientation candidates or path-point count.

The original scalar path-boundary core measured 2.487 s per orientation. The
first NumPy path batch measured 0.0970 s per orientation. The current
eight-orientation implementation keeps path vectors fixed, rotates the fixed
chunk boundary geometry into global coordinates, evaluates all path points,
and computes finite-arc distances only for points already proved inside the
two-chunk domain. On the real path data it measured 0.00280--0.00285 s per
orientation (about 23.7 million point-orientations/s; peak RSS about 112 MiB).

For exact ranking, the batch evaluator recomputes the single global minimum
path-boundary point per orientation through the legacy scalar six-arc routine.
Source/station checks are scalar. Thus a batch candidate with no numerical
guard has the same score used by the scalar reference; candidates at a
predicate guard, cutoff interval, or final stage keeper retain scalar review.
Full `GeometryCandidate` audits and serialized JSON remain scalar for returned
candidates.

`20 passed` package tests cover the legacy reference search, ordered
candidates, stage keepers, final audits, and a multi-orientation batch/scalar
comparison. A real checkpoint processed 480 coarse candidates with zero scalar
fallbacks, 5.274 s cumulative path-batch time, and no numerical-guard
candidates.

## Third-round persistent acceptance

The authoritative result directory is
`results/two_chunk_planner_high_frequency_search_20260720T111204Z_third_round/`.
It contains two independent complete planner outputs, their stdout/stderr,
`/usr/bin/time -v` records, collector comparison and final test evidence.

| Run | Exit | Wall time | User | System | Maximum RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| persistent run 1 | 0 | 12:31.62 | 747.98 s | 2.47 s | 264,464 KiB |
| persistent run 2 | 0 | 12:28.80 | 745.31 s | 2.20 s | 267,248 KiB |

The collector reported `end_to_end_acceptance_completed`; the two output trees
were recursively and strictly equal, including geometry, score, coverage,
warnings, phase/station results and resource suggestions. The final package
pytest result was `20 passed in 11.10s`.

The prior optimized persistent runs were approximately 18.5 minutes, so the
third round reduced wall time by about 32%. The original scalar snapshot did
not complete within 1800 s; that evidence supports only an old/new speedup
lower bound, not an exact speedup. Both new runs exceed 10 minutes, so the
10-minute target remains unmet.

The previous diagnostic attributed 719.94 s to batch path evaluation and
352.17 s to 60 keeper scalar reviews, with about 203 s unclassified. The
third-round formal measurements intentionally ran without detailed profiling;
therefore their remaining time is not retrospectively assigned to a guessed
hotspot. The keeper change retains full scalar review when the conservative
batch guard requires it and otherwise uses only an already scalar-exact compact
result. It preserves the deterministic candidate set, scoring, ordering,
tie-breaking and final audit semantics.

## Scope of these artifacts

`summary.json`, `performance_matrix.csv`, profile summaries, persistent shell
logs and comparison JSON in this result directory are **performance acceptance
artifacts**. They are not files created by ordinary `two-chunk-planner plan`.
The normal planner output set is documented in the package user guides.
