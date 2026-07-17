#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Write parser-derived CLI metadata without executing a planning run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from two_chunk_planner.cli import build_parser


def serialise_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def action_record(action: argparse.Action) -> dict:
    return {
        "flags": action.option_strings,
        "dest": action.dest,
        "metavar": action.metavar,
        "nargs": action.nargs,
        "required": action.required,
        "default": serialise_default(action.default),
        "choices": list(action.choices) if action.choices else None,
        "repeatable": isinstance(action, argparse._AppendAction),
        "help": action.help,
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = build_parser()
    plan_parser = next(action.choices["plan"] for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    records = [action_record(action) for action in plan_parser._actions if action.option_strings and action.dest != "help"]
    output = root / "docs/generated/cli_options.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema": "two_chunk_planner_cli_options.v1", "command": "two-chunk-planner plan", "options": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
