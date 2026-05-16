"""Tests for the LinuxBackend skeleton (GW-028).

Validates:
- Module can be imported on any platform (guarded pyatspi import).
- LinuxBackend is a concrete subclass of DesktopBackend.
- Platform guard raises BackendUnavailableError on non-Linux systems.
- pyatspi-missing guard raises BackendUnavailableError.
- All 9 abstract methods are present and raise NotImplementedError.
- dispose() sets internal state without error.
"""

from unittest.mock import patch

import pytest

from guidewire.backends.base import DesktopBackend
from guidewire.backends.linux import LinuxBackend
from guidewire.errors import BackendUnavailableError

# ---------------------------------------------------------------------------
# Structural tests (run on any platform)
# ---------------------------------------------------------------------------


class TestLinuxBackendStructure:
    """Verify the LinuxBackend class shape."""

    def test_is_subclass_of_desktop_backend(self) -> None:
        """LinuxBackend must inherit from DesktopBackend."""
        assert issubclass(LinuxBackend, DesktopBackend)

    def test_concrete_class(self) -> None:
        """LinuxBackend must be instantiable (no unimplemented abstracts)."""
        # We can't instantiate it on non-Linux, so just verify it's not abstract
        assert not getattr(LinuxBackend, "__abstractmethods__", None)

    def test_exports_in_backends_package(self) -> None:
        """LinuxBackend must be re-exported from the backends package."""
        from guidewire.backends import LinuxBackend as ImportedLinuxBackend

        assert ImportedLinuxBackend is LinuxBackend

    def test_all_nine_abstract_methods_exist(self) -> None:
        """LinuxBackend must define all 9 abstract DesktopBackend methods."""
        expected = [
            "list_windows",
            "get_window_info",
            "focus_window",
            "snapshot",
            "find_elements",
            "perform_action",
            "get_element_info",
            "is_valid",
            "dispose",
        ]
        for method_name in expected:
            assert hasattr(LinuxBackend, method_name), (
                f"LinuxBackend missing method: {method_name}"
            )
            assert callable(getattr(LinuxBackend, method_name))


# ---------------------------------------------------------------------------
# Platform guard tests
# ---------------------------------------------------------------------------


class TestPlatformGuard:
    """Verify platform detection and pyatspi availability guards."""

    @patch("sys.platform", "win32")
    def test_raises_on_windows(self) -> None:
        """Must raise BackendUnavailableError on Windows."""
        with pytest.raises(BackendUnavailableError, match="Linux platform"):
            LinuxBackend()

    @patch("sys.platform", "darwin")
    def test_raises_on_macos(self) -> None:
        """Must raise BackendUnavailableError on macOS."""
        with pytest.raises(BackendUnavailableError, match="Linux platform"):
            LinuxBackend()

    @patch("sys.platform", "linux")
    def test_raises_when_pyatspi_missing(self) -> None:
        """Must raise BackendUnavailableError when pyatspi is not installed."""
        with (
            patch.dict("sys.modules", {"pyatspi": None}),
            pytest.raises(BackendUnavailableError, match="pyatspi"),
        ):
            LinuxBackend()

    @patch("sys.platform", "linux")
    def test_error_code_is_backend_unavailable(self) -> None:
        """Guard errors must use the backend_unavailable error code."""
        with (
            patch.dict("sys.modules", {"pyatspi": None}),
            pytest.raises(BackendUnavailableError) as exc_info,
        ):
            LinuxBackend()
        assert exc_info.value.error_code == "backend_unavailable"


# ---------------------------------------------------------------------------
# Stub method tests
# ---------------------------------------------------------------------------


class TestStubMethods:
    """Verify all 9 methods raise NotImplementedError before real implementation."""

    @pytest.fixture()
    def backend(self) -> LinuxBackend:
        """Create a LinuxBackend bypassing the platform guard."""
        with (
            patch("sys.platform", "linux"),
            patch.dict("sys.modules", {"pyatspi": type("mod", (), {})}),
        ):
            b = LinuxBackend.__new__(LinuxBackend)
            b._disposed = False
            return b

    def test_list_windows_raises_not_implemented(self, backend: LinuxBackend) -> None:
        with pytest.raises(NotImplementedError, match="list_windows"):
            backend.list_windows()

    def test_get_window_info_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="get_window_info"):
            backend.get_window_info(NativeHandle("fake"))

    def test_focus_window_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="focus_window"):
            backend.focus_window(NativeHandle("fake"))

    def test_snapshot_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="snapshot"):
            backend.snapshot(NativeHandle("fake"))

    def test_find_elements_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="find_elements"):
            backend.find_elements(NativeHandle("fake"), role="button")

    def test_perform_action_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import DesktopAction, NativeHandle

        with pytest.raises(NotImplementedError, match="perform_action"):
            backend.perform_action(NativeHandle("fake"), DesktopAction.CLICK)

    def test_get_element_info_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="get_element_info"):
            backend.get_element_info(NativeHandle("fake"))

    def test_is_valid_raises_not_implemented(self, backend: LinuxBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="is_valid"):
            backend.is_valid(NativeHandle("fake"))

    def test_dispose_sets_disposed_flag(self, backend: LinuxBackend) -> None:
        """dispose() must set _disposed to True without raising."""
        assert not backend._disposed
        backend.dispose()
        assert backend._disposed
