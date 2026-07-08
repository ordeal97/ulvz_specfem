#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


RULE_TARGET = "\t$E/xulvz_model_extract \\"
RULE_OBJECT = "\t$(xulvz_model_extract_OBJECTS) \\"
RULE_BLOCK = """xulvz_model_extract_OBJECTS = \\
\t$O/ulvz_model_extract.aux.o \\
\t$(EMPTY_MACRO)

xulvz_model_extract_SHARED_OBJECTS = \\
\t$O/shared_par.shared_module.o \\
\t$(EMPTY_MACRO)

${E}/xulvz_model_extract: $(xulvz_model_extract_OBJECTS) $(xulvz_model_extract_SHARED_OBJECTS)
\t${MPIFCCOMPILE_CHECK} -o $@ $+ $(MPILIBS)

#######################################

"""


@dataclass(frozen=True)
class InstallPlan:
    specfem_root: Path
    source_path: Path
    target_source: Path
    rules_path: Path
    new_rules_text: str
    copy_source: bool
    patch_rules: bool
    messages: list[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install the ULVZ model extractor source and build rule into a compatible SPECFEM3D_GLOBE checkout."
    )
    parser.add_argument("--specfem-root", required=True, help="Path to the target SPECFEM3D_GLOBE checkout")
    parser.add_argument("--dry-run", action="store_true", help="Print planned operations without modifying the checkout")
    parser.add_argument("--apply", action="store_true", help="Apply the planned source copy and rules.mk update")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dry_run = not args.apply or bool(args.dry_run)
    try:
        plan = make_plan(Path(args.specfem_root))
        print_plan(plan, dry_run=dry_run)
        if dry_run:
            return 0
        apply_plan(plan)
        print("Applied ULVZ extractor installation.")
        return 0
    except InstallerError as exc:
        print(f"install_extractor.py: {exc}", file=sys.stderr)
        return 1


class InstallerError(RuntimeError):
    pass


def make_plan(specfem_root: Path) -> InstallPlan:
    specfem_root = specfem_root.expanduser().resolve()
    if not specfem_root.exists():
        raise InstallerError(f"target SPECFEM root does not exist: {specfem_root}")
    if not specfem_root.is_dir():
        raise InstallerError(f"target SPECFEM root is not a directory: {specfem_root}")

    extension_root = Path(__file__).resolve().parent
    source_path = extension_root / "src" / "auxiliaries" / "ulvz_model_extract.f90"
    if not source_path.exists():
        raise InstallerError(f"bundled extractor source is missing: {source_path}")

    rules_path = specfem_root / "src" / "auxiliaries" / "rules.mk"
    if not rules_path.exists():
        raise InstallerError(f"required SPECFEM build file is missing: {rules_path}")

    target_source = specfem_root / "src" / "auxiliaries" / "ulvz_model_extract.f90"
    messages: list[str] = []
    copy_source = True
    if target_source.exists():
        if target_source.read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8"):
            copy_source = False
            messages.append(f"Extractor source already present with matching content: {target_source}")
        else:
            raise InstallerError(
                "target extractor source already exists with different content; "
                f"refusing to overwrite without explicit manual handling: {target_source}"
            )

    rules_text = rules_path.read_text(encoding="utf-8")
    if "xulvz_model_extract" in rules_text:
        messages.append(f"xulvz_model_extract build rule already appears in {rules_path}; rules.mk will not be modified.")
        new_rules_text = rules_text
        patch_rules = False
    else:
        new_rules_text = add_build_rule(rules_text, rules_path)
        patch_rules = True

    return InstallPlan(
        specfem_root=specfem_root,
        source_path=source_path,
        target_source=target_source,
        rules_path=rules_path,
        new_rules_text=new_rules_text,
        copy_source=copy_source,
        patch_rules=patch_rules,
        messages=messages,
    )


def add_build_rule(rules_text: str, rules_path: Path) -> str:
    updated = _insert_after(
        rules_text,
        "\t$E/xextract_database \\",
        RULE_TARGET,
        rules_path,
        "auxiliaries_TARGETS xextract_database entry",
    )
    updated = _insert_after(
        updated,
        "\t$(xextract_database_OBJECTS) \\",
        RULE_OBJECT,
        rules_path,
        "auxiliaries_OBJECTS xextract_database entry",
    )
    marker = "xwrite_profile_OBJECTS = \\"
    if marker not in updated:
        raise InstallerError(f"patch context is incompatible in {rules_path}: missing {marker!r}")
    return updated.replace(marker, RULE_BLOCK + marker, 1)


def _insert_after(text: str, anchor: str, insertion: str, rules_path: Path, label: str) -> str:
    if insertion in text:
        return text
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\n") == anchor:
            newline = "\n" if line.endswith("\n") else ""
            lines.insert(index + 1, insertion + newline)
            return "".join(lines)
    raise InstallerError(f"patch context is incompatible in {rules_path}: missing {label}")


def print_plan(plan: InstallPlan, *, dry_run: bool) -> None:
    print("DRY RUN: no files will be modified." if dry_run else "APPLY: files will be modified.")
    print(f"SPECFEM root: {plan.specfem_root}")
    for message in plan.messages:
        print(f"- {message}")
    if plan.copy_source:
        print(f"- Copy {plan.source_path} -> {plan.target_source}")
    else:
        print(f"- Keep existing source {plan.target_source}")
    if plan.patch_rules:
        print(f"- Add xulvz_model_extract build rule to {plan.rules_path}")
    else:
        print(f"- Keep existing build rules in {plan.rules_path}")


def apply_plan(plan: InstallPlan) -> None:
    if plan.copy_source:
        shutil.copy2(plan.source_path, plan.target_source)
    if plan.patch_rules:
        current = plan.rules_path.read_text(encoding="utf-8")
        if "xulvz_model_extract" in current:
            raise InstallerError(f"xulvz_model_extract appeared in {plan.rules_path} before apply; aborting")
        plan.rules_path.write_text(plan.new_rules_text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
