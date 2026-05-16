"""LinuxBackend — AT-SPI2 accessibility backend for Linux (architecture v2 §4.2).

Uses the ``pyatspi`` bindings to communicate with the AT-SPI2 accessibility
framework via the D-Bus accessibility registry.  The ``pyatspi`` import is
guarded so that this module can be imported on non-Linux platforms without
error (the constructor will raise :class:`BackendUnavailableError` at
instantiation time).

Skeleton implementation — all 9 abstract methods are present but raise
:exc:`NotImplementedError` pending concrete implementation in later stories.
"""

import sys
from typing import Any

from guidewire.backends.base import DesktopBackend
from guidewire.backends.types import DesktopAction, NativeHandle
from guidewire.errors import BackendUnavailableError

__all__ = [
    "LinuxBackend",
]


class LinuxBackend(DesktopBackend):
    """AT-SPI2-based accessibility backend for the Linux desktop.

    Wraps the ``pyatspi`` library to enumerate windows, walk the
    accessibility tree, and perform actions on elements via the AT-SPI2
    D-Bus registry.

    Raises:
        BackendUnavailableError: If the platform is not Linux or the
            ``pyatspi`` package is not installed.

    Usage::

        from guidewire.backends import LinuxBackend

        backend = LinuxBackend()
        windows = backend.list_windows()
    """

    def __init__(self) -> None:
        if sys.platform != "linux":
            raise BackendUnavailableError(
                "LinuxBackend requires the Linux platform "
                f"(current: {sys.platform!r})"
            )
        try:
            import pyatspi  # noqa: F401 — availability check
        except ImportError:
            raise BackendUnavailableError(
                "LinuxBackend requires the 'pyatspi' package "
                "(install via system package manager: apt install python3-pyatspi)"
            ) from None
        self._disposed: bool = False

    # -- DesktopBackend interface (9 abstract methods) -------------------------

    def list_windows(self) -> list[NativeHandle]:
        """List all visible top-level application windows.

        .. todo:: Implement via ``pyatspi.Registry.getDesktop(0).children``.

        Returns:
            List of opaque native window handles.
        """
        raise NotImplementedError("list_windows not yet implemented")

    def get_window_info(self, window: NativeHandle) -> dict[str, Any]:
        """Return window metadata as a dict.

        .. todo:: Implement via ``pyatspi.Accessible`` properties.

        Args:
            window: Opaque native window handle.

        Returns:
            Dict with keys ``title``, ``app_name``, ``focused``, ``bounds``.

        Raises:
            WindowNotFoundError: If the handle is invalid.
        """
        raise NotImplementedError("get_window_info not yet implemented")

    def focus_window(self, window: NativeHandle) -> None:
        """Bring a window to the foreground.

        .. todo:: Implement via ``pyatspi.Accessible`` ``grabFocus`` action.

        Args:
            window: Opaque native window handle.

        Raises:
            WindowNotFoundError: If the handle is invalid.
        """
        raise NotImplementedError("focus_window not yet implemented")

    def snapshot(
        self,
        window: NativeHandle,
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> dict[str, Any]:
        """Return an accessibility snapshot as a tree dict.

        .. todo:: Walk the AT-SPI tree rooted at *window*, normalizing
           roles/states/actions via ``guidewire.models.mappings``.

        Args:
            window: Opaque native window handle.
            max_depth: Maximum tree depth (default 4).
            max_nodes: Maximum nodes to include (default 500).

        Returns:
            Dict matching the DesktopElement schema.

        Raises:
            WindowNotFoundError: If the handle is invalid.
        """
        raise NotImplementedError("snapshot not yet implemented")

    def find_elements(
        self,
        window: NativeHandle,
        role: str | None = None,
        name: str | None = None,
    ) -> list[NativeHandle]:
        """Find elements matching criteria within a window.

        .. todo:: Walk the AT-SPI tree and match normalized role/name.

        Args:
            window: Opaque native window handle.
            role: Normalized role to match.
            name: Accessible name to match (case-insensitive substring).

        Returns:
            List of matching opaque native element handles.
        """
        raise NotImplementedError("find_elements not yet implemented")

    def perform_action(
        self,
        handle: NativeHandle,
        action: DesktopAction,
        **kwargs: Any,
    ) -> Any:
        """Perform an action on an element.

        .. todo:: Map :class:`DesktopAction` to AT-SPI actions.

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
        raise NotImplementedError("perform_action not yet implemented")

    def get_element_info(self, handle: NativeHandle) -> dict[str, Any]:
        """Return element metadata as a dict.

        .. todo:: Read role, name, and states from ``pyatspi.Accessible``.

        Args:
            handle: Opaque native element handle.

        Returns:
            Dict with keys ``role``, ``name``, ``states``.

        Raises:
            ElementNotFoundError: If the handle is not known.
        """
        raise NotImplementedError("get_element_info not yet implemented")

    def is_valid(self, element: NativeHandle) -> bool:
        """Check whether a native element reference is still valid.

        .. todo:: Query the AT-SPI registry to confirm the object still exists.

        Args:
            element: Opaque native element handle.

        Returns:
            ``True`` if the element still exists in the accessibility tree.
        """
        raise NotImplementedError("is_valid not yet implemented")

    def dispose(self) -> None:
        """Release all resources held by this backend.

        .. todo:: Deregister event listeners and clear cached references.

        Called when the MCP server shuts down.
        """
        self._disposed = True
