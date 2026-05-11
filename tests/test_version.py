"""Sanity checks for the guidewire package."""

from guidewire import __version__


def test_version_is_semver() -> None:
    """Version should follow major.minor.patch format."""
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_package_importable() -> None:
    """The guidewire package should be importable."""
    import guidewire  # noqa: F401
