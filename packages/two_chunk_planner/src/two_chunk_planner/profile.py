# SPDX-License-Identifier: GPL-3.0-or-later
"""Load the package-local canonical planning profile."""
from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def canonical_profile() -> dict[str, Any]:
    """Return a fresh copy of the bundled canonical profile."""
    resource = files("two_chunk_planner.resources").joinpath("canonical_profile_v1.json")
    return json.loads(resource.read_text(encoding="utf-8"))
