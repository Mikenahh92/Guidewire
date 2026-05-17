"""Shared fixtures and markers for integration tests.

Registers the ``integration`` pytest marker with a skip condition based
on the ``GUIDEWARE_RUN_INTEGRATION`` environment variable.
"""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register the integration marker."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test (deselected unless "
        "GUIDEWARE_RUN_INTEGRATION=1)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip integration tests unless GUIDEWARE_RUN_INTEGRATION=1."""
    run_integration = os.environ.get("GUIDEWARE_RUN_INTEGRATION", "") in ("1", "true")
    for item in items:
        if "integration" in item.keywords and not run_integration:
            item.add_marker(
                pytest.mark.skip(
                    reason="integration tests skipped "
                    "(set GUIDEWARE_RUN_INTEGRATION=1)",
                )
            )
