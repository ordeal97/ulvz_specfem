# ULVZ SPECFEM project rules

## Scientific scope
This project uses SPECFEM3D_GLOBE to study waveform effects caused by
synthetic ultralow-velocity zones (ULVZ) near the core-mantle boundary.

Do not change scientific assumptions without explicitly reporting them.
Do not infer physical parameters from convenience.

## Reproducibility
- Never overwrite an existing simulation case.
- Every run directory must contain a copy of its parameter file.
- Every ULVZ model must have a machine-readable YAML or CSV record.
- Preserve the background model separately from the perturbation model.
- Record git commit, SPECFEM version, MPI command, mesh settings, and date.

## Model conventions
- Coordinates must be clearly documented: geographic latitude/longitude,
  geocentric latitude if used, radius/depth, and units.
- ULVZ perturbations must specify dVp, dVs, dRho, geometry, thickness,
  lateral radius, center location, and transition width.
- Use a smooth taper at ULVZ boundaries unless a sharp boundary is requested.
- Do not modify attenuation parameters unless explicitly instructed.

<!-- ## Workflow
1. Validate the reference simulation before generating ULVZ cases.
2. Run a small test model before a parameter sweep.
3. Check that the ULVZ is located at the intended CMB position.
4. Verify no NaNs, abnormal CFL warnings, missing seismograms, or failed MPI ranks.
5. Compare ULVZ runs only against the identical reference case. -->

## Coding
- Python scripts must use argparse and write logs.
- Use pathlib rather than hard-coded absolute paths.
- Add dry-run support for file-generating scripts.
- Do not delete files unless explicitly asked.
- Before editing SPECFEM source code, explain why input-model scripts are insufficient.
- Follow existing file structure and naming style.
- Prefer small, focused changes.
- Do not rewrite unrelated files.
- Do not add new dependencies unless necessary.
- Never intall and update python environment, ask the user to do it.
- Always plan before really coding.
- Do not write test outputs, diagnostic outputs, logs, plots, or temporary generated files directly into the repository root. If such outputs need to be kept near the main working directory, place them under `results/`.


## Python environment

  For ULVZ mesh visualization and test scripts, use:

  `$ULVZ_PYTHON` (set it to the project-managed Python interpreter).

  Do not rely on implicit `conda activate`. Use the absolute interpreter path in verification commands unless the
  user says otherwise.



## Project status
Authoritative project overview:
docs/project_status.md
Update it whenever a major Task is completed or a new validation result is obtained.

Visulization tool overview:
docs/ulvz_mesh_visualization_guide.md
Update it whenever a major Task for visualization is completed or a new update of the visualization tools is obtained.
