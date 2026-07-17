# One-chunk regional coverage for Hawai'i and Iceland ULVZ geometries

## Executive conclusion

`NCHUNKS=1` is a real, supported regional-mesh mode, not a hidden two-chunk workaround. It has no parser-enforced angular-width maximum, but its cubed-sphere mapping uses `tan(width/2)` and is singular at 180°. That is only a mathematical bound. Low-resolution meshes at 90°, 105°, 120°, 135°, and 150° all completed with positive Jacobians; their quality degrades materially as width grows. No numerical reliable maximum was established above 150°.

For the explicitly **locally constructed** Hawai'i 100°–110° source–ULVZ–receiver proxy, a 135° square one chunk can cover all sampled points with a 24.3° minimum margin; a 120° candidate has only 16.8°. The best tested orientation is center latitude 16°, longitude −166°, gamma 154°. A short 1-rank solver smoke at that configuration located both points, completed, and wrote nonzero seismograms. This supports **B** only: main constructed geometry is coverable, but production boundary safety is unverified.

The 20-minute boundary-safety run completed all 6500 steps (1233.3 simulated seconds, exit 0). It establishes that this low-resolution configuration can run through a nominal long window, but has no independent larger-domain/reference comparison with which to identify or exclude lateral-boundary reflections. Therefore **no one-chunk configuration in this study is production-safe**.

## Source constraints

| Question | Verdict | Source | Routine / lines |
|---|---|---|---|
| One chunk legal | Yes | `src/shared/read_compute_parameters.f90` | `rcp_check_parameters:430-439,515-517` |
| One-chunk width cap | No explicit parser cap | same | xi=90 only for `NCHUNKS>1`; eta=90 only for `>2` |
| Mathematical limit | width must be <180° for finite mapping | `src/meshfem3D/compute_coordinates_grid.f90` | `compute_coord_main_mesh:149-163` |
| Rotation meaning | center lon/lat position AB face; gamma rotates local axes | `src/shared/euler_angles.f90` | `euler_angles:30-86` |
| Point inclusion | inverse rotation then chunk map/local coordinates | `src/auxiliaries/write_profile.f90` | `get_latlon_chunk_location:1290-1365` |
| Lateral absorption | xmin, xmax, ymin, ymax are absorbing for NCHUNKS=1 | `src/meshfem3D/get_absorb.f90` | `268-300,335-412` |
| CMB availability | needs full radial mesh, not shallow regional cutoff | `src/shared/define_all_layers.f90` | `126-147` |

The source therefore permits a one-chunk regional domain with independent xi/eta widths, but does not certify a large-width mesh. The 180° tangent singularity must not be treated as a usable limit.

## Inputs and geometry limits

Kim et al.'s local PDFs give the 2012-04-17 Eastern New Guinea reference event, Mw 6.9 and 208.6 km depth, 100°–110° Pdiff observations, and two 480-element chunks with edge absorption. They do **not** provide the source coordinates, station list, chunk rotation, original Par_file, or CMB ray coordinates. This study consequently uses an illustrative source `(−5°,145°)`, Hawai'i marker `(19.6°,−155.5°)`, 512-km ULVZ radius, a receiver continued on the same great circle to 105°, and a ±15° local CMB-sensitive corridor. It is not Fig. S4 reproduction.

Yuan & Romanowicz Table S1 supplies all eight event locations and distance ranges; its Event 2 is `(15.06°,−61.41°)`, 147.9 km, 120°–140°. Table S2 model 651 gives the Iceland ULVZ marker `(64.04°N,345.05°E)`, 400-km radius. Since no station files are local, each receiver is continued along the source-to-ULVZ great circle to the stated distance midpoint. Yuan's hybrid numerical method is not used as SPECFEM configuration evidence.

## Rotation search and margins

The Python search exactly implements the spherical-Earth algebra of `euler_angles.f90` and the AB-face `tan` map. It evaluates source, one constructed station, ULVZ center/edge samples, and the CMB proxy. Results are in `03_orientation_search/outputs/orientation_search.csv`.

| Case | 90° | 105° | 120° | 135° | 150° |
|---|---:|---:|---:|---:|---:|
| Hawai'i 100°–110° | 1.8° | 9.3° | 16.8° | 24.3° | 31.8° |
| Yuan Event 1 | 5.8° | 13.3° | 20.8° | 28.3° | 35.8° |
| Yuan Event 2 (120°–140°) | outside | outside | 3.1° | 10.6° | 18.1° |
| Yuan Event 3 | 4.7° | 12.2° | 19.7° | 27.2° | 34.7° |
| Yuan Event 4 | 1.9° | 9.4° | 16.9° | 24.4° | 31.9° |
| Yuan Event 5 | outside | 4.2° | 11.7° | 19.2° | 26.7° |
| Yuan Event 6 | outside | 5.6° | 13.1° | 20.6° | 28.1° |
| Yuan Event 7 | 0.9° | 8.4° | 15.9° | 23.4° | 30.9° |
| Yuan Event 8 | outside | 6.8° | 14.3° | 21.8° | 29.3° |
| All Yuan events, one fixed mesh | outside | outside | outside | 5.4° | 12.9° |

Entries are minimum edge margins for independently optimized orientations, not paper inputs. They show why distance alone is insufficient: Event 2 is geometrically coverable at 120°, but retains only 3.1° buffer; all Yuan events can be included in a fixed 150° domain only at 12.9°, where mesh quality is poorest.

For the selected 135° Hawai'i candidate, source/station/ULVZ-edge/CMB-proxy margins are 24.3°/24.8°/55.0°/48.4°. It passes 10°, 15°, and 20° screens but misses a 25° screen by 0.7°. Margins are screening metrics only; they do not prove a reflection-free time window.

## Width mesh scan

All scans used the source-derived minimum legal full-radial smoke grid `NEX_XI=NEX_ETA=32`, `NPROC_XI=NPROC_ETA=1`, `1D_isotropic_prem`, no cutoff, and lateral Stacey absorption. They are topology/stability tests, not 6.3-s resolution tests.

| Width | Exit | crust/mantle max/min edge ratio | min Jacobian eigenvalue ratio | empirical resolved period |
|---:|---|---:|---:|---:|
| 90° | 0 | 94.8 | 0.02062 | 139.0 s |
| 105° | 0 | 110.7 | 0.01615 | 162.2 s |
| 120° | 0 | 130.8 | 0.01224 | 185.3 s |
| 135° | 0 | 161.0 | 0.00863 | 208.5 s |
| 150° | 0 | 212.0 | 0.00434 | 231.7 s |

Thus 150° remains meshable in this low-resolution test, but has substantially larger distortion and the lowest tested Jacobian quality. 135° is the largest tested width that is selected for the Hawai'i balance of geometric margin and relative mesh quality; it is not a proven production limit.

## Solver evidence and boundary safety

The final 135° optimal-orientation mesh was remeshed separately. A 0.5-minute, 1-rank solver smoke ended normally: source and station both located in slice 0 and each component had 300 samples with nonzero values. This verifies executable operation, point location, MPI stability, and output only.

A separate 20-minute run was the boundary-safety tier. The mesh's maximum P velocity is about 13.7 km/s; even a simplistic closest-side source/station path gives a roughly 400-s fast-path reflection-scale proxy, while a 105° direct path has an 850-s lower-bound travel time at that maximum speed. Exact Pdiff/Sdiff and side-reflection arrivals require ray/wavefield comparison. The run completed 6500/6500 steps (1233.3 s, exit 0). In its vertical trace, detectable energy begins near 513.8 s, reaches 1% of peak near 725.1 s, and the largest peak is near 1189.8 s. Those observations show that the run covers a long nominal window, but cannot identify or exclude lateral-boundary arrivals without a larger-domain/reference comparison. Its boundary-safety status is therefore `completed_duration_reference_contamination_unverified`, not production-safe.

## Classifications

- **Hawai'i: B.** The constructed principal geometry fits in 135° with substantial screening margins and short runtime verification, but a completed boundary-safe production window is absent.
- **Yuan medium-distance events: B.** Individually rotated 120°–135° configurations can geometrically cover most constructed source–ULVZ–receiver proxies; no event-specific solver or boundary test was run.
- **Yuan Event 2, 120°–140°: C.** It requires at least 120° merely to be inside and reaches only 18.1° even at 150°; large-width mesh degradation and no runtime evidence limit it to a coverage/smoke candidate.
- **One fixed mesh for all Yuan events: C.** 135° covers all only with 5.4° margin; 150° raises that to 12.9° but is the poorest tested mesh. It is not a credible multi-event production domain.
- **Production-safe: false.** No configuration has a completed boundary-safety run through verified target Pdiff/Sdiff windows and reflected arrivals.

## Candidate Par_file prescriptions

These are source-constraint-consistent planning configurations, **not production approvals**. `REGIONAL_MESH_CUTOFF=.false.` and `ABSORBING_CONDITIONS=.true.` are required for CMB Pdiff/Sdiff. Topography, oceans, attenuation, rotation and gravity should remain disabled only for the present reference/smoke design; science-model choices require a separate decision.

| Tier | NCHUNKS | NEX xi/eta | NPROC xi/eta | center lat/lon/gamma | width xi/eta | duration | Station rule |
|---|---:|---:|---:|---|---|---|---|
| Hawai'i B candidate | 1 | 768/768 | 4/4 | 16°/−166°/154° | 135°/135° | 20 min candidate; unverified | retain only stations with ≥20° computed margin |
| Wider-margin study | 1 | 960/960 | 4/4 | rerun 150° search optimum | 150°/150° | 20 min candidate; unverified | retain only ≥20°; reject if production mesh quality worsens |
| Lowest-cost smoke | 1 | 384/384 | 2/2 | 16°/−166°/154° | 120°/120° | 0.5–2 min | only the constructed station subset; no Pdiff/Sdiff interpretation |

The NEX/NPROC combinations satisfy the observed default full-radial divisibility rule. The larger NEX values preserve lateral resolution more closely as width grows; they have not been meshed here. Before any production use, rerun the selected configuration at target period with a completed boundary-safe duration and an independent larger-domain/reference comparison.

## Artifacts and limits

All evidence is in `results/one_chunk_hawaii_yuan_analysis_20260713T123820Z/`. The previous two-chunk result was read only. No SPECFEM production source was changed. The completed long run is not classified as a reflection-free validation because no larger-domain/reference comparison was run.
