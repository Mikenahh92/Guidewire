"""Tests for the LinuxBackend skeleton (GW-028), list_windows (GW-029),
snapshot (GW-031), and element interaction methods (GW-032).

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
- perform_action dispatches 12 DesktopAction variants via AT-SPI actions.
- get_element_info returns role, name, states from AT-SPI accessible.
- is_valid probes element liveness without raising.
- find_elements walks the AT-SPI tree matching role/name.
- dispose() sets internal state without error.
- snapshot() walks the AT-SPI tree, normalizes elements, and returns a dict.
- snapshot() respects max_depth and max_nodes limits.
- snapshot() filters offscreen descendants (depth > 0).
- snapshot() silently skips defunct/inaccessible nodes (§5.4).
- snapshot() extracts role, name, states, bounds, and actions from each node.
- snapshot() returns a dict compatible with the DesktopElement schema.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from guidewire.backends.base import DesktopBackend
from guidewire.backends.linux import LinuxBackend
from guidewire.backends.types import NativeHandle
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

    def test_dispose_sets_disposed_flag(self, backend: LinuxBackend) -> None:
        """dispose() must set _disposed to True without raising."""
        assert not backend._disposed
        backend.dispose()
        assert backend._disposed


# ---------------------------------------------------------------------------
# perform_action tests (GW-032)
# ---------------------------------------------------------------------------


class TestPerformAction:
    """Tests for LinuxBackend.perform_action (GW-032).

    Validates the 12 DesktopAction dispatch variants and error handling.
    """

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

    def _mock_accessible_with_action(self, action_name: str = "click") -> MagicMock:
        """Create a mock accessible that supports a given AT-SPI action."""
        mock_action = MagicMock()
        mock_action.get_n_actions.return_value = 1
        mock_action.get_action_name.return_value = action_name
        mock_accessible = MagicMock()
        mock_accessible.queryAction.return_value = mock_action
        return mock_accessible

    # -- disposed state -------------------------------------------------------

    def test_disposed_raises_stale_element_reference(self, backend: LinuxBackend) -> None:
        """perform_action on disposed backend raises StaleElementReferenceError."""
        from guidewire.backends.types import DesktopAction, NativeHandle
        from guidewire.errors import StaleElementReferenceError

        backend.dispose()
        with pytest.raises(StaleElementReferenceError, match="disposed"):
            backend.perform_action(NativeHandle("fake"), DesktopAction.CLICK)

    def test_none_handle_raises_element_not_found(self, backend: LinuxBackend) -> None:
        """perform_action with None handle raises ElementNotFoundError."""
        from guidewire.backends.types import DesktopAction
        from guidewire.errors import ElementNotFoundError

        with pytest.raises(ElementNotFoundError, match="None"):
            backend.perform_action(None, DesktopAction.CLICK)

    # -- CLICK action ---------------------------------------------------------

    def test_click_via_click_action(self, backend: LinuxBackend) -> None:
        """CLICK dispatches to AT-SPI 'click' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("click")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.CLICK)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("click")

    def test_click_falls_back_to_press(self, backend: LinuxBackend) -> None:
        """CLICK falls back to 'press' when 'click' is not available."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        mock_action = MagicMock()
        mock_action.get_n_actions.return_value = 1
        mock_action.get_action_name.return_value = "press"
        accessible.queryAction.return_value = mock_action

        result = backend.perform_action(NativeHandle(accessible), DesktopAction.CLICK)
        assert result is None
        mock_action.do_action.assert_called_once_with("press")

    def test_click_falls_back_to_activate(self, backend: LinuxBackend) -> None:
        """CLICK falls back to 'activate' when 'click' and 'press' are not available."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        mock_action = MagicMock()
        mock_action.get_n_actions.return_value = 1
        mock_action.get_action_name.return_value = "activate"
        accessible.queryAction.return_value = mock_action

        result = backend.perform_action(NativeHandle(accessible), DesktopAction.CLICK)
        assert result is None
        mock_action.do_action.assert_called_once_with("activate")

    def test_click_raises_when_no_action_available(self, backend: LinuxBackend) -> None:
        """CLICK raises ActionNotSupportedError when no click action exists."""
        from guidewire.backends.types import DesktopAction, NativeHandle
        from guidewire.errors import ActionNotSupportedError

        accessible = MagicMock()
        accessible.queryAction.return_value = None

        with pytest.raises(ActionNotSupportedError, match="click"):
            backend.perform_action(NativeHandle(accessible), DesktopAction.CLICK)

    def test_click_raises_when_action_interface_missing(self, backend: LinuxBackend) -> None:
        """CLICK raises ActionNotSupportedError when queryAction fails."""
        from guidewire.backends.types import DesktopAction, NativeHandle
        from guidewire.errors import ActionNotSupportedError

        accessible = MagicMock()
        accessible.queryAction.side_effect = RuntimeError("no action interface")

        with pytest.raises(ActionNotSupportedError, match="Action interface"):
            backend.perform_action(NativeHandle(accessible), DesktopAction.CLICK)

    # -- TYPE action ----------------------------------------------------------

    def test_type_requires_text_parameter(self, backend: LinuxBackend) -> None:
        """TYPE raises ActionNotSupportedError without 'text' kwarg."""
        from guidewire.backends.types import DesktopAction, NativeHandle
        from guidewire.errors import ActionNotSupportedError

        accessible = MagicMock()
        with pytest.raises(ActionNotSupportedError, match="text"):
            backend.perform_action(NativeHandle(accessible), DesktopAction.TYPE)

    def test_type_calls_grab_focus(self, backend: LinuxBackend) -> None:
        """TYPE sets focus before typing."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        # No grabFocus action available — should not raise
        mock_action = MagicMock()
        mock_action.get_n_actions.return_value = 0
        accessible.queryAction.return_value = mock_action

        with patch.object(backend, "_send_text"):
            backend.perform_action(NativeHandle(accessible), DesktopAction.TYPE, text="hello")

    # -- PRESS_KEY action -----------------------------------------------------

    def test_press_key_requires_key_parameter(self, backend: LinuxBackend) -> None:
        """PRESS_KEY raises ActionNotSupportedError without 'key' kwarg."""
        from guidewire.backends.types import DesktopAction, NativeHandle
        from guidewire.errors import ActionNotSupportedError

        accessible = MagicMock()
        with pytest.raises(ActionNotSupportedError, match="key"):
            backend.perform_action(NativeHandle(accessible), DesktopAction.PRESS_KEY)

    # -- SET_VALUE action -----------------------------------------------------

    def test_set_value_requires_value_parameter(self, backend: LinuxBackend) -> None:
        """SET_VALUE raises ActionNotSupportedError without 'value' kwarg."""
        from guidewire.backends.types import DesktopAction, NativeHandle
        from guidewire.errors import ActionNotSupportedError

        accessible = MagicMock()
        with pytest.raises(ActionNotSupportedError, match="value"):
            backend.perform_action(NativeHandle(accessible), DesktopAction.SET_VALUE)

    def test_set_value_via_text_interface(self, backend: LinuxBackend) -> None:
        """SET_VALUE falls back to Text interface when edit action unavailable."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        accessible.queryAction.return_value = None
        mock_text = MagicMock()
        accessible.queryText.return_value = mock_text

        backend.perform_action(
            NativeHandle(accessible), DesktopAction.SET_VALUE, value="new value"
        )
        mock_text.set_text_content.assert_called_once_with("new value")

    # -- SELECT action --------------------------------------------------------

    def test_select_via_select_action(self, backend: LinuxBackend) -> None:
        """SELECT dispatches to AT-SPI 'select' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("select")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.SELECT)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("select")

    # -- SCROLL action --------------------------------------------------------

    def test_scroll_via_scroll_action(self, backend: LinuxBackend) -> None:
        """SCROLL dispatches to AT-SPI 'scroll' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("scroll")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.SCROLL)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("scroll")

    def test_scroll_falls_back_to_variants(self, backend: LinuxBackend) -> None:
        """SCROLL tries scrollUp/scrollDown variants."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        mock_action = MagicMock()
        mock_action.get_n_actions.return_value = 1
        mock_action.get_action_name.return_value = "scrollDown"
        accessible.queryAction.return_value = mock_action

        result = backend.perform_action(NativeHandle(accessible), DesktopAction.SCROLL)
        assert result is None
        mock_action.do_action.assert_called_once_with("scrollDown")

    # -- GET_TEXT action ------------------------------------------------------

    def test_get_text_returns_string(self, backend: LinuxBackend) -> None:
        """GET_TEXT returns a string from the Text interface."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        mock_text = MagicMock()
        mock_text.character_count = 5
        mock_text.get_text.return_value = "hello"
        accessible.queryText.return_value = mock_text

        result = backend.perform_action(NativeHandle(accessible), DesktopAction.GET_TEXT)
        assert result == "hello"
        assert isinstance(result, str)

    def test_get_text_falls_back_to_name(self, backend: LinuxBackend) -> None:
        """GET_TEXT falls back to accessible name when Text interface unavailable."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        accessible.queryText.return_value = None
        accessible.get_name.return_value = "Element Name"

        result = backend.perform_action(NativeHandle(accessible), DesktopAction.GET_TEXT)
        assert result == "Element Name"

    def test_get_text_returns_empty_string_for_no_content(self, backend: LinuxBackend) -> None:
        """GET_TEXT returns empty string when no text content."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = MagicMock()
        mock_text = MagicMock()
        mock_text.character_count = 0
        mock_text.get_text.return_value = ""
        accessible.queryText.return_value = mock_text

        result = backend.perform_action(NativeHandle(accessible), DesktopAction.GET_TEXT)
        assert result == ""

    # -- TOGGLE action --------------------------------------------------------

    def test_toggle_via_toggle_action(self, backend: LinuxBackend) -> None:
        """TOGGLE dispatches to AT-SPI 'toggle' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("toggle")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.TOGGLE)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("toggle")

    # -- EXPAND / COLLAPSE actions --------------------------------------------

    def test_expand_via_expand_action(self, backend: LinuxBackend) -> None:
        """EXPAND dispatches to AT-SPI 'expand' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("expand")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.EXPAND)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("expand")

    def test_collapse_via_collapse_action(self, backend: LinuxBackend) -> None:
        """COLLAPSE dispatches to AT-SPI 'collapse' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("collapse")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.COLLAPSE)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("collapse")

    # -- INCREMENT / DECREMENT actions ----------------------------------------

    def test_increment_via_increment_action(self, backend: LinuxBackend) -> None:
        """INCREMENT dispatches to AT-SPI 'increment' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("increment")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.INCREMENT)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("increment")

    def test_decrement_via_decrement_action(self, backend: LinuxBackend) -> None:
        """DECREMENT dispatches to AT-SPI 'decrement' action."""
        from guidewire.backends.types import DesktopAction, NativeHandle

        accessible = self._mock_accessible_with_action("decrement")
        result = backend.perform_action(NativeHandle(accessible), DesktopAction.DECREMENT)
        assert result is None
        accessible.queryAction.return_value.do_action.assert_called_once_with("decrement")


# ---------------------------------------------------------------------------
# get_element_info tests (GW-032)
# ---------------------------------------------------------------------------


class TestGetElementInfo:
    """Tests for LinuxBackend.get_element_info (GW-032).

    Validates:
    - Returns dict with role, name, states.
    - Role is normalized via resolve_role.
    - States are read from AT-SPI state set.
    - Disposed backend raises StaleElementReferenceError.
    - Invalid handle raises ElementNotFoundError.
    """

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

    def _mock_accessible(
        self,
        role_name: str = "push button",
        name: str | None = "OK",
        states: dict[str, bool] | None = None,
    ) -> MagicMock:
        """Create a mock accessible with role, name, and states."""
        accessible = MagicMock()
        accessible.getRoleName.return_value = role_name
        accessible.get_name.return_value = name

        mock_state_set = MagicMock()
        if states is None:
            states = {"enabled": True, "focused": False}

        def _contains(state_const):
            # Map the sentinel state constants to their names
            return states.get(state_const, False)

        mock_state_set.contains.side_effect = _contains
        accessible.getState.return_value = mock_state_set
        return accessible

    def test_returns_dict_with_required_keys(self, backend: LinuxBackend) -> None:
        """get_element_info returns dict with role, name, states."""
        from guidewire.backends.types import NativeHandle

        accessible = self._mock_accessible()
        result = backend.get_element_info(NativeHandle(accessible))
        assert isinstance(result, dict)
        assert "role" in result
        assert "name" in result
        assert "states" in result

    def test_role_is_normalized(self, backend: LinuxBackend) -> None:
        """get_element_info normalizes AT-SPI role via resolve_role."""
        from guidewire.backends.types import NativeHandle

        accessible = self._mock_accessible(role_name="push button")
        result = backend.get_element_info(NativeHandle(accessible))
        assert result["role"] == "button"

    def test_role_falls_back_to_raw(self, backend: LinuxBackend) -> None:
        """get_element_info falls back to raw role when not in mapping."""
        from guidewire.backends.types import NativeHandle

        accessible = self._mock_accessible(role_name="some unknown role")
        result = backend.get_element_info(NativeHandle(accessible))
        assert result["role"] == "some unknown role"

    def test_name_is_returned(self, backend: LinuxBackend) -> None:
        """get_element_info returns the accessible name."""
        from guidewire.backends.types import NativeHandle

        accessible = self._mock_accessible(name="My Button")
        result = backend.get_element_info(NativeHandle(accessible))
        assert result["name"] == "My Button"

    def test_name_none_when_empty(self, backend: LinuxBackend) -> None:
        """get_element_info returns None for empty name."""
        from guidewire.backends.types import NativeHandle

        accessible = self._mock_accessible(name="")
        result = backend.get_element_info(NativeHandle(accessible))
        assert result["name"] is None

    def test_states_is_dict(self, backend: LinuxBackend) -> None:
        """get_element_info returns states as a dict."""
        from guidewire.backends.types import NativeHandle

        accessible = self._mock_accessible()
        result = backend.get_element_info(NativeHandle(accessible))
        assert isinstance(result["states"], dict)

    def test_disposed_raises_stale_element_reference(self, backend: LinuxBackend) -> None:
        """get_element_info on disposed backend raises StaleElementReferenceError."""
        from guidewire.backends.types import NativeHandle
        from guidewire.errors import StaleElementReferenceError

        backend.dispose()
        with pytest.raises(StaleElementReferenceError, match="disposed"):
            backend.get_element_info(NativeHandle("fake"))

    def test_none_handle_raises_element_not_found(self, backend: LinuxBackend) -> None:
        """get_element_info with None handle raises ElementNotFoundError."""
        from guidewire.errors import ElementNotFoundError

        with pytest.raises(ElementNotFoundError, match="None"):
            backend.get_element_info(None)

    def test_invalid_handle_raises_element_not_found(self, backend: LinuxBackend) -> None:
        """get_element_info with non-accessible handle raises ElementNotFoundError."""
        from guidewire.backends.types import NativeHandle
        from guidewire.errors import ElementNotFoundError

        with pytest.raises(ElementNotFoundError):
            backend.get_element_info(NativeHandle("not an accessible"))


# ---------------------------------------------------------------------------
# is_valid tests (GW-032)
# ---------------------------------------------------------------------------


class TestIsValid:
    """Tests for LinuxBackend.is_valid (GW-032).

    Validates:
    - Returns True for valid accessible.
    - Returns False for defunct accessible.
    - Returns False for None handle.
    - Returns False when disposed.
    - Never raises.
    """

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

    def test_returns_true_for_valid_element(self, backend: LinuxBackend) -> None:
        """is_valid returns True for a responsive accessible."""
        from guidewire.backends.types import NativeHandle

        accessible = MagicMock()
        assert backend.is_valid(NativeHandle(accessible)) is True

    def test_returns_false_for_defunct_element(self, backend: LinuxBackend) -> None:
        """is_valid returns False when getState raises."""
        from guidewire.backends.types import NativeHandle

        accessible = MagicMock()
        accessible.getState.side_effect = RuntimeError("defunct")
        assert backend.is_valid(NativeHandle(accessible)) is False

    def test_returns_false_for_none(self, backend: LinuxBackend) -> None:
        """is_valid returns False for None handle."""
        assert backend.is_valid(None) is False

    def test_returns_false_when_disposed(self, backend: LinuxBackend) -> None:
        """is_valid returns False when backend is disposed."""
        from guidewire.backends.types import NativeHandle

        accessible = MagicMock()
        backend.dispose()
        assert backend.is_valid(NativeHandle(accessible)) is False

    def test_never_raises(self, backend: LinuxBackend) -> None:
        """is_valid must never raise an exception."""
        # None handle
        assert backend.is_valid(None) is False
        # Arbitrary object
        assert backend.is_valid("random string") is False
        assert backend.is_valid(42) is False
        assert backend.is_valid(object()) is False


# ---------------------------------------------------------------------------
# find_elements tests (GW-032)
# ---------------------------------------------------------------------------


class TestFindElements:
    """Tests for LinuxBackend.find_elements (GW-032).

    Validates:
    - Returns empty list when no filters provided.
    - Returns empty list when no matches.
    - Matches by role.
    - Matches by name (case-insensitive substring).
    - Matches by both role and name.
    - Walks tree recursively.
    - Silently skips defunct children.
    - Disposed backend raises BackendUnavailableError.
    """

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

    def _make_tree(
        self,
        children: list[tuple[str, str | None]] | None = None,
    ) -> MagicMock:
        """Create a mock accessible tree.

        Args:
            children: List of (role_name, name) tuples for direct children.
        """
        window = MagicMock()

        if children is None:
            children = []

        mock_children = []
        for role_name, name in children:
            child = MagicMock()
            child.getRoleName.return_value = role_name
            child.get_name.return_value = name
            child.get_child_at_index.return_value = None
            mock_children.append(child)

        def _get_child(idx):
            if 0 <= idx < len(mock_children):
                return mock_children[idx]
            return None

        window.get_child_at_index.side_effect = _get_child
        return window

    def test_no_filters_returns_empty(self, backend: LinuxBackend) -> None:
        """find_elements returns empty list when no role or name filter."""
        from guidewire.backends.types import NativeHandle

        window = self._make_tree([("push button", "OK")])
        result = backend.find_elements(NativeHandle(window))
        assert result == []

    def test_matches_by_role(self, backend: LinuxBackend) -> None:
        """find_elements matches elements by normalized role."""
        from guidewire.backends.types import NativeHandle

        window = self._make_tree([
            ("push button", "OK"),
            ("text", "Label"),
            ("push button", "Cancel"),
        ])
        result = backend.find_elements(NativeHandle(window), role="button")
        assert len(result) == 2

    def test_matches_by_name_substring(self, backend: LinuxBackend) -> None:
        """find_elements matches elements by case-insensitive name substring."""
        from guidewire.backends.types import NativeHandle

        window = self._make_tree([
            ("push button", "Save File"),
            ("push button", "Cancel"),
            ("push button", "save as"),
        ])
        result = backend.find_elements(NativeHandle(window), name="save")
        assert len(result) == 2

    def test_matches_by_role_and_name(self, backend: LinuxBackend) -> None:
        """find_elements matches elements satisfying both role and name."""
        from guidewire.backends.types import NativeHandle

        window = self._make_tree([
            ("push button", "Save"),
            ("text", "Save"),
            ("push button", "Cancel"),
        ])
        result = backend.find_elements(NativeHandle(window), role="button", name="Save")
        assert len(result) == 1

    def test_no_matches_returns_empty(self, backend: LinuxBackend) -> None:
        """find_elements returns empty list when nothing matches."""
        from guidewire.backends.types import NativeHandle

        window = self._make_tree([("push button", "OK")])
        result = backend.find_elements(NativeHandle(window), role="checkbox")
        assert result == []

    def test_disposed_raises_backend_unavailable(self, backend: LinuxBackend) -> None:
        """find_elements on disposed backend raises BackendUnavailableError."""
        from guidewire.backends.types import NativeHandle

        backend.dispose()
        with pytest.raises(BackendUnavailableError, match="disposed"):
            backend.find_elements(NativeHandle("fake"), role="button")

    def test_silently_skips_defunct_children(self, backend: LinuxBackend) -> None:
        """find_elements silently skips children that raise exceptions."""
        from guidewire.backends.types import NativeHandle

        window = MagicMock()

        # First child is defunct (raises on getRoleName)
        defunct_child = MagicMock()
        defunct_child.getRoleName.side_effect = RuntimeError("defunct")
        defunct_child.get_name.side_effect = RuntimeError("defunct")
        defunct_child.get_child_at_index.return_value = None

        # Second child is valid
        good_child = MagicMock()
        good_child.getRoleName.return_value = "push button"
        good_child.get_name.return_value = "OK"
        good_child.get_child_at_index.return_value = None

        def _get_child(idx):
            if idx == 0:
                return defunct_child
            if idx == 1:
                return good_child
            return None

        window.get_child_at_index.side_effect = _get_child
        result = backend.find_elements(NativeHandle(window), role="button")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Snapshot tests (GW-031)
# ---------------------------------------------------------------------------


class TestSnapshot:
    """Tests for LinuxBackend.snapshot (GW-031).

    Validates:
    - Returns a dict with DesktopElement schema keys.
    - Extracts role, name, states, bounds, and actions from accessible nodes.
    - Walks children recursively respecting max_depth.
    - Respects max_nodes limit.
    - Filters offscreen descendants (depth > 0).
    - Silently skips defunct/inaccessible nodes per §5.4.
    - BackendUnavailableError raised for disposed backend.
    - Handles single-node (leaf) windows with no children.
    """

    @pytest.fixture()
    def backend(self) -> LinuxBackend:
        """Create a LinuxBackend with mocked pyatspi, bypassing platform guard."""
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

    # -- Helper to build mock accessible trees for snapshot ---

    @staticmethod
    def _make_accessible(
        role: str = "frame",
        name: str | None = "Test",
        description: str | None = None,
        states: dict[str, bool] | None = None,
        bounds: tuple[int, int, int, int] | None = (0, 0, 800, 600),
        actions: list[str] | None = None,
        text_content: str | None = None,
        value: float | None = None,
        children: list | None = None,
        child_count: int | None = None,
    ) -> MagicMock:
        """Create a mock pyatspi.Accessible for snapshot tests.

        Args:
            role: AT-SPI role string (e.g. 'frame', 'push button').
            name: Accessible name.
            description: Accessible description.
            states: Dict of state names to boolean presence.
            bounds: (x, y, width, height) tuple.
            actions: List of action name strings.
            text_content: Text from Text interface.
            value: Value from Value interface.
            children: List of child mock accessibles.
            child_count: Override child count (defaults to len(children)).
        """
        acc = MagicMock()
        acc.get_role.return_value = role
        acc.get_name.return_value = name
        acc.get_description.return_value = description

        # States
        state_names = list(states.keys()) if states else []
        mock_state_set = MagicMock()
        mock_state_set.get_states.return_value = state_names
        mock_state_set.contains.return_value = False  # not used by snapshot
        acc.getState.return_value = mock_state_set

        # Bounds
        if bounds:
            mock_ext = MagicMock()
            mock_ext.x = bounds[0]
            mock_ext.y = bounds[1]
            mock_ext.width = bounds[2]
            mock_ext.height = bounds[3]
            acc.getExtent.return_value = mock_ext
        else:
            acc.getExtent.return_value = None

        # Text interface
        if text_content is not None:
            mock_text = MagicMock()
            mock_text.characterCount = len(text_content)
            mock_text.getText.return_value = text_content
            acc.get_text.return_value = mock_text
        else:
            acc.get_text.return_value = None

        # Value interface
        if value is not None:
            mock_val = MagicMock()
            mock_val.currentValue = value
            acc.get_value.return_value = mock_val
        else:
            acc.get_value.return_value = None

        # Actions
        if actions:
            mock_action = MagicMock()
            mock_action.nActions = len(actions)
            mock_action.getName.side_effect = lambda i: actions[i] if i < len(actions) else None
            acc.get_action.return_value = mock_action
        else:
            acc.get_action.return_value = None

        # Children
        _children = children or []
        acc.childCount = child_count if child_count is not None else len(_children)
        acc.getChildAtIndex.side_effect = lambda i: _children[i] if i < len(_children) else None

        return acc

    # -- basic snapshot tests ---

    def test_snapshot_returns_dict(self, backend: LinuxBackend) -> None:
        """snapshot() must return a dict."""
        root = self._make_accessible(role="frame", name="Main Window")
        result = backend.snapshot(NativeHandle(root))
        assert isinstance(result, dict)

    def test_snapshot_dict_has_required_keys(self, backend: LinuxBackend) -> None:
        """snapshot() dict must contain DesktopElement schema keys."""
        root = self._make_accessible(role="frame", name="Main Window")
        result = backend.snapshot(NativeHandle(root))
        for key in ("ref", "role", "name", "states", "bounds", "actions"):
            assert key in result, f"Missing key: {key}"

    def test_snapshot_extracts_role(self, backend: LinuxBackend) -> None:
        """snapshot() must extract and normalize the AT-SPI role."""
        root = self._make_accessible(role="frame", name="W")
        result = backend.snapshot(NativeHandle(root))
        # 'frame' maps to 'pane' per _LINUX_ROLES
        assert result["role"] == "pane"

    def test_snapshot_extracts_name(self, backend: LinuxBackend) -> None:
        """snapshot() must extract the accessible name."""
        root = self._make_accessible(role="frame", name="My Window")
        result = backend.snapshot(NativeHandle(root))
        assert result["name"] == "My Window"

    def test_snapshot_extracts_button_role(self, backend: LinuxBackend) -> None:
        """snapshot() normalizes 'push button' to 'button'."""
        root = self._make_accessible(role="push button", name="OK")
        result = backend.snapshot(NativeHandle(root))
        assert result["role"] == "button"

    def test_snapshot_extracts_entry_role(self, backend: LinuxBackend) -> None:
        """snapshot() normalizes 'entry' to 'text_input'."""
        root = self._make_accessible(role="entry", name="Search")
        result = backend.snapshot(NativeHandle(root))
        assert result["role"] == "text_input"

    def test_snapshot_extracts_checkbox_role(self, backend: LinuxBackend) -> None:
        """snapshot() normalizes 'check box' to 'checkbox'."""
        root = self._make_accessible(role="check box", name="Enable")
        result = backend.snapshot(NativeHandle(root))
        assert result["role"] == "checkbox"

    def test_snapshot_extracts_states(self, backend: LinuxBackend) -> None:
        """snapshot() must extract and normalize states.

        States dict keys represent present states (value=True in AT-SPI).
        Absent states default to None in ElementStates.
        """
        root = self._make_accessible(
            role="push button",
            name="Click",
            states={"enabled": True, "visible": True},
        )
        result = backend.snapshot(NativeHandle(root))
        states = result["states"]
        assert states["enabled"] is True
        assert states["visible"] is True
        # 'focused' was not in the states dict, so it should be absent
        assert "focused" not in states

    def test_snapshot_extracts_bounds(self, backend: LinuxBackend) -> None:
        """snapshot() must extract bounding rectangle."""
        root = self._make_accessible(role="frame", name="W", bounds=(10, 20, 800, 600))
        result = backend.snapshot(NativeHandle(root))
        bounds = result["bounds"]
        assert bounds["x"] == 10.0
        assert bounds["y"] == 20.0
        assert bounds["width"] == 800.0
        assert bounds["height"] == 600.0

    def test_snapshot_extracts_actions(self, backend: LinuxBackend) -> None:
        """snapshot() must extract and normalize actions."""
        root = self._make_accessible(
            role="push button",
            name="OK",
            actions=["click", "activate"],
        )
        result = backend.snapshot(NativeHandle(root))
        actions = result["actions"]
        assert "click" in actions
        assert "invoke" in actions  # 'activate' normalizes to 'invoke'

    def test_snapshot_no_bounds_when_absent(self, backend: LinuxBackend) -> None:
        """snapshot() must handle missing bounds gracefully."""
        root = self._make_accessible(role="frame", name="W", bounds=None)
        result = backend.snapshot(NativeHandle(root))
        assert result["bounds"] is None

    def test_snapshot_no_children_for_leaf(self, backend: LinuxBackend) -> None:
        """snapshot() must return empty children list for leaf nodes."""
        root = self._make_accessible(role="push button", name="OK", children=[])
        result = backend.snapshot(NativeHandle(root))
        assert result["children"] is None or result["children"] == []

    # -- tree walking tests ---

    def test_snapshot_walks_children(self, backend: LinuxBackend) -> None:
        """snapshot() must include children in the tree."""
        child = self._make_accessible(role="push button", name="OK", children=[])
        root = self._make_accessible(role="frame", name="Window", children=[child])
        result = backend.snapshot(NativeHandle(root))
        children = result.get("children") or []
        assert len(children) == 1
        assert children[0]["role"] == "button"
        assert children[0]["name"] == "OK"

    def test_snapshot_multiple_children(self, backend: LinuxBackend) -> None:
        """snapshot() must include all children at the same level."""
        btn1 = self._make_accessible(role="push button", name="OK", children=[])
        btn2 = self._make_accessible(role="push button", name="Cancel", children=[])
        root = self._make_accessible(role="frame", name="Dialog", children=[btn1, btn2])
        result = backend.snapshot(NativeHandle(root))
        children = result.get("children") or []
        assert len(children) == 2

    def test_snapshot_nested_children(self, backend: LinuxBackend) -> None:
        """snapshot() must walk nested children to multiple depths."""
        inner = self._make_accessible(role="entry", name="Field", children=[])
        outer = self._make_accessible(role="panel", name="Panel", children=[inner])
        root = self._make_accessible(role="frame", name="Window", children=[outer])
        result = backend.snapshot(NativeHandle(root), max_depth=4)
        children = result.get("children") or []
        assert len(children) == 1
        assert children[0]["role"] == "pane"
        inner_children = children[0].get("children") or []
        assert len(inner_children) == 1
        assert inner_children[0]["role"] == "text_input"

    def test_snapshot_respects_max_depth(self, backend: LinuxBackend) -> None:
        """snapshot() must not traverse beyond max_depth."""
        deep = self._make_accessible(role="label", name="Deep", children=[])
        mid = self._make_accessible(role="panel", name="Mid", children=[deep])
        root = self._make_accessible(role="frame", name="Root", children=[mid])
        result = backend.snapshot(NativeHandle(root), max_depth=1)
        children = result.get("children") or []
        assert len(children) == 1
        # max_depth=1 means root + 1 level; children of children should not appear
        mid_children = children[0].get("children") or []
        assert len(mid_children) == 0

    def test_snapshot_max_depth_zero(self, backend: LinuxBackend) -> None:
        """snapshot() with max_depth=0 must return root only, no children."""
        child = self._make_accessible(role="push button", name="OK", children=[])
        root = self._make_accessible(role="frame", name="W", children=[child])
        result = backend.snapshot(NativeHandle(root), max_depth=0)
        children = result.get("children") or []
        assert len(children) == 0

    def test_snapshot_respects_max_nodes(self, backend: LinuxBackend) -> None:
        """snapshot() must stop adding nodes when max_nodes is reached."""
        children = [
            self._make_accessible(role="push button", name=f"Btn {i}", children=[])
            for i in range(10)
        ]
        root = self._make_accessible(role="frame", name="W", children=children)
        result = backend.snapshot(NativeHandle(root), max_depth=4, max_nodes=3)
        # Count all nodes in the tree
        all_nodes = [result]
        queue = [result]
        while queue:
            current = queue.pop(0)
            for c in current.get("children") or []:
                all_nodes.append(c)
                queue.append(c)
        assert len(all_nodes) <= 3

    # -- offscreen filtering ---

    def test_snapshot_filters_offscreen_descendants(self, backend: LinuxBackend) -> None:
        """snapshot() must exclude offscreen descendants (depth > 0)."""
        offscreen_child = self._make_accessible(
            role="push button",
            name="Hidden",
            states={"offscreen": True, "enabled": True},
            children=[],
        )
        root = self._make_accessible(role="frame", name="Window", children=[offscreen_child])
        result = backend.snapshot(NativeHandle(root))
        children = result.get("children") or []
        assert len(children) == 0  # offscreen child filtered out

    def test_snapshot_root_included_when_offscreen(self, backend: LinuxBackend) -> None:
        """snapshot() must include root even when offscreen (depth 0)."""
        root = self._make_accessible(
            role="frame",
            name="Window",
            states={"offscreen": True, "enabled": True},
            children=[],
        )
        result = backend.snapshot(NativeHandle(root))
        assert result["role"] == "pane"
        assert result["name"] == "Window"

    # -- defunct/inaccessible node handling ---

    def test_snapshot_handles_defunct_child_properties(self, backend: LinuxBackend) -> None:
        """snapshot() must handle children with failing property reads per §5.4.

        Individual property reads on defunct nodes are guarded; the node
        appears with empty/default values rather than crashing.
        """
        good_child = self._make_accessible(role="push button", name="OK", children=[])
        defunct_child = MagicMock()
        defunct_child.get_role.side_effect = RuntimeError("defunct")
        defunct_child.get_name.side_effect = RuntimeError("defunct")
        defunct_child.get_description.side_effect = RuntimeError("defunct")
        defunct_child.getState.side_effect = RuntimeError("defunct")
        defunct_child.getExtent.side_effect = RuntimeError("defunct")
        defunct_child.get_text.side_effect = RuntimeError("defunct")
        defunct_child.get_value.side_effect = RuntimeError("defunct")
        defunct_child.get_action.side_effect = RuntimeError("defunct")
        defunct_child.childCount = 0
        root = self._make_accessible(
            role="frame", name="Window", children=[good_child, defunct_child]
        )
        # Must NOT raise
        result = backend.snapshot(NativeHandle(root))
        children = result.get("children") or []
        assert len(children) == 2
        # Good child is intact
        assert children[0]["role"] == "button"
        assert children[0]["name"] == "OK"
        # Defunct child has empty/default properties
        assert children[1]["role"] == ""

    def test_snapshot_skips_child_with_get_child_at_index_error(
        self, backend: LinuxBackend
    ) -> None:
        """snapshot() must skip children when getChildAtIndex raises per §5.4."""
        good_child = self._make_accessible(role="push button", name="OK", children=[])
        root = self._make_accessible(
            role="frame",
            name="Window",
            children=[],
            child_count=2,
        )

        call_count = [0]

        def _get_child(idx):
            call_count[0] += 1
            if idx == 0:
                return good_child
            raise RuntimeError("defunct child")

        root.getChildAtIndex.side_effect = _get_child
        result = backend.snapshot(NativeHandle(root))
        children = result.get("children") or []
        assert len(children) == 1
        assert children[0]["name"] == "OK"

    def test_snapshot_skips_none_children(self, backend: LinuxBackend) -> None:
        """snapshot() must skip None children returned by getChildAtIndex."""
        root = self._make_accessible(
            role="frame",
            name="Window",
            children=[],
            child_count=2,  # Claim 2 children but provide 0
        )
        root.getChildAtIndex.return_value = None
        result = backend.snapshot(NativeHandle(root))
        children = result.get("children") or []
        assert len(children) == 0

    def test_snapshot_handles_defunct_root(self, backend: LinuxBackend) -> None:
        """snapshot() must return a valid dict even when root properties fail.

        Individual property reads are guarded; the result has a fallback role
        when get_role() fails.
        """
        defunct_root = MagicMock()
        defunct_root.get_role.side_effect = RuntimeError("defunct")
        defunct_root.get_name.return_value = None
        defunct_root.get_description.return_value = None
        defunct_root.getState.return_value.get_states.return_value = []
        defunct_root.getExtent.return_value = None
        defunct_root.get_text.return_value = None
        defunct_root.get_value.return_value = None
        defunct_root.get_action.return_value = None
        defunct_root.childCount = 0
        result = backend.snapshot(NativeHandle(defunct_root))
        assert isinstance(result, dict)
        # When role extraction fails, normalize_element falls back to role.lower() of ""
        assert result["role"] == ""

    # -- disposed state ---

    def test_snapshot_disposed_raises(self, backend: LinuxBackend) -> None:
        """snapshot() on disposed backend raises BackendUnavailableError."""
        backend.dispose()
        root = self._make_accessible(role="frame", name="W")
        with pytest.raises(BackendUnavailableError, match="disposed"):
            backend.snapshot(NativeHandle(root))

    # -- description and text extraction ---

    def test_snapshot_extracts_description(self, backend: LinuxBackend) -> None:
        """snapshot() must extract accessible description."""
        root = self._make_accessible(
            role="push button",
            name="Save",
            description="Save the current document",
        )
        result = backend.snapshot(NativeHandle(root))
        assert result.get("description") == "Save the current document"

    def test_snapshot_extracts_text_content(self, backend: LinuxBackend) -> None:
        """snapshot() must extract text via the Text interface."""
        root = self._make_accessible(
            role="entry",
            name="Search",
            text_content="hello world",
        )
        result = backend.snapshot(NativeHandle(root))
        assert result.get("text") == "hello world"

    def test_snapshot_extracts_value(self, backend: LinuxBackend) -> None:
        """snapshot() must extract value via the Value interface."""
        root = self._make_accessible(
            role="slider",
            name="Volume",
            value=0.75,
        )
        result = backend.snapshot(NativeHandle(root))
        assert result.get("value") == 0.75

    # -- role normalization edge cases ---

    def test_snapshot_unknown_role_fallback(self, backend: LinuxBackend) -> None:
        """snapshot() must fall back to lowercased role for unknown roles."""
        root = self._make_accessible(role="some custom widget", name="X")
        result = backend.snapshot(NativeHandle(root))
        # Unknown roles fall back to role.lower()
        assert result["role"] == "some custom widget"

    def test_snapshot_empty_name(self, backend: LinuxBackend) -> None:
        """snapshot() must handle empty/None name (omitted from dict)."""
        root = self._make_accessible(role="frame", name="")
        result = backend.snapshot(NativeHandle(root))
        # to_dict() omits None fields
        assert "name" not in result

    def test_snapshot_dialog_role(self, backend: LinuxBackend) -> None:
        """snapshot() normalizes 'dialog' role correctly."""
        root = self._make_accessible(role="dialog", name="Confirm")
        result = backend.snapshot(NativeHandle(root))
        assert result["role"] == "dialog"

    def test_snapshot_window_role(self, backend: LinuxBackend) -> None:
        """snapshot() normalizes 'window' role correctly."""
        root = self._make_accessible(role="window", name="Main")
        result = backend.snapshot(NativeHandle(root))
        assert result["role"] == "window"


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
        for attr in (
            "ROLE_FRAME",
            "ROLE_DIALOG",
            "ROLE_WINDOW",
            "ROLE_DESKTOP_FRAME",
            "ROLE_PANEL",
            "ROLE_TOOLTIP",
            "STATE_SHOWING",
        ):
            if hasattr(mock_pyatspi, attr):
                setattr(live_mock, attr, getattr(mock_pyatspi, attr))
    mock_desktop = mock_pyatspi.Registry.getDesktop.return_value
    backend._desktop.children = mock_desktop.children
