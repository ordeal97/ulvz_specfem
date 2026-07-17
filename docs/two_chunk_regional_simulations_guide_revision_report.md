# Bilingual regional-guide revision report

## Purpose and scope

This report records the usability and source-audit revision of the bilingual
canonical two-chunk manual.  It changes documentation, source-controlled SVG
figures, and a shell/Python documentation-validation path only.  It does not
modify formal SPECFEM source, build rules, or the accepted endpoint patch, and
it runs no mesher, database, or solver production calculation.

## Files changed

- `docs/two_chunk_regional_simulations_guide_en.md`
- `docs/two_chunk_regional_simulations_guide_zh.md`
- `docs/two_chunk_regional_simulations_guide.md`
- `docs/two_chunk_regional_simulations_guide_en.pdf`
- `docs/two_chunk_regional_simulations_guide_zh.pdf`
- `docs/two_chunk_absorbing_boundary_audit.md`
- `docs/assets/two_chunk_canonical_geometry.svg`
- `docs/assets/two_chunk_user_workflow.svg`
- `cases/two_chunk_canonical_90deg/generate_geometry_figure.py`
- `cases/two_chunk_canonical_90deg/run_canonical.sh`
- `scripts/render_two_chunk_regional_guides.sh`
- `scripts/validate_two_chunk_regional_guides.py`

## Resolution of the user-facing issues

| Concern | Revision |
|---|---|
| Opaque AB--AC/C1/C2 terminology | Added a plain-language terminology table before implementation detail, endpoint roles, MPI/buffer/rank explanation, and a glossary. |
| Gamma arrow and prose disagreed | Replaced the figure with a tangent-plane panel labelled with the external viewing direction and positive counter-clockwise convention.  The examples for 0°, 90°, and 180° are numerical local-axis consequences. |
| “Chunk 2 left” looked geographic | The local topology panel now labels AB/AC face roles and states that `supported-left` is unrotated topology, not west on a map. |
| “Audit tool” was ambiguous | The manual separates the pre-mesh `audit_geometry.py`, planner, patch verifier, and advanced topology/waveform evidence; every user-run action has a command and output/stop criterion. |
| Patch installation was underspecified | Added minimum and traceable `git apply` workflows, candidate-hash verification, reverse check, already-applied recognition, and a warning against whole-file replacement. |
| First-run and research validation were mixed | Replaced the narrative sequence with a minimal staged workflow, stop conditions, a one-page checklist, and an explicitly separate advanced acceptance section. |

## Gamma convention and evidence

Operational convention: viewed from outside Earth looking down at the central
point, positive `GAMMA_ROTATION_AZIMUTH` is counter-clockwise from due North.
For centre `(0°, 0°)`, no ellipticity, gamma 0° gives local `+eta` North and
`+xi` East; 90° gives `+eta` West and `+xi` North; 180° gives `+eta` South and
`+xi` West.  Evidence: `src/shared/euler_angles.f90` (Euler matrix),
`doc/USER_MANUAL/05_regional_simulations.tex` (regional definition), and
`packages/two_chunk_planner/src/two_chunk_planner/transforms.py` (same
operational transformation).  The SVG uses that same external-view convention.

## Global sponge, regional Stacey, and AB--AC correction

| Item | Earlier handbook wording | Current-source evidence | Corrected user instruction |
|---|---|---|---|
| Global sponge | The older short sponge description did not state the two-chunk run-time stop or distinguish it from regional faces. | `read_compute_parameters.f90` lines 456--457 stop sponge unless `NCHUNKS=6`; `meshfem3D_models.F90` applies sponge through Q/attenuation logic. | For canonical two chunks set `ABSORB_USING_GLOBAL_SPONGE=.false.`; never treat sponge as a side-face option. |
| Regional absorption | The older text did not enumerate the actual outer-face selection. | `create_regions_mesh.F90` calls `get_absorb`; `get_absorb.f90` selects AC xi-min, AB xi-max, and exposed eta faces. | Set `ABSORBING_CONDITIONS=.true.` and validate exposed face roles after meshing. |
| AB--AC | The invariant was present but its source-level exclusion was not explained. | `get_absorb.f90` excludes AB xi-min and AC xi-max. | AB--AC is MPI communication only: never sponge, Stacey, or another absorber. |

The audited conclusion is therefore: current source stops global sponge unless
`NCHUNKS=6`; canonical two chunks use regional `ABSORBING_CONDITIONS=.true.`
on exposed faces and `ABSORB_USING_GLOBAL_SPONGE=.false.`. Full source locations,
call path, and configuration rule are in
[`two_chunk_absorbing_boundary_audit.md`](two_chunk_absorbing_boundary_audit.md).

## Figures and reproducibility

- `two_chunk_canonical_geometry.svg`: local AB/AC topology and gamma
  tangent-plane convention.
- `two_chunk_user_workflow.svg`: first-run stages, stop conditions, face-role
  invariant, and production-validation gate.
- `generate_geometry_figure.py`: source-controlled regeneration of both SVG
  assets; `--dry-run` performs no write.

## Verification record

### Workflow clarification update

The first revision's section 6 could be read as if `audit_geometry.py`, the
planner, and `run_canonical.sh` were a single general-user sequence. Current
implementation inspection showed otherwise: `audit_geometry.py` enforces the
teaching fixture's center 90°, longitude 90°, and gamma 0°; the runner copies
that fixture's `DATA/`; the planner is the component that accepts arbitrary
canonical center/lon/gamma searches and emits the transformed geographic map.
The bilingual guides now separate custom-input planning/running from teaching
fixture checking/running, and add an explicit fixed-geometry planner procedure
for locating AC on Earth after the three placement parameters are chosen. It
also documents the planner's intentional longitude/gamma canonicalization at a
polar center, where multiple numeric triplets encode the same physical domain.

The 2026-07-17 document verification completed as follows:

- bilingual static validator: pass; both guides contain ordered sections 1--12,
  28 required parameter names, identical executable command blocks, manifest
  hashes, required safety text, local links, SVG assets, and current-source
  global-sponge/internal-face invariants;
- teaching `audit_geometry.py --validate-only`: pass, seven in-domain points
  and total MPI ranks 8;
- fixed-geometry planner command: pass with the teaching inputs; it returned
  one feasible candidate and wrote `map.png`. The polar teaching center was
  canonically represented as longitude 0°/gamma 90°, which is physically
  equivalent to its input longitude 90°/gamma 0°;
- `run_canonical.sh --dry-run`: pass with the project Python interpreter; it
  printed, but did not execute, the 8-rank `xmeshfem3D` and `xspecfem3D`
  commands;
- planner geometry-only smoke: pass; all eight documented output files were
  produced in a fresh temporary directory;
- patch check: a temporary nested-HEAD baseline passed `verify_patch.sh`,
  forward apply produced candidate SHA
  `8c64f1d1d415ec6c0792f06474dafcffcc698da6ee03ecd21bfd4fdc90b64857`,
  and reverse dry-run passed; the current accepted worktree also passed the
  reverse dry-run;
- a relative patch path was found to fail under `git -C specfem3d_globe` during
  this check, so both guides now bind `PATCH` to `$(pwd)/patches/...` before
  the `git -C` commands;
- PDF build: the English PDF rendered as six A4 pages and the Chinese PDF as
  five. Text extraction found the new AC-position and fixture-scope wording;
  pages with terminology, topology/gamma figure, custom-workflow code blocks,
  workflow figure, tables, and final evidence were visually inspected. No blank
  trailing page, clipped figure, unreadable CJK text, or split code block was
  found.

`wkhtmltopdf` emitted sandbox-only AF_NETLINK warnings while rendering; PDF
generation still completed normally and the PDFs passed inspection. The
scientific limits remain unchanged: canonical 90°×90° only;
`general_two_chunk_mode_classification=B`; no Kim/Song exact reconstruction
without author inputs; the planner does not replace mesher, Stacey, or waveform
acceptance.
