"""Golden snapshot fixtures for Windows backend regression testing (GW-026).

Contains JSON golden fixtures representing real accessibility tree snapshots
from Notepad, Calculator, and Windows Settings. These fixtures conform to
the NormalizedElement.to_dict() schema and serve as regression test data
for the Windows backend snapshot pipeline.

Fixture files:
- notepad.json: Notepad with menu bar, document editor, status bar.
- calculator.json: Calculator with display, digit/operator buttons.
- windows_settings.json: Settings with navigation list, content pane.
"""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> dict:
    """Load a JSON golden fixture by filename.

    Args:
        name: Fixture filename (e.g. ``"notepad.json"``).

    Returns:
        Parsed fixture dict.
    """
    path = FIXTURES_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)
