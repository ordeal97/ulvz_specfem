---
name: ulvz-github-publish
description: Publish this ULVZ SPECFEM project to GitHub using its dedicated clean publishing repository. Use when the user asks to push, publish, update GitHub, synchronize the GitHub repository, or follow docs/github_publish_workflow.md for this project.
---

# ULVZ GitHub Publish

## Overview

Set `PROJECT_ROOT` to the ULVZ working tree and `PUBLISH_REPO` to its dedicated
clean publishing copy, then use this skill to publish from `PUBLISH_REPO`.

Do not publish from `specfem3d_globe`; that nested repository tracks upstream
SPECFEM and is not the GitHub publishing repository for this project.

## Required Context

Read `docs/github_publish_workflow.md` before publishing. Treat it as the
authoritative workflow. This skill and its script encode that workflow for
repeatable use.

The GitHub remote must be:

```text
git@github.com:ordeal97/ulvz_specfem.git
```

The publishing branch must be:

```text
main
```

## Workflow

1. Verify any task-specific tests before publishing. For visualization changes,
   use the project Python interpreter:

   ```bash
   "${ULVZ_PYTHON:-python3}" \
     -m pytest tests/ulvz_mesh_viz/test_ulvz_mesh_viz.py -q
   ```

2. Run a dry run from the working project root:

   ```bash
   python .codex/skills/ulvz-github-publish/scripts/publish_ulvz_specfem.py
   ```

   Inspect the rsync preview, publishing repository status, and large-file
   check. The dry run must not modify files.

3. If the preview is correct, synchronize, commit, and push:

   ```bash
   python .codex/skills/ulvz-github-publish/scripts/publish_ulvz_specfem.py \
     --sync \
     --commit-message "Describe the update" \
     --push
   ```

4. Verify the final output:

   ```bash
   git -C "$PUBLISH_REPO" status --short
   git -C "$PUBLISH_REPO" status -sb
   git -C "$PUBLISH_REPO" log -1 --oneline
   ```

## Safety Rules

- Never force-push unless the user explicitly requests it after reviewing
  remote history.
- Never initialize Git in the working project directory.
- Never commit preserved work directories, SPECFEM build outputs, simulation
  databases, logs, caches, or secret-like files.
- Treat any file larger than 90 MB in the publishing copy as a hard blocker.
- Stop if the publishing repo is dirty before synchronization.
- Stop if the publishing remote or current branch does not match this skill.

## Script

Use `scripts/publish_ulvz_specfem.py` for the repetitive checks and rsync
command. It defaults to dry-run mode. It only pushes when `--push` is supplied.
