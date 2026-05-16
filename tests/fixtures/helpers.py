"""Shared helpers for golden snapshot fixture tests (GW-026).

Provides utilities for loading golden snapshot JSON files from the
``tests/fixtures/windows/`` directory and comparing snapshot structures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent / "windows"


def load_golden_snapshot(name: str) -> dict[str, Any]:
    """Load a golden snapshot JSON file by filename.

    Args:
        name: Fixture filename, e.g. ``"notepad_snapshot.json"``.

    Returns:
        The full fixture dict including ``_metadata`` and ``snapshot`` keys.

    Raises:
        FileNotFoundError: If the fixture file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = FIXTURES_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_snapshots(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> list[str]:
    """Compare two raw snapshot tree dicts and report differences.

    Recursively walks both trees and checks structural and value
    equality for all node fields. Returns a list of difference
    descriptions (empty if the trees match).

    Args:
        actual: The snapshot tree to validate.
        expected: The reference golden snapshot tree.

    Returns:
        A list of human-readable difference strings.
    """
    differences: list[str] = []
    _compare_nodes(actual, expected, path="root", differences=differences)
    return differences


def _compare_nodes(
    actual: dict[str, Any],
    expected: dict[str, Any],
    path: str,
    differences: list[str],
) -> None:
    """Recursively compare two snapshot nodes."""
    # Compare top-level scalar fields
    for field in ("control_type", "name", "value", "is_enabled", "is_offscreen"):
        actual_val = actual.get(field)
        expected_val = expected.get(field)
        if actual_val != expected_val:
            differences.append(
                f"{path}.{field}: expected {expected_val!r}, got {actual_val!r}"
            )

    # Compare bounds
    _compare_bounds(actual.get("bounds"), expected.get("bounds"), path, differences)

    # Compare patterns
    _compare_patterns(
        actual.get("patterns", []),
        expected.get("patterns", []),
        path,
        differences,
    )

    # Compare children count and recurse
    actual_children = actual.get("children", [])
    expected_children = expected.get("children", [])
    if len(actual_children) != len(expected_children):
        differences.append(
            f"{path}.children: expected {len(expected_children)} children, "
            f"got {len(actual_children)}"
        )
        return

    for i, (ac, ec) in enumerate(
        zip(actual_children, expected_children, strict=True),
    ):
        child_name = ac.get("name", ac.get("control_type", i))
        _compare_nodes(ac, ec, path=f"{path}.children[{i}]({child_name})", differences=differences)


def _compare_bounds(
    actual: dict[str, Any] | None,
    expected: dict[str, Any] | None,
    path: str,
    differences: list[str],
) -> None:
    """Compare bounds dicts."""
    if actual is None and expected is None:
        return
    if actual is None:
        differences.append(f"{path}.bounds: expected {expected!r}, got None")
        return
    if expected is None:
        differences.append(f"{path}.bounds: expected None, got {actual!r}")
        return
    for key in ("x", "y", "width", "height"):
        if actual.get(key) != expected.get(key):
            differences.append(
                f"{path}.bounds.{key}: expected {expected.get(key)!r}, "
                f"got {actual.get(key)!r}"
            )


def _compare_patterns(
    actual: list[str],
    expected: list[str],
    path: str,
    differences: list[str],
) -> None:
    """Compare pattern lists."""
    actual_set = set(actual)
    expected_set = set(expected)
    if actual_set != expected_set:
        missing = expected_set - actual_set
        extra = actual_set - expected_set
        if missing:
            differences.append(f"{path}.patterns: missing {sorted(missing)}")
        if extra:
            differences.append(f"{path}.patterns: extra {sorted(extra)}")
