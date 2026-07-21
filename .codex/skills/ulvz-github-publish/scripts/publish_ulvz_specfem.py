#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_WORKING_DIR = PROJECT_ROOT
DEFAULT_PUBLISH_DIR = PROJECT_ROOT.with_name(f"{PROJECT_ROOT.name}_publish")
EXPECTED_REMOTE = "git@github.com:ordeal97/ulvz_specfem.git"
EXPECTED_BRANCH = "main"
MAX_FILE_BYTES = 90 * 1024 * 1024

RSYNC_FILTERS = [
    "--exclude=.git",
    "--exclude=.agents",
    "--include=/.codex/",
    "--include=/.codex/skills/",
    "--include=/.codex/skills/**",
    "--exclude=/.codex/**",
    "--exclude=.pytest_cache",
    "--exclude=.mpl",
    "--exclude=__pycache__",
    "--exclude=*.py[cod]",
    "--exclude=.conda",
    "--exclude=.venv",
    "--exclude=venv",
    "--exclude=env",
    "--exclude=conda-env",
    "--exclude=.env",
    "--exclude=.env.*",
    "--exclude=*.pem",
    "--exclude=*.key",
    "--exclude=*secret*",
    "--exclude=*token*",
    "--exclude=*password*",
    "--exclude=/note",
    "--exclude=/chunkplanner.zip",
    "--exclude=/results",
    "--exclude=/+results",
    "--exclude=/specfem3d_globe/obj",
    "--exclude=/specfem3d_globe/bin",
    "--exclude=/specfem3d_globe/DATABASES_MPI",
    "--exclude=/specfem3d_globe/OUTPUT_FILES",
    "--exclude=/specfem3d_globe/tests/**/obj",
    "--exclude=/specfem3d_globe/tests/**/bin",
    "--exclude=/specfem3d_globe/tests/meshfem3D/results.log",
    "--exclude=/specfem3d_globe/tests/meshfem3D/s40rts_ulvz_mesh_work_*",
    "--include=/packages/two_chunk_planner/validation/",
    "--include=/packages/two_chunk_planner/validation/user_guide_acceptance_20260717T093847Z/",
    "--include=/packages/two_chunk_planner/validation/user_guide_acceptance_20260717T093847Z/summary.json",
    "--include=/packages/two_chunk_planner/validation/user_guide_acceptance_20260717T093847Z/report.md",
    "--exclude=/packages/two_chunk_planner/validation/**",
    "--exclude=/task_4c_acceptance_artifacts",
]


class PublishError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the ULVZ SPECFEM working tree through the clean GitHub publishing copy."
    )
    parser.add_argument("--working-dir", type=Path, default=DEFAULT_WORKING_DIR)
    parser.add_argument("--publish-dir", type=Path, default=DEFAULT_PUBLISH_DIR)
    parser.add_argument("--sync", action="store_true", help="perform rsync instead of dry-run only")
    parser.add_argument("--commit-message", help="commit message to use after synchronization")
    parser.add_argument("--push", action="store_true", help="push origin/main after committing")
    parser.add_argument(
        "--allow-dirty-publish-repo",
        action="store_true",
        help="allow synchronization when the publishing repo is already dirty",
    )
    return parser


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if check and result.returncode != 0:
        raise PublishError(f"command failed with exit code {result.returncode}: {' '.join(cmd)}")
    return result


def git_output(publish_dir: Path, *args: str) -> str:
    result = run(["git", "-C", str(publish_dir), *args], check=True)
    return result.stdout.strip()


def require_publish_repo(publish_dir: Path) -> None:
    if not (publish_dir / ".git").is_dir():
        raise PublishError(f"publishing repository is missing .git: {publish_dir}")
    remote = git_output(publish_dir, "remote", "get-url", "origin")
    if remote != EXPECTED_REMOTE:
        raise PublishError(f"unexpected origin remote: {remote!r}; expected {EXPECTED_REMOTE!r}")
    branch = git_output(publish_dir, "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise PublishError(f"unexpected branch: {branch!r}; expected {EXPECTED_BRANCH!r}")


def status_short(publish_dir: Path) -> str:
    return git_output(publish_dir, "status", "--short")


def require_clean_publish_repo(publish_dir: Path, allow_dirty: bool) -> None:
    status = status_short(publish_dir)
    if status and not allow_dirty:
        raise PublishError(
            "publishing repository is dirty before synchronization. "
            "Commit, clean, or rerun with --allow-dirty-publish-repo.\n" + status
        )


def find_large_files(root: Path) -> list[Path]:
    large: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        if current == root / ".git" or root / ".git" in current.parents:
            dirnames[:] = []
            continue
        for filename in filenames:
            path = current / filename
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    large.append(path)
            except OSError:
                continue
    return large


def require_no_large_files(publish_dir: Path) -> None:
    large = find_large_files(publish_dir)
    if large:
        joined = "\n".join(str(path) for path in large)
        raise PublishError(f"files larger than 90 MB found in publishing copy:\n{joined}")


def rsync_command(working_dir: Path, publish_dir: Path, *, dry_run: bool) -> list[str]:
    mode = "-ani" if dry_run else "-a"
    return [
        "rsync",
        mode,
        *RSYNC_FILTERS,
        str(working_dir.resolve()) + "/",
        str(publish_dir.resolve()) + "/",
    ]


def synchronize(working_dir: Path, publish_dir: Path, *, dry_run: bool) -> None:
    if not working_dir.is_dir():
        raise PublishError(f"working directory does not exist: {working_dir}")
    run(rsync_command(working_dir, publish_dir, dry_run=dry_run), check=True)


def commit_changes(publish_dir: Path, message: str) -> bool:
    status = status_short(publish_dir)
    if not status:
        print("No publishing repository changes to commit.")
        return False
    run(["git", "-C", str(publish_dir), "add", "."], check=True)
    run(["git", "-C", str(publish_dir), "commit", "-m", message], check=True)
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        require_publish_repo(args.publish_dir)
        require_clean_publish_repo(args.publish_dir, args.allow_dirty_publish_repo)
        require_no_large_files(args.publish_dir)

        dry_run = not args.sync
        synchronize(args.working_dir, args.publish_dir, dry_run=dry_run)
        if dry_run:
            print("Dry-run complete. No files were changed.")
            return 0

        require_no_large_files(args.publish_dir)
        print("Publishing repository status after synchronization:")
        print(status_short(args.publish_dir) or "(clean)")

        committed = False
        if args.commit_message:
            committed = commit_changes(args.publish_dir, args.commit_message)
        elif args.push:
            raise PublishError("--push requires --commit-message")

        if args.push:
            if not committed:
                raise PublishError("--push requested but no commit was created")
            run(["git", "-C", str(args.publish_dir), "push", "origin", EXPECTED_BRANCH], check=True)

        print("Final publishing repository state:")
        run(["git", "-C", str(args.publish_dir), "status", "--short"], check=True)
        run(["git", "-C", str(args.publish_dir), "status", "-sb"], check=True)
        run(["git", "-C", str(args.publish_dir), "log", "-1", "--oneline"], check=True)
        return 0
    except PublishError as exc:
        print(f"publish_ulvz_specfem: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
