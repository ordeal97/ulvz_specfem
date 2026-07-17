# Hawai'i 135° one-chunk boundary-contamination validation

## Conclusion

The 135°×135° one-chunk candidate remains **B**.  It completed a full
matched-resolution comparison with a native 6-chunk global reference and no
science-station residual growth attributable to a lateral boundary was
demonstrated during the constructed Pdiff/Sdiff/postcursor window.  However,
the 120° domain-size test changes the Sdiff comparison while also changing
local grid sampling and mesh alignment.  The boundary probes show
one-minus-global differences already at outgoing arrivals, not a separately
identifiable reflected arrival.  Therefore this evidence does not uniquely
isolate lateral-boundary causation and is insufficient to promote the case to
unconditional production-safe status.

This is a domain-convergence result for the uniform `MODEL=s40rts` plus local
ULVZ overlay, `ATTENUATION=.false.`, 80–250 s diagnostic band.  It is not a
Kim et al. exact reproduction or production-frequency scientific validation.

## Reproducible fixtures

All artifacts are under
`results/one_chunk_boundary_validation_20260713T161732Z/`.  Inputs are
explicitly `locally_constructed_one_chunk_boundary_validation`:

- source: 5°S, 145°E, 208.6 km;
- science receiver: 25.26927°N, 110.75903°W;
- ULVZ: 19.6°N, 155.5°W, 512 km radius, 50 km height, dVs −20%, dVp −15%,
  dRho +10%, with the runtime smooth taper;
- 16 boundary probes: four sides, 5° inside each side, at 0, 50, 1,000 and
  2,750 km burial.  All 17 receivers were actually located by both solvers.

The 135° case uses center `(16°, −166°)`, gamma `154°`, NEX=96 and
2×2 ranks.  The global reference uses NEX=64 per 90° face and 2×2 ranks per
face (24 ranks total).  Full radial meshes are used; the one-chunk case has
Stacey lateral absorption and the global case has no lateral absorbing edge.

## Duration and resolution

Local `TauPyModel("prem")` gives Pdiff=821.68 s and Sdiff=1518.57 s for the
constructed 105° station.  With a 70 s postcursor end and 120 s safety
margin, the required duration was 1708.57 s.  The common user time step was
0.1035 s (0.9 × min(0.140, 0.115) s provisional stable steps); both final
solvers ran 16,800 steps (1738.80 s step span) and reported an end simulation
time of 1723.70 s, still above the 1708.57 s requirement.

Nominal 3:2 NEX was not treated as sufficient.  Extracted mesh databases show
135°/global target-layer median horizontal and radial GLL-spacing differences
of 0.0–5.7% for source, ULVZ core/edge, CMB corridor and station; the stated
15% matching criterion passes.  The corresponding tables, finite-difference
GLL Jacobian and local scale-ratio diagnostics are in
`03_mesh_resolution/analysis_target_layers/`.

## Runtime results

Both final solvers exit 0 and write 51 traces (17 receivers × 3 components).
On the science vertical trace, 135° versus global yields Pdiff CC=0.99970,
shift=−0.41 s; Sdiff CC=0.97145, shift=−2.38 s.  Its Pdiff and Sdiff residual
RMS are respectively 0.094 and 0.303 times the early pre-return residual RMS.
Thus there is no late residual increase above the specified `3×` early-baseline
criterion.  A conservative station-return lower bound is 1196.4 s; the
detected difference envelope begins earlier, as do boundary-probe differences,
so they cannot be labelled reflected boundary energy.

The triggered 120° NEX=96 test also exits 0.  Its vertical Sdiff CC falls to
0.92005 and its residual ratio rises to 0.589.  This is a sensitivity to the
smaller domain, but not a pure boundary test: actual horizontal GLL spacing
also differs by 6.1–11.8% from global (and is 120° rather than 135° geometry).
It supports retaining B rather than asserting A.

## Evidence and limits

| Question | Verdict | Evidence |
| --- | --- | --- |
| Common physics/time/output settings | verified | `01_inputs/`, final fixture `DATA/` copies |
| Actual target-region resolution matched, 135°/global | verified | `03_mesh_resolution/analysis_target_layers/actual_mesh_resolution_summary.json` |
| Deep buried probes supported | verified | both `OUTPUT_FILES/output_solver.txt`: 17/17 receivers |
| 135° full solver runtime | verified | `04_onechunk_135/logs/xspecfem3D_corrected.exit_code` = 0 |
| 6-chunk full solver runtime | verified | `05_global_6/logs/xspecfem3D_corrected.exit_code` = 0 |
| Target-window lateral contamination | not demonstrated | `07_waveform_analysis/metrics_v2/` |
| Unique probe-return attribution | unresolved | probe differences begin before return bounds |
| 120° domain sensitivity | verified but confounded by spacing | `metrics_120/`, `analysis_120_target_layers/` |

The full machine-readable result is
`08_reports/summary.json`.  Earlier failed/partial fixtures are intentionally
preserved with their logs: they record an initial relative S40RTS symlink
error, missing `crust2.0` dependency, front-end MPI timeout behavior, and an
initial incorrect probe-coordinate mapping.  They are not used as validation
evidence.
