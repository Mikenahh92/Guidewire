"""Tests for the WindowsBackend (GW-019 skeleton).

Validates:
- Module can be imported on any platform (guarded comtypes import).
- WindowsBackend is a concrete subclass of DesktopBackend.
- Platform guard raises BackendUnavailableError on non-Windows systems.
- comtypes-missing guard raises BackendUnavailableError.
- 8 abstract methods raise NotImplementedError (remaining stubs).
- dispose() performs full COM cleanup and is idempotent.
- Constructor signature matches DesktopBackend contract.

Focus-window tests live in ``test_windows_focus_window.py`` (architecture §3.2).
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest

from guidewire.backends.base import DesktopBackend
from guidewire.backends.windows import WindowsBackend
from guidewire.errors import BackendUnavailableError

# ---------------------------------------------------------------------------
# Structural tests (run on any platform)
# ---------------------------------------------------------------------------


class TestWindowsBackendStructure:
    """Verify the WindowsBackend class shape."""

    def test_is_subclass_of_desktop_backend(self) -> None:
        """WindowsBackend must inherit from DesktopBackend."""
        assert issubclass(WindowsBackend, DesktopBackend)

    def test_concrete_class(self) -> None:
        """WindowsBackend must be instantiable (no unimplemented abstracts)."""
        # We can't instantiate it on non-Windows, so just verify it's not abstract
        assert not getattr(WindowsBackend, "__abstractmethods__", None)

    def test_exports_in_backends_package(self) -> None:
        """WindowsBackend must be re-exported from the backends package on win32."""
        with patch("sys.platform", "win32"):
            # Reload the __init__ to pick up the conditional import
            import importlib

            import guidewire.backends

            importlib.reload(guidewire.backends)
            if guidewire.backends.WindowsBackend is not None:
                assert guidewire.backends.WindowsBackend is WindowsBackend

    def test_all_nine_abstract_methods_exist(self) -> None:
        """WindowsBackend must define all 9 abstract DesktopBackend methods."""
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
            assert hasattr(WindowsBackend, method_name), (
                f"WindowsBackend missing method: {method_name}"
            )
            assert callable(getattr(WindowsBackend, method_name))

    # TC-WIN-006: Constructor signature must match DesktopBackend contract

    def test_constructor_signature_no_extra_params(self) -> None:
        """WindowsBackend.__init__ must accept only self (no extra params)."""
        sig = inspect.signature(WindowsBackend.__init__)
        params = list(sig.parameters.keys())
        assert params == ["self"], f"Expected only 'self', got {params}"


# ---------------------------------------------------------------------------
# Platform guard tests
# ---------------------------------------------------------------------------


class TestPlatformGuard:
    """Verify platform detection and comtypes availability guards."""

    @patch("sys.platform", "linux")
    def test_raises_on_linux(self) -> None:
        """Must raise BackendUnavailableError on Linux."""
        with pytest.raises(BackendUnavailableError, match="Windows platform"):
            WindowsBackend()

    @patch("sys.platform", "darwin")
    def test_raises_on_macos(self) -> None:
        """Must raise BackendUnavailableError on macOS."""
        with pytest.raises(BackendUnavailableError, match="Windows platform"):
            WindowsBackend()

    # TC-WIN-014: Error message must include the current platform

    @patch("sys.platform", "linux")
    def test_error_message_includes_platform(self) -> None:
        """Platform guard error message must include the current platform name."""
        with pytest.raises(BackendUnavailableError) as exc_info:
            WindowsBackend()
        assert "linux" in str(exc_info.value).lower()

    @patch("sys.platform", "win32")
    def test_raises_when_comtypes_missing(self) -> None:
        """Must raise BackendUnavailableError when comtypes is not installed."""
        with (
            patch.dict("sys.modules", {"comtypes": None}),
            pytest.raises(BackendUnavailableError, match="comtypes"),
        ):
            WindowsBackend()

    @patch("sys.platform", "win32")
    def test_error_code_is_backend_unavailable(self) -> None:
        """Guard errors must use the backend_unavailable error code."""
        with (
            patch.dict("sys.modules", {"comtypes": None}),
            pytest.raises(BackendUnavailableError) as exc_info,
        ):
            WindowsBackend()
        assert exc_info.value.error_code == "backend_unavailable"

    @patch("sys.platform", "win32")
    def test_error_message_mentions_windows_extra(self) -> None:
        """comtypes-missing error must mention the [windows] extra."""
        with (
            patch.dict("sys.modules", {"comtypes": None}),
            pytest.raises(BackendUnavailableError) as exc_info,
        ):
            WindowsBackend()
        assert "guidewire[windows]" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Stub method tests
# ---------------------------------------------------------------------------


class TestStubMethods:
    """Verify stub methods raise NotImplementedError (focus_window tested separately)."""

    @pytest.fixture()
    def backend(self) -> WindowsBackend:
        """Create a WindowsBackend bypassing the platform guard."""
        with (
            patch("sys.platform", "win32"),
            patch.dict("sys.modules", {"comtypes": type("mod", (), {})}),
        ):
            b = WindowsBackend.__new__(WindowsBackend)
            b._com_initialized = True
            b._uia = MagicMock()
            b._disposed = False
            return b

    def test_list_windows_raises_not_implemented(self, backend: WindowsBackend) -> None:
        with pytest.raises(NotImplementedError, match="list_windows"):
            backend.list_windows()

    def test_get_window_info_raises_not_implemented(self, backend: WindowsBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="get_window_info"):
            backend.get_window_info(NativeHandle("fake"))

    def test_snapshot_raises_not_implemented(self, backend: WindowsBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="snapshot"):
            backend.snapshot(NativeHandle("fake"))

    def test_find_elements_raises_not_implemented(self, backend: WindowsBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="find_elements"):
            backend.find_elements(NativeHandle("fake"), role="button")

    def test_perform_action_raises_not_implemented(self, backend: WindowsBackend) -> None:
        from guidewire.backends.types import DesktopAction, NativeHandle

        with pytest.raises(NotImplementedError, match="perform_action"):
            backend.perform_action(NativeHandle("fake"), DesktopAction.CLICK)

    def test_get_element_info_raises_not_implemented(self, backend: WindowsBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="get_element_info"):
            backend.get_element_info(NativeHandle("fake"))

    def test_is_valid_raises_not_implemented(self, backend: WindowsBackend) -> None:
        from guidewire.backends.types import NativeHandle

        with pytest.raises(NotImplementedError, match="is_valid"):
            backend.is_valid(NativeHandle("fake"))

    def test_dispose_sets_disposed_flag(self, backend: WindowsBackend) -> None:
        """dispose() must set _disposed to True without raising."""
        assert not backend._disposed
        backend.dispose()
        assert backend._disposed

    # TC-WIN-028: dispose() must set _com_initialized to False

    def test_dispose_clears_com_initialized(self, backend: WindowsBackend) -> None:
        """TC-WIN-028: dispose() must set _com_initialized to False."""
        assert backend._com_initialized is True
        backend.dispose()
        assert backend._com_initialized is False

    # TC-WIN-029: dispose() must set _uia to None

    def test_dispose_clears_uia_reference(self, backend: WindowsBackend) -> None:
        """TC-WIN-029: dispose() must set _uia to None."""
        assert backend._uia is not None
        backend.dispose()
        assert backend._uia is None

    def test_dispose_is_idempotent(self, backend: WindowsBackend) -> None:
        """dispose() must be safe to call multiple times."""
        backend.dispose()
        backend.dispose()  # second call should not raise
        assert backend._disposed is True
        assert backend._com_initialized is False
        assert backend._uia is None
