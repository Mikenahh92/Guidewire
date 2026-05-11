"""Sanity checks for the guidewire package."""

from guidewire import __version__


def test_version_is_pep440() -> None:
    """Version should follow PEP 440 format (e.g. 0.0.1.dev0)."""
    import re

    assert re.match(r"\d+\.\d+\.\d+(?:\.dev\d+)?", __version__)


def test_package_importable() -> None:
    """The guidewire package should be importable."""
    import guidewire  # noqa: F401
