"""MockBackend — in-memory test double for DesktopBackend (architecture v2 §5).

Provides programmable implementations of all 8 canonical synchronous methods
so that unit tests can exercise the MCP tool layer without a real platform
accessibility backend.

Usage::

    from guidewire.backends import MockBackend

    backend = (
        MockBackend()
        .add_window(title="Notepad", app="notepad.exe")
        .add_element(role="button", name="Save", parent=w)
    )

    windows = backend.list_windows()
    info = backend.get_window_info(windows[0])
    elements = backend.find_elements(windows[0], role="button")
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Self
from uuid import uuid4

from guidewire.backends.base import DesktopBackend
from guidewire.backends.types import (
    DesktopAction,
    ElementBounds,
    ElementState,
    NativeHandle,
)
from guidewire.errors import (
    ElementNotFoundError,
    WindowNotFoundError,
)

# -- Internal data classes --------------------------------------------------


@dataclass(slots=True)
class _MockWindow:
    """Internal representation of a mock window."""

    handle: NativeHandle
    title: str
    app: str
    focused: bool = False
    bounds: ElementBounds = field(
        default_factory=lambda: ElementBounds(x=0, y=0, width=800, height=600),
    )
    disposed: bool = False


@dataclass(slots=True)
class _MockElement:
    """Internal representation of a mock element."""

    handle: NativeHandle
    role: str
    name: str | None = None
    value: str | None = None
    window_handle: NativeHandle | None = None
    parent_handle: NativeHandle | None = None
    valid: bool = True
    states: ElementState = field(default_factory=ElementState)
    actions: list[DesktopAction] = field(default_factory=list)
    bounds: ElementBounds = field(
        default_factory=lambda: ElementBounds(x=0, y=0, width=100, height=30),
    )


# -- Unique handle factory --------------------------------------------------


def _new_handle() -> NativeHandle:
    """Return a unique opaque handle string."""
    return NativeHandle(uuid4().hex)


# -- Tree-building helpers --------------------------------------------------


def _element_to_dict(e: _MockElement) -> dict[str, Any]:
    """Convert an internal _MockElement to a DesktopElement-style dict (no children)."""
    return {
        "ref": e.handle,
        "role": e.role,
        "name": e.name,
        "states": asdict(e.states),
        "bounds": {"x": e.bounds.x, "y": e.bounds.y, "width": e.bounds.width, "height": e.bounds.height},
        "actions": [a.value for a in e.actions],
        "children": [],
    }


def _build_tree(
    elements: list[_MockElement],
    parent_handle: NativeHandle | None,
    depth: int,
    max_depth: int,
    counter: list[int],
    max_nodes: int,
) -> list[dict[str, Any]]:
    """Recursively build a tree of element dicts respecting depth and node limits.

    Children at *depth* 1 are the direct children of the window root.
    ``max_depth=0`` means no children at all (root only).
    """
    if depth >= max_depth or counter[0] >= max_nodes:
        return []

    children: list[dict[str, Any]] = []
    for e in elements:
        if not e.valid or e.parent_handle != parent_handle:
            continue
        if counter[0] >= max_nodes:
            break
        counter[0] += 1
        node = _element_to_dict(e)
        node["children"] = _build_tree(elements, e.handle, depth + 1, max_depth, counter, max_nodes)
        children.append(node)
    return children


# -- MockBackend ------------------------------------------------------------


class MockBackend(DesktopBackend):
    """In-memory test double for :class:`DesktopBackend`.

    Stores windows and elements in plain dictionaries.  All methods are
    synchronous and complete immediately.  Supports simulating disposed
    (invalid) elements and configurable error conditions for testing.

    Builder methods (``add_window``, ``add_element``) return ``self`` for
    fluent chaining per architecture v2 §5.3.
    """

    def __init__(self) -> None:
        self._windows: dict[NativeHandle, _MockWindow] = {}
        self._elements: dict[NativeHandle, _MockElement] = {}
        self._disposed: bool = False
        self._action_log: list[dict[str, Any]] = []
        self._last_window_handle: NativeHandle | None = None

    # -- Builder API (seed helpers, fluent) ----------------------------------

    def add_window(
        self,
        title: str = "",
        app: str = "",
        focused: bool = False,
        bounds: ElementBounds | None = None,
    ) -> Self:
        """Register a mock window and return ``self`` for chaining."""
        handle = _new_handle()
        self._windows[handle] = _MockWindow(
            handle=handle,
            title=title,
            app=app,
            focused=focused,
            bounds=bounds or ElementBounds(x=0, y=0, width=800, height=600),
        )
        self._last_window_handle = handle
        return self

    def add_element(
        self,
        role: str,
        name: str | None = None,
        value: str | None = None,
        parent: NativeHandle | None = None,
        bounds: ElementBounds | None = None,
        states: ElementState | None = None,
        actions: list[DesktopAction] | None = None,
    ) -> Self:
        """Register a mock element and return ``self`` for chaining.

        Args:
            role: Normalized accessibility role.
            name: Accessible name.
            value: Current value.
            parent: Window handle this element belongs to (or ``None``).
            bounds: Bounding rectangle, or a default.
            states: Element state flags, or defaults.
            actions: Supported actions list, or empty.
        """
        handle = _new_handle()
        self._elements[handle] = _MockElement(
            handle=handle,
            role=role,
            name=name,
            value=value,
            window_handle=parent,
            parent_handle=None,
            valid=True,
            states=states or ElementState(),
            actions=actions or [],
            bounds=bounds or ElementBounds(x=0, y=0, width=100, height=30),
        )
        return self

    def invalidate(self, element: NativeHandle) -> None:
        """Mark an element as invalid (simulates a stale reference)."""
        if element in self._elements:
            self._elements[element].valid = False

    # -- Canonical 8 methods -------------------------------------------------

    def list_windows(self) -> list[NativeHandle]:
        """Return handles for all registered mock windows."""
        return [h for h, w in self._windows.items() if not w.disposed]

    def get_window_info(self, window: NativeHandle) -> dict[str, Any]:
        """Return window metadata as a dict (architecture v2 §4.1)."""
        if window not in self._windows:
            raise WindowNotFoundError(f"Window handle {window!r} not found")
        w = self._windows[window]
        return {
            "title": w.title,
            "app_name": w.app,
            "focused": w.focused,
            "bounds": {
                "x": w.bounds.x,
                "y": w.bounds.y,
                "width": w.bounds.width,
                "height": w.bounds.height,
            },
        }

    def focus_window(self, window: NativeHandle) -> None:
        """Focus a mock window by handle."""
        if window not in self._windows:
            raise WindowNotFoundError(f"Window handle {window!r} not found")
        for w in self._windows.values():
            w.focused = False
        self._windows[window].focused = True

    def snapshot(
        self,
        window: NativeHandle,
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> dict[str, Any]:
        """Return a tree dict of window elements (architecture v2 §4.1).

        Returns a dict matching the DesktopElement schema with nested children.
        Respects ``max_depth`` and ``max_nodes`` limits.
        """
        if window not in self._windows:
            raise WindowNotFoundError(f"Window handle {window!r} not found")
        w = self._windows[window]
        elements = [e for e in self._elements.values() if e.window_handle == window and e.valid]
        counter = [0]
        children = _build_tree(elements, None, 0, max_depth, counter, max_nodes)
        return {
            "ref": window,
            "role": "window",
            "name": w.title,
            "states": {"enabled": True, "focused": w.focused},
            "bounds": {
                "x": w.bounds.x,
                "y": w.bounds.y,
                "width": w.bounds.width,
                "height": w.bounds.height,
            },
            "actions": [],
            "children": children,
        }

    def find_elements(
        self,
        window: NativeHandle,
        role: str | None = None,
        name: str | None = None,
    ) -> list[NativeHandle]:
        """Find mock elements matching criteria within a window.

        Returns list of NativeHandle (not ElementState) per architecture v2 §4.1.
        """
        if window not in self._windows:
            raise WindowNotFoundError(f"Window handle {window!r} not found")
        results: list[NativeHandle] = []
        for e in self._elements.values():
            if e.window_handle != window or not e.valid:
                continue
            if role is not None and e.role != role:
                continue
            if name is not None and (e.name is None or name.lower() not in e.name.lower()):
                continue
            results.append(e.handle)
        return results

    def perform_action(
        self,
        handle: NativeHandle,
        action: DesktopAction,
        **kwargs: Any,
    ) -> Any:
        """Perform an action on a mock element.

        Parameter order is ``(handle, action, **kwargs)`` per architecture v2 §4.1.
        Returns ``str`` when action is ``GET_TEXT``, otherwise ``None``.
        """
        if handle not in self._elements:
            raise ElementNotFoundError(f"Element handle {handle!r} not found")
        e = self._elements[handle]
        if not e.valid:
            from guidewire.errors import StaleElementReferenceError

            raise StaleElementReferenceError(f"Element handle {handle!r} is stale")
        self._action_log.append({"action": action, "handle": handle, "kwargs": kwargs})
        if action == DesktopAction.GET_TEXT:
            return e.value or ""
        return None

    def is_valid(self, element: NativeHandle) -> bool:
        """Check whether a mock element reference is still valid."""
        if element not in self._elements:
            return False
        return self._elements[element].valid

    def dispose(self) -> None:
        """Release all mock resources."""
        self._disposed = True
        self._windows.clear()
        self._elements.clear()

    # -- Inspection helpers for tests ----------------------------------------

    @property
    def action_log(self) -> list[dict[str, Any]]:
        """Recorded action calls."""
        return list(self._action_log)

    @property
    def is_disposed(self) -> bool:
        """Whether dispose has been called."""
        return self._disposed

    @property
    def last_window_handle(self) -> NativeHandle | None:
        """Handle of the most recently added window (for fluent chaining)."""
        return self._last_window_handle
