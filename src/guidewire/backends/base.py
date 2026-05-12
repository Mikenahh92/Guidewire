"""DesktopBackend — abstract contract for platform accessibility backends.

Defines the 8 canonical synchronous methods that every platform backend
must implement (architecture v2 §4.1).  Concrete backends (Windows UIA,
macOS AX, Linux AT-SPI) inherit from :class:`DesktopBackend` and translate
native accessibility APIs into the cross-platform types defined in
:mod:`guidewire.backends.types`.
"""

from abc import ABC, abstractmethod
from typing import Any

from guidewire.backends.types import (
    DesktopAction,
    NativeHandle,
)

__all__ = [
    "DesktopBackend",
]


class DesktopBackend(ABC):
    """Abstract base class for platform accessibility backends.

    Every method is synchronous.  The 8 methods form the complete contract
    that the MCP tool layer calls.  Subclasses must implement all of them.

    Method mapping (architecture v2 §4.1):
        list_windows  → desktop.list_windows
        get_window_info → desktop.get_window_info
        focus_window  → desktop.focus_window
        snapshot      → desktop.snapshot
        find_elements → desktop.find_elements
        perform_action → desktop.perform_action
        is_valid      → internal staleness check
        dispose       → resource cleanup
    """

    @abstractmethod
    def list_windows(self) -> list[NativeHandle]:
        """List all visible top-level windows.

        Returns:
            List of opaque native window handles.

        Maps to: ``desktop.list_windows`` (PRD §6.1).
        """

    @abstractmethod
    def get_window_info(self, window: NativeHandle) -> dict[str, Any]:
        """Return window metadata as a dict (architecture v2 §4.1).

        Args:
            window: Opaque native window handle from :meth:`list_windows`.

        Returns:
            Dict with keys ``title`` (str), ``app_name`` (str),
            ``focused`` (bool), ``bounds`` (ElementBounds | None).

        Maps to: ``desktop.get_window_info``.
        """

    @abstractmethod
    def focus_window(self, window: NativeHandle) -> None:
        """Bring a window to the foreground.

        Args:
            window: Opaque native window handle.

        Raises:
            WindowNotFoundError: If the handle is invalid.

        Maps to: ``desktop.focus_window`` (PRD §6.2).
        """

    @abstractmethod
    def snapshot(
        self,
        window: NativeHandle,
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> dict[str, Any]:
        """Return an accessibility snapshot as a tree dict (architecture v2 §4.1).

        Produces a concise, depth-limited view of the accessibility tree
        suitable for LLM consumption (PRD §5.3).

        Args:
            window: Opaque native window handle.
            max_depth: Maximum tree depth to traverse (default 4).
            max_nodes: Maximum number of nodes to include (default 500).

        Returns:
            Dict matching the DesktopElement schema with keys:
            ``ref``, ``role``, ``name``, ``states``, ``bounds``, ``actions``,
            ``children`` (nested list of child dicts).

        Maps to: ``desktop.snapshot`` (PRD §6.3).
        """

    @abstractmethod
    def find_elements(
        self,
        window: NativeHandle,
        role: str | None = None,
        name: str | None = None,
    ) -> list[NativeHandle]:
        """Find elements matching criteria within a window.

        Args:
            window: Opaque native window handle.
            role: Normalized role to match (e.g. ``"button"``).
            name: Accessible name to match (case-insensitive substring).

        Returns:
            List of matching opaque native element handles.

        Maps to: ``desktop.find_elements`` (PRD §6.5).
        """

    @abstractmethod
    def perform_action(
        self,
        handle: NativeHandle,
        action: DesktopAction,
        **kwargs: Any,
    ) -> Any:
        """Perform an action on an element (architecture v2 §4.1).

        Dispatches to the appropriate native action pattern based on
        the :class:`DesktopAction` value.

        Args:
            handle: Opaque native element handle (first positional arg).
            action: The action to perform.
            **kwargs: Action-specific parameters.

        Returns:
            ``str`` when action is ``GET_TEXT``, otherwise ``None``.

        Raises:
            ActionNotSupportedError: If the action is not available.

        Maps to: ``desktop.perform_action`` (PRD 6.6-6.12).
        """

    @abstractmethod
    def is_valid(self, element: NativeHandle) -> bool:
        """Check whether a native element reference is still valid.

        Args:
            element: Opaque native element handle.

        Returns:
            ``True`` if the element still exists in the accessibility tree.
        """

    @abstractmethod
    def dispose(self) -> None:
        """Release all resources held by this backend.

        Called when the MCP server shuts down.  Should clean up event
        subscriptions, COM references, and other platform handles.
        """
