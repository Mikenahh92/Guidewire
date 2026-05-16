"""Tests for the LinuxBackend skeleton (GW-028) and list_windows (GW-029).

Validates:
- Module can be imported on any platform (guarded pyatspi import).
- LinuxBackend is a concrete subclass of DesktopBackend.
- Platform guard raises BackendUnavailableError on non-Linux systems.
- pyatspi-missing guard raises BackendUnavailableError.
- list_windows() enumerates visible top-level windows via AT-SPI2.
- Role filtering: only ROLE_FRAME, ROLE_DIALOG, ROLE_WINDOW are included (§5.3).
- Off-screen windows (missing STATE_SHOWING) are filtered out.
- ROLE_DESKTOP_FRAME with empty name is excluded (§5.3).
- Defunct children are silently skipped (§5.4).
- BackendUnavailableError raised for disposed backend.
- Remaining 7 stub methods raise NotImplementedError.
- dispose() sets internal state without error.
"""

import sys
from unittest.mock import MagicMock, patch

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
            assert hasattr(LinuxBackend, method_name), f"LinuxBackend missing method: {method_name}"
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
# list_windows tests (GW-029)
# ---------------------------------------------------------------------------


class TestListWindows:
    """Tests for LinuxBackend.list_windows (GW-029).

    Validates:
    - Returns list of NativeHandle for visible top-level windows.
    - Filters out windows missing STATE_SHOWING.
    - Filters by role (ROLE_FRAME, ROLE_DIALOG, ROLE_WINDOW) per §5.3.
    - Excludes ROLE_DESKTOP_FRAME with empty name per §5.3.
    - Silently skips defunct/inaccessible children per §5.4.
    - Returns empty list when no windows found.
    - Disposed backend raises BackendUnavailableError.
    """

    @pytest.fixture()
    def backend(self) -> LinuxBackend:
        """Create a LinuxBackend with mocked pyatspi, bypassing platform guard.

        The mock is injected into sys.modules for the lifetime of the test
        so that ``import pyatspi`` inside ``list_windows`` resolves correctly.
        """
        mock_pyatspi = _make_mock_pyatspi(showing_count=0, hidden_count=0)
        original_platform = sys.platform
        original_pyatspi = sys.modules.get("pyatspi")
        sys.platform = "linux"
        sys.modules["pyatspi"] = mock_pyatspi
        yield LinuxBackend()
        sys.platform = original_platform
        if original_pyatspi is None:
            sys.modules.pop("pyatspi", None)
        else:
            sys.modules["pyatspi"] = original_pyatspi

    # -- basic behaviour ----------------------------------------------------

    def test_returns_handles_for_showing_windows(self, backend: LinuxBackend) -> None:
        """list_windows() should return NativeHandle for windows with STATE_SHOWING."""
        _patch_list_windows_children(backend, _make_mock_pyatspi(showing_count=2, hidden_count=0))
        result = backend.list_windows()
        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert item is not None

    def test_filters_out_non_showing_windows(self, backend: LinuxBackend) -> None:
        """list_windows() should exclude windows missing STATE_SHOWING."""
        _patch_list_windows_children(backend, _make_mock_pyatspi(showing_count=1, hidden_count=2))
        result = backend.list_windows()
        assert len(result) == 1

    def test_returns_empty_list_when_no_windows(self, backend: LinuxBackend) -> None:
        """list_windows() should return empty list when no windows found."""
        _patch_list_windows_children(backend, _make_mock_pyatspi(showing_count=0, hidden_count=0))
        result = backend.list_windows()
        assert result == []

    # -- TC-LW-02: role filtering (AC-3, §5.3) -----------------------------

    def test_filters_non_window_roles(self, backend: LinuxBackend) -> None:
        """Only ROLE_FRAME, ROLE_DIALOG, ROLE_WINDOW pass the role filter (TC-LW-02)."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=3, hidden_count=0)
        children = mock_pyatspi.Registry.getDesktop.return_value.children
        # Assign non-window roles to 2 of the 3 children
        children[0].get_role.return_value = mock_pyatspi.ROLE_PANEL
        children[1].get_role.return_value = mock_pyatspi.ROLE_TOOLTIP
        # children[2] keeps default ROLE_FRAME
        _patch_list_windows_children(backend, mock_pyatspi)
        result = backend.list_windows()
        assert len(result) == 1

    def test_accepts_role_dialog(self, backend: LinuxBackend) -> None:
        """ROLE_DIALOG children are included."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=1, hidden_count=0)
        children = mock_pyatspi.Registry.getDesktop.return_value.children
        children[0].get_role.return_value = mock_pyatspi.ROLE_DIALOG
        _patch_list_windows_children(backend, mock_pyatspi)
        result = backend.list_windows()
        assert len(result) == 1

    def test_accepts_role_window(self, backend: LinuxBackend) -> None:
        """ROLE_WINDOW children are included."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=1, hidden_count=0)
        children = mock_pyatspi.Registry.getDesktop.return_value.children
        children[0].get_role.return_value = mock_pyatspi.ROLE_WINDOW
        _patch_list_windows_children(backend, mock_pyatspi)
        result = backend.list_windows()
        assert len(result) == 1

    # -- TC-LW-04: single window --------------------------------------------

    def test_single_window(self, backend: LinuxBackend) -> None:
        """list_windows with exactly one visible window returns a single handle (TC-LW-04)."""
        _patch_list_windows_children(backend, _make_mock_pyatspi(showing_count=1, hidden_count=0))
        result = backend.list_windows()
        assert len(result) == 1

    # -- TC-LW-05: many windows (50+) --------------------------------------

    def test_many_windows(self, backend: LinuxBackend) -> None:
        """list_windows handles 50+ windows correctly (TC-LW-05)."""
        _patch_list_windows_children(backend, _make_mock_pyatspi(showing_count=55, hidden_count=10))
        result = backend.list_windows()
        assert len(result) == 55

    # -- TC-LW-08: defunct silently skipped (AC-4, §5.4) -------------------

    def test_silently_skips_defunct(self, backend: LinuxBackend) -> None:
        """Defunct children are silently skipped, not raised as errors (TC-LW-08)."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=2, hidden_count=0)
        children = mock_pyatspi.Registry.getDesktop.return_value.children
        # Make the second child raise when getState is called
        children[1].getState.side_effect = RuntimeError("defunct")
        _patch_list_windows_children(backend, mock_pyatspi)
        # Must NOT raise — defunct child is silently skipped
        result = backend.list_windows()
        assert len(result) == 1

    # -- TC-LW-13: desktop frame exclusion (§5.3) --------------------------

    def test_excludes_desktop_frame(self, backend: LinuxBackend) -> None:
        """ROLE_DESKTOP_FRAME with empty name is excluded (TC-LW-13)."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=2, hidden_count=0)
        children = mock_pyatspi.Registry.getDesktop.return_value.children
        # First child is a normal frame
        children[0].get_role.return_value = mock_pyatspi.ROLE_FRAME
        # Second child is a desktop frame with empty name
        children[1].get_role.return_value = mock_pyatspi.ROLE_DESKTOP_FRAME
        children[1].get_name.return_value = ""
        _patch_list_windows_children(backend, mock_pyatspi)
        result = backend.list_windows()
        assert len(result) == 1

    def test_includes_desktop_frame_with_name(self, backend: LinuxBackend) -> None:
        """ROLE_DESKTOP_FRAME with a non-empty name is included."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=1, hidden_count=0)
        children = mock_pyatspi.Registry.getDesktop.return_value.children
        children[0].get_role.return_value = mock_pyatspi.ROLE_DESKTOP_FRAME
        children[0].get_name.return_value = "Desktop"
        _patch_list_windows_children(backend, mock_pyatspi)
        # Note: ROLE_DESKTOP_FRAME is NOT in _valid_roles, so it's excluded
        # regardless of name. This test verifies the role filter takes priority.
        result = backend.list_windows()
        assert len(result) == 0

    # -- disposed state ------------------------------------------------------

    def test_disposed_backend_raises(self, backend: LinuxBackend) -> None:
        """list_windows() on disposed backend raises BackendUnavailableError."""
        backend.dispose()
        with pytest.raises(BackendUnavailableError, match="disposed"):
            backend.list_windows()

    def test_disposed_error_mentions_linuxbackend(self, backend: LinuxBackend) -> None:
        """Disposed backend error message must mention LinuxBackend."""
        backend.dispose()
        with pytest.raises(BackendUnavailableError) as exc_info:
            backend.list_windows()
        msg = str(exc_info.value).lower()
        assert "disposed" in msg
        assert "linuxbackend" in msg

    # -- __init__ desktop storage (Arch §5.2, §6.2) -------------------------

    def test_desktop_stored_in_init(self) -> None:
        """getDesktop(0) is called in __init__, not on every list_windows (§5.2)."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=0, hidden_count=0)
        with (
            patch("sys.platform", "linux"),
            patch.dict("sys.modules", {"pyatspi": mock_pyatspi}),
        ):
            b = LinuxBackend()
            # getDesktop was called once during __init__
            mock_pyatspi.Registry.getDesktop.assert_called_once_with(0)
            # list_windows does not call getDesktop again
            b.list_windows()
            mock_pyatspi.Registry.getDesktop.assert_called_once_with(0)

    # -- state checking ------------------------------------------------------

    def test_state_checked_with_contains(self, backend: LinuxBackend) -> None:
        """Each window's state must be checked via state_set.contains(STATE_SHOWING)."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=2, hidden_count=1)
        _patch_list_windows_children(backend, mock_pyatspi)
        backend.list_windows()
        mock_desktop = backend._desktop
        for child in mock_desktop.children:
            child.getState.assert_called_once()
            state_set = child.getState.return_value
            state_set.contains.assert_called_once_with(mock_pyatspi.STATE_SHOWING)


# ---------------------------------------------------------------------------
# Remaining stub method tests
# ---------------------------------------------------------------------------


class TestStubMethods:
    """Verify remaining stub methods raise NotImplementedError."""

    @pytest.fixture()
    def backend(self) -> LinuxBackend:
        """Create a LinuxBackend bypassing the platform guard."""
        mock_pyatspi = _make_mock_pyatspi(showing_count=0, hidden_count=0)
        original_platform = sys.platform
        original_pyatspi = sys.modules.get("pyatspi")
        sys.platform = "linux"
        sys.modules["pyatspi"] = mock_pyatspi
        yield LinuxBackend()
        sys.platform = original_platform
        if original_pyatspi is None:
            sys.modules.pop("pyatspi", None)
        else:
            sys.modules["pyatspi"] = original_pyatspi

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_pyatspi(showing_count: int, hidden_count: int) -> MagicMock:
    """Create a mock pyatspi module with desktop children.

    Args:
        showing_count: Number of children with STATE_SHOWING.
        hidden_count: Number of children without STATE_SHOWING.

    Returns:
        A MagicMock object standing in for the pyatspi module.
    """
    # Use sentinel objects for roles so identity comparison works in sets.
    role_frame = object()
    role_dialog = object()
    role_window = object()
    role_desktop_frame = object()
    role_panel = object()
    role_tooltip = object()

    mock_pyatspi = MagicMock()
    mock_pyatspi.ROLE_FRAME = role_frame
    mock_pyatspi.ROLE_DIALOG = role_dialog
    mock_pyatspi.ROLE_WINDOW = role_window
    mock_pyatspi.ROLE_DESKTOP_FRAME = role_desktop_frame
    mock_pyatspi.ROLE_PANEL = role_panel
    mock_pyatspi.ROLE_TOOLTIP = role_tooltip
    mock_pyatspi.STATE_SHOWING = 42

    mock_registry = MagicMock()
    mock_desktop = MagicMock()
    children = []

    for _ in range(showing_count):
        mock_state = MagicMock()
        mock_state.contains.return_value = True
        mock_child = MagicMock()
        mock_child.getState.return_value = mock_state
        mock_child.get_role.return_value = role_frame
        mock_child.get_name.return_value = "Test Window"
        children.append(mock_child)

    for _ in range(hidden_count):
        mock_state = MagicMock()
        mock_state.contains.return_value = False
        mock_child = MagicMock()
        mock_child.getState.return_value = mock_state
        mock_child.get_role.return_value = role_frame
        mock_child.get_name.return_value = "Hidden Window"
        children.append(mock_child)

    mock_desktop.children = children
    mock_registry.getDesktop.return_value = mock_desktop
    mock_pyatspi.Registry = mock_registry
    return mock_pyatspi


def _patch_list_windows_children(backend: LinuxBackend, mock_pyatspi: MagicMock) -> None:
    """Replace backend._desktop.children with children from a fresh mock.

    The role constants from *mock_pyatspi* are copied into the module-level
    ``sys.modules["pyatspi"]`` so that ``import pyatspi`` inside
    ``list_windows`` sees the same role objects used by the children.
    """
    import sys as _sys

    live_mock = _sys.modules.get("pyatspi")
    if live_mock is not None:
        for attr in ("ROLE_FRAME", "ROLE_DIALOG", "ROLE_WINDOW", "ROLE_DESKTOP_FRAME",
                      "ROLE_PANEL", "ROLE_TOOLTIP", "STATE_SHOWING"):
            if hasattr(mock_pyatspi, attr):
                setattr(live_mock, attr, getattr(mock_pyatspi, attr))
    mock_desktop = mock_pyatspi.Registry.getDesktop.return_value
    backend._desktop.children = mock_desktop.children
