"""WindowsBackend — Windows UI Automation accessibility backend (architecture v2 §4.2).

Uses the ``comtypes`` library to access the Windows UI Automation (UIA)
COM API.  The ``comtypes`` import is guarded so that this module can be
imported on non-Windows platforms without error (the constructor will raise
:class:`BackendUnavailableError` at instantiation time).

Implementation status:
- ``list_windows`` — implemented (GW-020)
- ``get_window_info``, ``focus_window`` — pending (GW-021)
- ``snapshot``, ``find_elements`` — pending (GW-022)
- ``perform_action``, ``get_element_info``, ``is_valid`` — pending (GW-023)
"""

import sys
from typing import Any

from guidewire.backends.base import DesktopBackend
from guidewire.backends.types import DesktopAction, NativeHandle
from guidewire.errors import BackendUnavailableError

__all__ = [
    "WindowsBackend",
]

# -- UIA constants (architecture §5: module-level) ----------------------------

_UIA_TREE_SCOPE_CHILDREN = 2  # UIA TreeScope_Children
_UIA_CONTROL_TYPE_PROPERTY_ID = 30003  # UIA_PropertyId_UIA_ControlTypePropertyId
_UIA_WINDOW_CONTROL_TYPE_ID = 50032  # UIA_ControlType_Window (0xC370)
_UIA_IS_OFFSCREEN_PROPERTY_ID = 30022  # UIA_PropertyId_UIA_IsOffscreenPropertyId


class WindowsBackend(DesktopBackend):
    """Windows UI Automation-based accessibility backend.

    Wraps the ``comtypes`` library to communicate with the Windows UI
    Automation COM API for enumerating windows, walking the accessibility
    tree, and performing actions on elements.

    Raises:
        BackendUnavailableError: If the platform is not Windows or the
            ``comtypes`` package is not installed.

    Usage::

        from guidewire.backends import WindowsBackend

        backend = WindowsBackend()
        windows = backend.list_windows()
    """

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise BackendUnavailableError(
                f"WindowsBackend requires the Windows platform (current: {sys.platform!r})"
            )
        try:
            import comtypes
            import comtypes.client
        except ImportError:
            raise BackendUnavailableError(
                "WindowsBackend requires the 'comtypes' package "
                "(install via: pip install 'guidewire[windows]')"
            ) from None
        comtypes.CoInitialize()  # type: ignore[attr-defined]
        self._com_initialized: bool = True
        self._uia: Any = comtypes.client.CreateObject(  # type: ignore[attr-defined]
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=comtypes.IUnknown,  # type: ignore[attr-defined]
        )
        self._disposed: bool = False

    # -- DesktopBackend interface (9 abstract methods) -------------------------

    def list_windows(self) -> list[NativeHandle]:
        """List all visible top-level application windows.

        Uses ``IUIAutomation.GetRootElement`` to obtain the desktop root,
        then ``FindAll`` with ``TreeScope_Children`` and a
        ``ControlType.Window`` property condition to enumerate top-level
        windows.  Off-screen windows are filtered out.

        Returns:
            List of opaque native window handles (COM pointers to
            ``IUIAutomationElement`` objects).

        Raises:
            BackendUnavailableError: If the backend is disposed or UIA
                COM calls fail.
        """
        if self._disposed:
            raise BackendUnavailableError("WindowsBackend has been disposed")

        import comtypes  # noqa: F401

        try:
            root = self._uia.GetRootElement()
            condition = self._uia.CreatePropertyCondition(
                _UIA_CONTROL_TYPE_PROPERTY_ID,
                _UIA_WINDOW_CONTROL_TYPE_ID,
            )
            found = self._uia.FindAll(_UIA_TREE_SCOPE_CHILDREN, root, condition)
            count = found.Length
            result: list[NativeHandle] = []
            for i in range(count):
                element = found.GetElement(i)
                is_offscreen = element.GetCurrentPropertyValue(_UIA_IS_OFFSCREEN_PROPERTY_ID)
                if not is_offscreen:
                    result.append(NativeHandle(element))
            return result
        except BackendUnavailableError:
            raise
        except Exception as exc:
            raise BackendUnavailableError(f"Failed to enumerate windows via UIA: {exc}") from exc

    def get_window_info(self, window: NativeHandle) -> dict[str, Any]:
        """Return window metadata as a dict.

        .. todo:: Implement via ``IUIAutomationElement`` properties
           (CurrentName, CurrentClassName, CurrentBoundingRectangle).

        Args:
            window: Opaque native window handle.

        Returns:
            Dict with keys ``title``, ``app_name``, ``focused``, ``bounds``.

        Raises:
            WindowNotFoundError: If the handle is invalid.
        """
        raise NotImplementedError("get_window_info not yet implemented — see GW-021")

    # -- Private helpers (section 4.2-4.4) -----------------------------------

    @staticmethod
    def _extract_hwnd(window: NativeHandle) -> int:
        """Extract an HWND integer from a :class:`NativeHandle`.

        Args:
            window: Opaque native window handle.

        Returns:
            The underlying HWND as a positive integer.

        Raises:
            WindowNotFoundError: If the extracted handle is zero (null window).
        """
        from guidewire.errors import WindowNotFoundError

        hwnd = int(window)
        if hwnd == 0:
            raise WindowNotFoundError("Window handle 0x0 is not a valid window")
        return hwnd

    def _element_from_handle(self, hwnd: int) -> Any:
        """Bridge an HWND to an ``IUIAutomationElement`` via COM.

        Args:
            hwnd: A valid window handle.

        Returns:
            The COM ``IUIAutomationElement`` for the window.
        """
        return self._uia.ElementFromHandle(hwnd)

    # -- DesktopBackend interface (9 abstract methods) -------------------------

    def focus_window(self, window: NativeHandle) -> None:
        """Bring a window to the foreground.

        Validates the backend is not disposed, extracts and validates the
        HWND, then calls the Win32 ``SetForegroundWindow`` API.  If the first
        attempt fails (foreground-lock restriction), a ``keybd_event`` Alt-key
        workaround is applied (architecture §2.4) and the call is retried once.
        On success, ``IUIAutomationElement.SetFocus`` is called to set keyboard
        focus (architecture §2.5).

        Args:
            window: Opaque native window handle (HWND integer).

        Raises:
            RuntimeError: If the backend has been disposed.
            WindowNotFoundError: If the handle does not reference a valid window
                or ``SetForegroundWindow`` fails to activate it.
            TypeError: If *window* is not an int-backed NativeHandle.
            OSError: If an unexpected ctypes / OS error occurs.
        """
        import ctypes

        from guidewire.errors import WindowNotFoundError

        if self._disposed:
            raise RuntimeError("Cannot focus window on a disposed backend")

        try:
            hwnd = self._extract_hwnd(window)
        except TypeError as exc:
            raise TypeError(f"window must be an int-backed NativeHandle: {exc}") from exc

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]

        if not user32.IsWindow(hwnd):  # type: ignore[attr-defined]
            raise WindowNotFoundError(
                f"Window handle {hwnd:#x} is not a valid window"
            )

        # First attempt: SetForegroundWindow
        result = user32.SetForegroundWindow(hwnd)  # type: ignore[attr-defined]

        # Foreground-lock workaround (architecture §2.4): simulate an Alt
        # keypress to convince Windows that user interaction is occurring,
        # then retry SetForegroundWindow once.
        if not result:
            vk_menu = 0x12  # Alt key virtual-key code
            keyeventf_keyup = 0x0002
            user32.keybd_event(vk_menu, 0, 0, 0)  # type: ignore[attr-defined]
            user32.keybd_event(  # type: ignore[attr-defined]
                vk_menu, 0, keyeventf_keyup, 0,
            )
            result = user32.SetForegroundWindow(hwnd)  # type: ignore[attr-defined]

        if not result:
            raise WindowNotFoundError(
                f"SetForegroundWindow failed for window handle {hwnd:#x}"
            )

        # Set UIA keyboard focus (architecture §2.5)
        try:
            element = self._element_from_handle(hwnd)
            element.SetFocus()
        except Exception:
            # SetFocus is best-effort; foreground was already set.
            pass

    def snapshot(
        self,
        window: NativeHandle,
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> dict[str, Any]:
        """Return an accessibility snapshot as a tree dict.

        .. todo:: Walk the UIA tree rooted at *window*, normalizing
           roles/states/actions via ``guidewire.models.mappings``.
           Use ``IUIAutomationTreeWalker`` for traversal.

        Args:
            window: Opaque native window handle.
            max_depth: Maximum tree depth (default 4).
            max_nodes: Maximum nodes to include (default 500).

        Returns:
            Dict matching the DesktopElement schema.

        Raises:
            WindowNotFoundError: If the handle is invalid.
        """
        raise NotImplementedError("snapshot not yet implemented — see GW-022")

    def find_elements(
        self,
        window: NativeHandle,
        role: str | None = None,
        name: str | None = None,
    ) -> list[NativeHandle]:
        """Find elements matching criteria within a window.

        .. todo:: Walk the UIA tree and match normalized role/name.
           Use ``IUIAutomation.CreatePropertyCondition`` for efficient
           queries.

        Args:
            window: Opaque native window handle.
            role: Normalized role to match.
            name: Accessible name to match (case-insensitive substring).

        Returns:
            List of matching opaque native element handles.
        """
        raise NotImplementedError("find_elements not yet implemented — see GW-022")

    def perform_action(
        self,
        handle: NativeHandle,
        action: DesktopAction,
        **kwargs: Any,
    ) -> Any:
        """Perform an action on an element.

        .. todo:: Map :class:`DesktopAction` to UIA invoke/set-value
           patterns (``IUIAutomationInvokePattern``, etc.).

        Args:
            handle: Opaque native element handle.
            action: The action to perform.
            **kwargs: Action-specific parameters.

        Returns:
            ``str`` when action is ``GET_TEXT``, otherwise ``None``.

        Raises:
            ElementNotFoundError: If the handle is not known.
            StaleElementReferenceError: If the element no longer exists.
            ActionNotSupportedError: If the action is not available.
        """
        raise NotImplementedError("perform_action not yet implemented — see GW-023")

    def get_element_info(self, handle: NativeHandle) -> dict[str, Any]:
        """Return element metadata as a dict.

        .. todo:: Read role, name, and states from ``IUIAutomationElement``
           properties (CurrentControlType, CurrentName, CurrentIsEnabled, etc.).

        Args:
            handle: Opaque native element handle.

        Returns:
            Dict with keys ``role``, ``name``, ``states``.

        Raises:
            ElementNotFoundError: If the handle is not known.
        """
        raise NotImplementedError("get_element_info not yet implemented — see GW-023")

    def is_valid(self, element: NativeHandle) -> bool:
        """Check whether a native element reference is still valid.

        .. todo:: Query the UIA element to confirm it still exists via
           ``IUIAutomation.ElementFromHandle`` or cached reference check.

        Args:
            element: Opaque native element handle.

        Returns:
            ``True`` if the element still exists in the accessibility tree.
        """
        raise NotImplementedError("is_valid not yet implemented — see GW-023")

    def dispose(self) -> None:
        """Release all resources held by this backend.

        Releases the IUIAutomation COM reference, uninitializes the COM
        library, and marks the backend as disposed.  Safe to call multiple
        times (idempotent).

        Called when the MCP server shuts down.
        """
        if self._disposed:
            return
        self._uia = None
        if self._com_initialized:
            try:
                import comtypes

                comtypes.CoUninitialize()  # type: ignore[attr-defined]
            except Exception:
                pass
            self._com_initialized = False
        self._disposed = True
