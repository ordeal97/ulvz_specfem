# Synthetic phase-aware acceptance fixture

This small input set is **synthetic phase-aware acceptance evidence**, not a
Kim/Song Hawaiʻi input, not a production model, and not a solver case.

It keeps the accepted canonical two-chunk geometry fixed at central latitude
0°, central longitude 0°, and `GAMMA_ROTATION_AZIMUTH=0°`. The source at
0°/0°, 50 km is classified in AB (the central chunk); `PA.PDA01` at 0°/−125°
is classified in AC (the supported-left chunk). Its 125° epicentral distance
was selected because current ObsPy TauP `prem` returns geographic `Pdiff` and
`Sdiff` paths. The phase-aware acceptance commands provide a 0–1900 s
analysis window and use a boundary speed only as an advisory, explicitly
non-conservative surface-arc estimate.

The fixture is consumed only by `packages/two_chunk_planner`; it must not be
passed to mesher or solver programs.
