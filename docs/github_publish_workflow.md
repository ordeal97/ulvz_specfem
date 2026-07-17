# GitHub Publish Workflow

This document records how this project is published to GitHub and how to update
the GitHub repository after future local changes.

## Repository Layout

Set portable locations before running the workflow:

```bash
export PROJECT_ROOT=/path/to/ulvz_specfem
export PUBLISH_REPO=/path/to/ulvz_specfem_publish
```

This directory is used for development, testing, SPECFEM builds, and simulation
work. It is not itself the GitHub publishing repository.

The long-lived publishing copy is `$PUBLISH_REPO`.

This publishing copy is a clean Git repository used only for commits and pushes
to GitHub. Keeping it separate avoids accidentally committing nested Git
metadata, build outputs, and temporary test artifacts from the working
directory.

The GitHub remote is:

```bash
git@github.com:ordeal97/ulvz_specfem.git
```

The publishing repository currently tracks:

```bash
main -> origin/main
```

Initial published commit:

```bash
3191be2 Initial ULVZ SPECFEM project import
```

## Update GitHub After Local Changes

After making and verifying changes in the working project directory, synchronize
the clean contents into the publishing copy:

```bash
rsync -a \
  --exclude=.git \
  --exclude=.agents \
  --include=/.codex/ \
  --include=/.codex/skills/ \
  --include=/.codex/skills/** \
  --exclude=/.codex/** \
  --exclude=.pytest_cache \
  --exclude=.mpl \
  --exclude=__pycache__ \
  --exclude='*.py[cod]' \
  --exclude=.conda \
  --exclude=.venv \
  --exclude=venv \
  --exclude=env \
  --exclude=conda-env \
  --exclude=.env \
  --exclude='.env.*' \
  --exclude='*.pem' \
  --exclude='*.key' \
  --exclude='*secret*' \
  --exclude='*token*' \
  --exclude='*password*' \
  --exclude=/note \
  --exclude=/results \
  --exclude=/+results \
  --exclude=/specfem3d_globe/obj \
  --exclude=/specfem3d_globe/bin \
  --exclude=/specfem3d_globe/DATABASES_MPI \
  --exclude=/specfem3d_globe/OUTPUT_FILES \
  --exclude='/specfem3d_globe/tests/**/obj' \
  --exclude='/specfem3d_globe/tests/**/bin' \
  --exclude=/specfem3d_globe/tests/meshfem3D/results.log \
  --exclude=/specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_* \
  --include=/packages/two_chunk_planner/validation/ \
  --include=/packages/two_chunk_planner/validation/user_guide_acceptance_20260717T093847Z/ \
  --include=/packages/two_chunk_planner/validation/user_guide_acceptance_20260717T093847Z/summary.json \
  --include=/packages/two_chunk_planner/validation/user_guide_acceptance_20260717T093847Z/report.md \
  --exclude=/packages/two_chunk_planner/validation/** \
  --exclude=/task_4c_acceptance_artifacts \
  "$PROJECT_ROOT/" \
  "$PUBLISH_REPO/"
```

Then commit and push from the publishing copy:

```bash
cd "$PUBLISH_REPO"
git status
git add .
git commit -m "Update project"
git push
```

Use a specific commit message when possible, for example:

```bash
git commit -m "Add S40RTS ULVZ test documentation"
```

If `git status` shows no changes after synchronization, there is nothing new to
push.

The same workflow is also encoded as a project Codex skill:

```bash
python .codex/skills/ulvz-github-publish/scripts/publish_ulvz_specfem.py
```

By default the script runs a dry run only. To synchronize, commit, and push:

```bash
python .codex/skills/ulvz-github-publish/scripts/publish_ulvz_specfem.py \
  --sync \
  --commit-message "Describe the update" \
  --push
```

## What Is Excluded

The synchronization command excludes:

- `.git`: prevents copying Git repository metadata from the working directory or
  nested source trees.
- `.agents`: local agent/tooling metadata.
- `.codex`: only `.codex/skills/**` is published; other `.codex` state is
  excluded as local agent/tooling metadata.
- `.pytest_cache`, `__pycache__`, and `*.py[cod]`: Python test and bytecode
  caches.
- `.mpl`: local Matplotlib cache.
- `.conda`, `.venv`, `venv`, `env`, and `conda-env`: local Python or Conda
  environments.
- `.env`, `.env.*`, `*.pem`, `*.key`, and names containing `secret`, `token`,
  or `password`: local secrets and credentials.
- `note`: local scratch notes.
- `results`: local simulation evidence, including large databases and waveform
  products. Summaries remain in project documentation and manifests.
- `+results`: a local legacy results directory retained outside GitHub.
- `specfem3d_globe/obj`: SPECFEM object/build files.
- `specfem3d_globe/bin`: SPECFEM compiled executables.
- `specfem3d_globe/DATABASES_MPI` and `specfem3d_globe/OUTPUT_FILES`:
  simulation databases and output.
- `specfem3d_globe/tests/meshfem3D/results.log`: generated test output.
- `specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_*`: preserved local
  validation work directories and mesher artifacts.
- nested SPECFEM test `obj` and `bin` directories: generated test objects and
  executables.
- `packages/two_chunk_planner/validation/**`: full local smoke outputs and
  logs. Only the compact published acceptance `summary.json` and `report.md`
  are synchronized.
- `task_4c_acceptance_artifacts`: reusable-postprocessing runtime evidence,
  including machine-specific database paths and generated arrays. It remains
  locally preserved; the public status documentation records its conclusions.

Before pushing large updates, it is useful to check for files that GitHub may
reject:

```bash
find "$PUBLISH_REPO" \
  -path "$PUBLISH_REPO/.git" -prune \
  -o -type f -size +90M -print
```

No output means no file larger than 90 MB was found outside `.git`.

## Important Rules

- Do not initialize Git directly in the working project directory.
- Do not force-push unless this is explicitly intended and the remote history has
  been checked.
- Do not commit SPECFEM build outputs unless there is a specific reason.
- Keep development, tests, and simulation runs in the working directory.
- Keep GitHub commits and pushes in the publishing copy.
- If SSH authentication fails, check:

```bash
ssh -T git@github.com
```

## Temporary Upload Copies

The earlier temporary upload directories under `/tmp` were only used for the
first import. They are no longer part of the workflow.

Future updates should use the long-lived publishing copy:

```bash
$PUBLISH_REPO
```
