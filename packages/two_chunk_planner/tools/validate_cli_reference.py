#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check that both CLI references track parser-derived option metadata."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def headings(path: Path) -> set[str]:
    return set(re.findall(r"^### `(--[a-z0-9-]+)`$", path.read_text(encoding="utf-8"), flags=re.MULTILINE))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    metadata = json.loads((root / "docs/generated/cli_options.json").read_text(encoding="utf-8"))
    expected = {item["flags"][0] for item in metadata["options"]}
    errors = []
    for language in ("en", "zh"):
        actual = headings(root / f"docs/cli_reference_{language}.md")
        if actual != expected:
            errors.append({"language": language, "missing": sorted(expected - actual), "extra": sorted(actual - expected)})
    text = json.dumps({"expected_options": sorted(expected), "errors": errors, "status": "pass" if not errors else "fail"}, indent=2)
    print(text)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
