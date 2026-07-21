#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check that both CLI references track parser-derived option metadata."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def option_sections(path: Path) -> dict[str, str]:
    """Return every level-three option section without accepting stale headings."""
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^### `(--[a-z0-9-]+)`$", text, flags=re.MULTILINE))
    return {
        match.group(1): text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        for index, match in enumerate(matches)
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    metadata = json.loads((root / "docs/generated/cli_options.json").read_text(encoding="utf-8"))
    expected = {item["flags"][0] for item in metadata["options"]}
    errors = []
    required_markers = {
        "en": tuple(f"**{field}:**" for field in ("Purpose", "Required", "Values", "Default", "When to use", "Relations", "Output effect", "Example", "Notes")),
        "zh": tuple(f"**{field}：**" for field in ("作用", "是否必需", "取值", "默认", "何时使用", "关系", "输出影响", "示例", "注意")),
    }
    for language in ("en", "zh"):
        sections = option_sections(root / f"docs/cli_reference_{language}.md")
        actual = set(sections)
        if actual != expected:
            errors.append({"language": language, "missing": sorted(expected - actual), "extra": sorted(actual - expected)})
        missing_fields = {
            option: [marker for marker in required_markers[language] if marker not in section]
            for option, section in sections.items()
        }
        missing_fields = {option: fields for option, fields in missing_fields.items() if fields}
        if missing_fields:
            errors.append({"language": language, "missing_required_fields": missing_fields})
    text = json.dumps({"expected_options": sorted(expected), "errors": errors, "status": "pass" if not errors else "fail"}, indent=2)
    print(text)
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
