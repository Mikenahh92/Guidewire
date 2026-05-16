"""WindowsBackend — Windows UI Automation accessibility backend (architecture v2 §4.2).

Uses the ``comtypes`` library to access the Windows UI Automation (UIA)
COM API.  The ``comtypes`` import is guarded so that this module can be
imported on non-Windows platforms without error (the constructor will raise
:class:`BackendUnavailableError` at instantiation time).

Implementation status:
- ``list_windows`` — implemented (GW-020)
- ``focus_window`` — implemented (GW-021)
- ``snapshot``, ``find_elements`` — implemented (GW-022)
- ``perform_action``, ``get_element_info`` — pending (GW-023)
- ``is_valid`` — implemented (GW-024)

Implements :meth:`snapshot` and :meth:`find_elements` via
``IUIAutomationTreeWalker`` for depth-limited accessibility tree traversal,
extracting raw element properties (ControlType, Name, Value, IsEnabled,
bounds, patterns) for later normalization by the tool layer (GW-022).
"""

import logging
import sys
from dataclasses import dataclass
from typing import Any

from guidewire.backends.base import DesktopBackend
from guidewire.backends.types import DesktopAction, NativeHandle
from guidewire.errors import BackendUnavailableError, WindowNotFoundError
from guidewire.models.mappings import resolve_action, resolve_role, resolve_state

logger = logging.getLogger(__name__)

__all__ = [
    "WindowsBackend",
]

# -- UIA constants (architecture §5: module-level) ----------------------------

_UIA_TREE_SCOPE_CHILDREN = 2  # UIA TreeScope_Children
_UIA_CONTROL_TYPE_PROPERTY_ID = 30003  # UIA_PropertyId_UIA_ControlTypePropertyId
_UIA_WINDOW_CONTROL_TYPE_ID = 50032  # UIA_ControlType_Window (0xC370)
_UIA_IS_OFFSCREEN_PROPERTY_ID = 30022  # UIA_PropertyId_UIA_IsOffscreenPropertyId
_UIA_PROCESS_ID_PROPERTY_ID = 30076  # UIA_PropertyId_UIA_ProcessIdPropertyId


@dataclass(slots=True)
class _ComHandle:
    """Wraps a COM ``IUIAutomationElement`` reference with a liveness check.

    Architecture §3.1 requires that element references carry the backend's
    ``IUIAutomation`` pointer so that ``is_alive()`` can verify the element
    still exists via ``ElementFromHandle`` or a similar COM query.
    """

    element: Any
    _uia: Any

    def is_alive(self) -> bool:
        """Return ``True`` if the COM element is still reachable.

        Queries ``_uia.CompareElements`` to check the reference is valid
        without requiring a window handle.
        """
        try:
            self._uia.CompareElements(self.element, self.element)
            return True
        except Exception:
            return False


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
        """Return an accessibility snapshot as a tree dict (GW-022).

        Walks the UIA tree rooted at *window* using ``IUIAutomationTreeWalker``,
        extracting raw element properties and normalizing them via the
        cross-platform mapping tables in :mod:`guidewire.models.mappings`.

        Args:
            window: Opaque native window handle (COM ``IUIAutomationElement``).
            max_depth: Maximum tree depth to traverse (default 4).
            max_nodes: Maximum number of nodes to include (default 500).

        Returns:
            Dict matching the DesktopElement schema with keys:
            ``ref``, ``role``, ``name``, ``states``, ``bounds``,
            ``actions``, ``children``.

        Raises:
            WindowNotFoundError: If the handle is invalid or the backend
                is disposed.
        """
        self._ensure_not_disposed()
        return self._walk_tree(window, max_depth=max_depth, max_nodes=max_nodes)

    # -- Internal tree-walking helpers -----------------------------------------

    def _ensure_not_disposed(self) -> None:
        """Raise :class:`WindowNotFoundError` if the backend is disposed."""
        if self._disposed:
            raise WindowNotFoundError("Backend is disposed")

    def _get_tree_walker(self) -> Any:
        """Return the control view ``IUIAutomationTreeWalker`` from ``self._uia``.

        Uses ``ControlViewWalker`` rather than ``RawViewWalker`` so that
        offscreen and decorative elements are excluded natively by the UIA
        runtime, producing a cleaner tree for LLM consumption.
        """
        return self._uia.ControlViewWalker

    def _extract_element_node(self, element: Any) -> dict[str, Any]:
        """Extract properties from a single ``IUIAutomationElement``.

        Reads ControlType, Name, Value, IsEnabled, bounding rectangle,
        and supported patterns, then normalizes via mapping tables.

        Returns:
            A flat dict with keys matching the DesktopElement schema
            (excluding ``children``).
        """
        # --- ControlType / role ---
        try:
            control_type_id = element.CurrentControlType
        except Exception:
            control_type_id = 0

        control_type_name = _control_type_id_to_name(control_type_id)
        normalized_role = resolve_role("windows", control_type_name) or control_type_name

        # --- Name ---
        try:
            name = element.CurrentName
        except Exception:
            name = None

        # --- Value ---
        value = None
        try:
            value_pattern = element.GetCurrentPattern(_UIA_VALUE_PATTERN_ID)
            if value_pattern is not None:
                value = value_pattern.CurrentValue
        except Exception:
            pass

        # --- States ---
        states: dict[str, Any] = {}
        _read_state(element, "IsEnabled", "CurrentIsEnabled", bool, states)
        _read_state(element, "HasKeyboardFocus", "CurrentHasKeyboardFocus", bool, states)
        _read_state(element, "IsSelected", "CurrentIsSelected", bool, states)
        _read_state(element, "IsOffscreen", "CurrentIsOffscreen", bool, states)
        _read_state(element, "IsReadOnly", "CurrentIsReadOnly", bool, states)
        _read_state(element, "IsRequiredForForm", "CurrentIsRequiredForForm", bool, states)
        _read_state(element, "IsPassword", "CurrentIsPassword", bool, states)

        # ToggleState needs special handling (integer enum)
        try:
            toggle_state = element.CurrentToggleState
            resolved = resolve_state("windows", "ToggleState", toggle_state)
            if resolved:
                states[resolved[0]] = resolved[1]
        except Exception:
            pass

        # IsExpanded
        try:
            expanded = element.CurrentIsExpanded
            resolved = resolve_state("windows", "IsExpanded", expanded)
            if resolved:
                states[resolved[0]] = resolved[1]
        except Exception:
            pass

        # Visibility (requires element pattern)
        try:
            visibility = element.CurrentVisibility
            resolved = resolve_state("windows", "Visibility", visibility)
            if resolved:
                states[resolved[0]] = resolved[1]
        except Exception:
            pass

        # --- Bounds ---
        bounds: dict[str, Any] | None = None
        try:
            rect = element.CurrentBoundingRectangle
            if rect:
                # rect is a tuple (left, top, width, height)
                bounds = {
                    "x": int(rect.left),
                    "y": int(rect.top),
                    "width": int(rect.width),
                    "height": int(rect.height),
                }
        except Exception:
            pass

        # --- Actions (pattern availability) ---
        actions: list[str] = []
        for pattern_id, pattern_name in _UIA_PATTERN_MAP:
            try:
                pattern = element.GetCurrentPattern(pattern_id)
                if pattern is not None:
                    action = resolve_action("windows", pattern_name)
                    if action and action not in actions:
                        actions.append(action)
            except Exception:
                pass

        return {
            "ref": _ComHandle(element, self._uia),
            "role": normalized_role,
            "name": name,
            "value": value,
            "states": states,
            "bounds": bounds,
            "actions": actions,
            "children": [],
        }

    def _walk_tree(
        self,
        root_element: Any,
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> dict[str, Any]:
        """Recursively walk the UIA tree and build a snapshot dict.

        The root element is always included regardless of offscreen state.
        Offscreen filtering only applies to descendant nodes.

        Args:
            root_element: The root ``IUIAutomationElement`` to walk from.
            max_depth: Maximum depth to traverse.
            max_nodes: Maximum total nodes (including root).

        Returns:
            Tree dict matching the DesktopElement schema.
        """
        counter = [0]
        walker = self._get_tree_walker()
        node = self._walk_recursive(root_element, walker, 0, max_depth, counter, max_nodes)
        if node is None:
            # Root should never be None; return a minimal node as fallback
            return {
                "ref": _ComHandle(root_element, self._uia),
                "role": "unknown",
                "name": None,
                "value": None,
                "states": {},
                "bounds": None,
                "actions": [],
                "children": [],
            }
        return node

    def _walk_recursive(
        self,
        element: Any,
        walker: Any,
        depth: int,
        max_depth: int,
        counter: list[int],
        max_nodes: int,
    ) -> dict[str, Any] | None:
        """Recursively walk from *element* building the tree dict.

        Returns ``None`` for offscreen descendant elements (depth > 0),
        which the caller filters out of the children list.  The root
        element (depth 0) is always included.  This acts as a safety net
        on top of ``ControlViewWalker`` (which already excludes most
        offscreen nodes).
        """
        if counter[0] >= max_nodes:
            return {"ref": _ComHandle(element, self._uia), "role": "unknown", "children": []}

        counter[0] += 1
        node = self._extract_element_node(element)

        # Exclude offscreen descendants (but never the root at depth 0)
        if depth > 0 and node.get("states", {}).get("offscreen") is True:
            counter[0] -= 1
            return None

        if depth < max_depth:
            children: list[dict[str, Any]] = []
            try:
                child = walker.GetFirstChildElement(element)
                while child is not None:
                    if counter[0] >= max_nodes:
                        break
                    child_node = self._walk_recursive(
                        child, walker, depth + 1, max_depth, counter, max_nodes
                    )
                    if child_node is not None:
                        children.append(child_node)
                    next_child = walker.GetNextSiblingElement(child)
                    child = next_child
            except Exception:
                logger.debug("Error walking children at depth %d", depth, exc_info=True)
            node["children"] = children

        return node

    def find_elements(
        self,
        window: NativeHandle,
        role: str | None = None,
        name: str | None = None,
    ) -> list[_ComHandle]:
        """Find elements matching criteria within a window (GW-022).

        Walks the UIA tree rooted at *window* and collects elements whose
        normalized role and/or accessible name match the given filters.

        Args:
            window: Opaque native window handle (COM ``IUIAutomationElement``).
            role: Normalized role to match (exact).
            name: Accessible name to match (case-insensitive substring).

        Returns:
            List of matching ``_ComHandle`` references wrapping COM pointers.
        """
        self._ensure_not_disposed()

        # AC-15 / AD-5: require at least one filter criterion
        if role is None and name is None:
            return []

        results: list[_ComHandle] = []
        walker = self._get_tree_walker()

        try:
            child = walker.GetFirstChildElement(window)
            while child is not None:
                self._find_recursive(child, walker, 0, role, name, results)
                child = walker.GetNextSiblingElement(child)
        except Exception:
            logger.debug("Error in find_elements tree walk", exc_info=True)

        return results

    def _find_recursive(
        self,
        element: Any,
        walker: Any,
        depth: int,
        role: str | None,
        name: str | None,
        results: list[_ComHandle],
    ) -> None:
        """Recursively search for elements matching *role* and/or *name*.

        No depth limit — architecture §3.3 requires exhaustive traversal.
        """
        # Extract role and name from the element
        try:
            control_type_id = element.CurrentControlType
        except Exception:
            control_type_id = 0

        control_type_name = _control_type_id_to_name(control_type_id)
        normalized_role = resolve_role("windows", control_type_name) or control_type_name

        try:
            element_name = element.CurrentName
        except Exception:
            element_name = None

        # Match criteria
        role_match = role is None or normalized_role == role
        name_match = name is None or (
            element_name is not None and name.lower() in element_name.lower()
        )

        if role_match and name_match:
            results.append(_ComHandle(element, self._uia))

        # Recurse into children
        try:
            child = walker.GetFirstChildElement(element)
            while child is not None:
                self._find_recursive(child, walker, depth + 1, role, name, results)
                child = walker.GetNextSiblingElement(child)
        except Exception:
            pass

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

        Uses a lightweight property-access probe on the underlying COM
        ``IUIAutomationElement`` to detect stale handles.  For HWND-integer
        handles (produced by ``focus_window``), delegates to the Win32
        ``IsWindow`` API via ``ctypes``.

        This method must **never** raise — the tool layer calls it outside
        any ``try / except`` block, so any exception would propagate as an
        unhandled MCP error.

        Args:
            element: Opaque native element handle.  May be a COM
                ``IUIAutomationElement`` pointer (from ``list_windows`` /
                ``find_elements``) or a bare HWND ``int`` (from
                ``focus_window``).

        Returns:
            ``True`` if the element still exists in the accessibility tree,
            ``False`` otherwise (including when the backend is disposed).
        """
        if self._disposed:
            return False

        # HWND integer handles — use Win32 IsWindow API.
        if isinstance(element, int):
            try:
                import ctypes

                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                return bool(user32.IsWindow(element))  # type: ignore[attr-defined]
            except Exception:
                return False

        # COM IUIAutomationElement — probe with a cheap property read.
        try:
            element.GetCurrentPropertyValue(_UIA_PROCESS_ID_PROPERTY_ID)
            return True
        except Exception:
            return False

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


# ---------------------------------------------------------------------------
# Module-level helpers for UIA property extraction
# ---------------------------------------------------------------------------

# UIA pattern / property IDs — see: https://docs.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpattern-ids
_UIA_VALUE_PATTERN_ID: int = 10002

# Map of UIA ControlType integer IDs to their string names.
# See: https://docs.microsoft.com/en-us/windows/win32/winauto/uiauto-controltype-ids
_UIA_CONTROL_TYPE_MAP: dict[int, str] = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50021: "ToolBar",
    50022: "ToolTip",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50027: "Thumb",
    50028: "DataGrid",
    50029: "DataItem",
    50030: "Document",
    50031: "SplitButton",
    50032: "Window",
    50033: "Pane",
    50034: "Header",
    50035: "HeaderItem",
    50036: "Table",
    50037: "TitleBar",
    50038: "Separator",
}


def _control_type_id_to_name(control_type_id: int) -> str:
    """Convert a UIA ControlType integer ID to its string name.

    Args:
        control_type_id: The UIA ControlType integer value.

    Returns:
        The string name (e.g. ``"Button"``, ``"Edit"``), or ``"Custom"``
        for unknown IDs.
    """
    return _UIA_CONTROL_TYPE_MAP.get(control_type_id, "Custom")


# Map of UIA pattern IDs to pattern names used for action resolution.
# Pattern IDs are the integer identifiers for UIA automation patterns.
_UIA_PATTERN_MAP: list[tuple[int, str]] = [
    (10000, "InvokePattern"),
    (10015, "TogglePattern"),
    (10005, "ExpandCollapsePattern"),
    (10004, "ScrollPattern"),
    (10006, "SelectionPattern"),
    (10010, "SelectionItemPattern"),
    (_UIA_VALUE_PATTERN_ID, "ValuePattern"),
    (10014, "TextPattern"),
    (10003, "RangeValuePattern"),
]


def _read_state(
    element: Any,
    state_key: str,
    attr_name: str,
    transform: type[bool],
    states: dict[str, Any],
) -> None:
    """Read a boolean state property from a UIA element and resolve it.

    Args:
        element: The ``IUIAutomationElement`` to read from.
        state_key: The key for :data:`STATE_MAP` (e.g. ``"IsEnabled"``).
        attr_name: The COM attribute name (e.g. ``"CurrentIsEnabled"``).
        transform: Type constructor to apply (typically ``bool``).
        states: Dict to accumulate resolved state key-value pairs into.
    """
    try:
        raw_value = getattr(element, attr_name)
        resolved = resolve_state("windows", state_key, raw_value)
        if resolved:
            states[resolved[0]] = resolved[1]
    except Exception:
        pass
