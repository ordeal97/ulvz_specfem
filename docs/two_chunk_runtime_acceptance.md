# Two-chunk formal runtime acceptance continuation — 2026-07-16

Runtime evidence is stored in
`results/two_chunk_runtime_acceptance_20260716T085151Z/`.

Fresh optimized 1x1/chunk (2-rank), 2x2/chunk (8-rank), and non-square
1x2/chunk (4-rank) runs completed. Physical fingerprints match. The formal
2-rank/8-rank full-record NRMS is `1.29e-6`–`3.43e-6` and energy difference is
`5.40e-7`–`1.13e-6`, matching the isolated approximately `1e-6` baseline.
Non-square NRMS is `0.88e-6`–`3.22e-6`.

Independent eta-min and eta-max fixtures used actual Euler-rotated geometry,
buried shallow/mid/CMB-near probes, and 6.5-minute records. Both endpoint
2-rank/8-rank pairs completed; all 36 component traces per endpoint pass the
strict comparison and each depth class has nine valid traces.

Fresh one- and six-chunk mesh/database/solver runs completed. Six-chunk
waveforms exactly reproduce the preserved isolated baseline. The preserved
one-chunk directory has no waveform baseline, so its comparison is partial.

Sequential Stacey data was parsed through `ispec/ijk -> ibool`. No absorbing
AB--AC face is found. Raw node intersections occur where external lateral
absorbing faces meet the MPI interface at physical endpoint edges. A face-only
classifier is required before asserting the requested node-zero condition;
classification therefore remains **B**, with `implementation_ready=false`.
