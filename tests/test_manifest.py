"""Consistency checks across files that must agree."""

from __future__ import annotations

import json
from pathlib import Path
import re

COMPONENT = Path(__file__).parents[1] / "custom_components" / "espn_fantasy_hockey"


def test_cards_version_matches_manifest() -> None:
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    cards = (COMPONENT / "frontend" / "lib" / "const.js").read_text()

    match = re.search(r'VERSION = "([^"]+)"', cards)
    assert match, "VERSION not found in frontend/lib/const.js"
    assert match.group(1) == manifest["version"]
