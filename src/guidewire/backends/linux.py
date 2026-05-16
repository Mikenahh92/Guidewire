"""LinuxBackend — AT-SPI2 accessibility backend for Linux (architecture v2 §4.2).

Uses the ``pyatspi`` bindings to communicate with the AT-SPI2 accessibility
framework via the D-Bus accessibility registry.  The ``pyatspi`` import is
guarded so that this module can be imported on non-Linux platforms without
error (the constructor will raise :class:`BackendUnavailableError` at
instantiation time).

Implementation status:
- ``list_windows`` — implemented (GW-029)
- ``get_window_info``, ``focus_window`` — pending
- ``snapshot`` — pending
- ``find_elements`` — implemented (GW-032)
- ``perform_action`` — implemented (GW-032)
- ``get_element_info`` — implemented (GW-032)
- ``is_valid`` — implemented (GW-032)
"""

import logging
import sys
from typing import Any

from guidewire.backends.base import DesktopBackend
from guidewire.backends.types import DesktopAction, NativeHandle
from guidewire.errors import (
    ActionNotSupportedError,
    BackendUnavailableError,
    ElementNotFoundError,
    StaleElementReferenceError,
)

logger = logging.getLogger(__name__)

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
                f"LinuxBackend requires the Linux platform (current: {sys.platform!r})"
            )
        try:
            import pyatspi  # availability check
        except ImportError:
            raise BackendUnavailableError(
                "LinuxBackend requires the 'pyatspi' package "
                "(install via system package manager: apt install python3-pyatspi)"
            ) from None
        self._disposed: bool = False

        import pyatspi

        self._desktop = pyatspi.Registry.getDesktop(0)

    # -- DesktopBackend interface (9 abstract methods) -------------------------

    def list_windows(self) -> list[NativeHandle]:
        """List all visible top-level application windows.

        Uses ``self._desktop`` (stored at construction) to iterate the
        AT-SPI2 desktop children, collecting only those that:

        1. Have AT-SPI2 role ``ROLE_FRAME``, ``ROLE_DIALOG``, or
           ``ROLE_WINDOW`` (Architecture §5.3).
        2. Include the ``STATE_SHOWING`` state (off-screen / hidden
           windows are filtered out).
        3. Are not ``ROLE_DESKTOP_FRAME`` entries with an empty name
           (Architecture §5.3).

        Defunct or inaccessible children are silently skipped per
        Architecture §5.4.

        Returns:
            List of opaque native window handles (``pyatspi.Accessible``
            objects wrapped in :class:`NativeHandle`).

        Raises:
            BackendUnavailableError: If the backend is disposed.
        """
        if self._disposed:
            raise BackendUnavailableError("LinuxBackend has been disposed")

        import pyatspi

        _valid_roles = {
            pyatspi.ROLE_FRAME,
            pyatspi.ROLE_DIALOG,
            pyatspi.ROLE_WINDOW,
        }

        result: list[NativeHandle] = []
        for child in self._desktop.children:
            try:
                state_set = child.getState()
                if not state_set.contains(pyatspi.STATE_SHOWING):
                    continue
                role = child.get_role()
                if role not in _valid_roles:
                    continue
                if role == pyatspi.ROLE_DESKTOP_FRAME and not (child.get_name() or "").strip():
                    continue
                result.append(NativeHandle(child))
            except Exception:
                logger.debug("Skipping inaccessible desktop child", exc_info=True)
                continue
        return result

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
        """Find elements matching criteria within a window (GW-032).

        Walks the AT-SPI tree rooted at *window* and collects elements whose
        normalized role and/or accessible name match the given filters.

        Args:
            window: Opaque native window handle (``pyatspi.Accessible``).
            role: Normalized role to match (exact).
            name: Accessible name to match (case-insensitive substring).

        Returns:
            List of matching opaque native element handles.
        """
        if self._disposed:
            raise BackendUnavailableError("LinuxBackend has been disposed")

        # Require at least one filter criterion
        if role is None and name is None:
            return []

        from guidewire.models.mappings import resolve_role

        results: list[NativeHandle] = []
        try:
            self._find_recursive(window, role, name, resolve_role, results)
        except Exception:
            logger.debug("Error in find_elements tree walk", exc_info=True)

        return results

    def _find_recursive(
        self,
        accessible: Any,
        role: str | None,
        name: str | None,
        resolve_fn: Any,
        results: list[NativeHandle],
    ) -> None:
        """Recursively search for elements matching *role* and/or *name*.

        No depth limit — architecture §3.3 requires exhaustive traversal.
        Defunct or inaccessible children are silently skipped.
        """
        try:
            accessible.get_child_at_index(0)
        except Exception:
            return

        idx = 0
        while True:
            try:
                child = accessible.get_child_at_index(idx)
            except Exception:
                break
            if child is None:
                break

            try:
                # Extract and normalize role
                atspi_role_name = child.getRoleName()
                normalized_role = resolve_fn("linux", atspi_role_name) or atspi_role_name

                # Extract name
                child_name = child.get_name()

                # Match criteria
                role_match = role is None or normalized_role == role
                name_match = name is None or (
                    child_name is not None and name.lower() in child_name.lower()
                )

                if role_match and name_match:
                    results.append(NativeHandle(child))

                # Recurse into children
                self._find_recursive(child, role, name, resolve_fn, results)
            except Exception:
                logger.debug("Skipping inaccessible element in find_elements", exc_info=True)

            idx += 1

    def perform_action(
        self,
        handle: NativeHandle,
        action: DesktopAction,
        **kwargs: Any,
    ) -> Any:
        """Perform an action on an element via AT-SPI2 actions (GW-032).

        Maps each :class:`DesktopAction` variant to the appropriate AT-SPI2
        action or accessibility interface:

        - ``CLICK`` → AT-SPI ``Action.doAction('click')`` or ``doAction(0)``
        - ``TYPE`` → ``grabFocus()`` then pynput keyboard simulation
        - ``PRESS_KEY`` → ``grabFocus()`` then pynput keyboard simulation
        - ``SET_VALUE`` → ``Action.doAction('edit')`` with value parameter
        - ``SELECT`` → AT-SPI ``Action.doAction('select')``
        - ``SCROLL`` → AT-SPI ``Action.doAction('scroll')``
        - ``GET_TEXT`` → ``Accessible.get_text()`` via Text interface
        - ``TOGGLE`` → AT-SPI ``Action.doAction('toggle')``
        - ``EXPAND`` → AT-SPI ``Action.doAction('expand')``
        - ``COLLAPSE`` → AT-SPI ``Action.doAction('collapse')``
        - ``INCREMENT`` → AT-SPI ``Action.doAction('increment')``
        - ``DECREMENT`` → AT-SPI ``Action.doAction('decrement')``

        Args:
            handle: Opaque native element handle (``pyatspi.Accessible``).
            action: The action to perform.
            **kwargs: Action-specific parameters:
                - ``text`` (str): text to type (for ``TYPE``)
                - ``value`` (str): value to set (for ``SET_VALUE``)
                - ``key`` (str): key to press (for ``PRESS_KEY``)

        Returns:
            ``str`` when action is ``GET_TEXT``, otherwise ``None``.

        Raises:
            StaleElementReferenceError: If the backend is disposed or the
                element is no longer accessible.
            ActionNotSupportedError: If the element does not support the
                required action.
            ElementNotFoundError: If the handle is ``None`` or invalid.
        """
        if self._disposed:
            raise StaleElementReferenceError("LinuxBackend has been disposed")

        accessible = self._unwrap_element(handle)

        try:
            if action == DesktopAction.CLICK:
                return self._action_click(accessible)
            if action == DesktopAction.TYPE:
                return self._action_type(accessible, **kwargs)
            if action == DesktopAction.PRESS_KEY:
                return self._action_press_key(accessible, **kwargs)
            if action == DesktopAction.SET_VALUE:
                return self._action_set_value(accessible, **kwargs)
            if action == DesktopAction.SELECT:
                return self._action_select(accessible)
            if action == DesktopAction.SCROLL:
                return self._action_scroll(accessible)
            if action == DesktopAction.GET_TEXT:
                return self._action_get_text(accessible)
            if action == DesktopAction.TOGGLE:
                return self._action_toggle(accessible)
            if action == DesktopAction.EXPAND:
                return self._action_expand(accessible)
            if action == DesktopAction.COLLAPSE:
                return self._action_collapse(accessible)
            if action == DesktopAction.INCREMENT:
                return self._action_increment(accessible)
            if action == DesktopAction.DECREMENT:
                return self._action_decrement(accessible)
        except (ActionNotSupportedError, StaleElementReferenceError):
            raise
        except Exception as exc:
            raise ActionNotSupportedError(f"Failed to perform {action!r}: {exc}") from exc

    # -- Action dispatch helpers -----------------------------------------------

    @staticmethod
    def _unwrap_element(handle: NativeHandle) -> Any:
        """Extract the underlying ``pyatspi.Accessible`` from a NativeHandle.

        Args:
            handle: Opaque native element handle.

        Returns:
            The ``pyatspi.Accessible`` object.

        Raises:
            ElementNotFoundError: If the handle is ``None`` or empty.
        """
        if handle is None:
            raise ElementNotFoundError("Element handle is None")
        return handle

    def _get_action_interface(self, accessible: Any, action_name: str) -> Any:
        """Retrieve the AT-SPI Action interface from an accessible.

        Args:
            accessible: A ``pyatspi.Accessible`` object.
            action_name: The AT-SPI action name to look for.

        Returns:
            The ``pyatspi.Action`` interface object.

        Raises:
            ActionNotSupportedError: If the action interface is not available
                or the named action is not supported.
        """
        try:
            action_interface = accessible.queryAction()
        except Exception:
            raise ActionNotSupportedError(
                "Element does not support the Action interface"
            ) from None

        if action_interface is None:
            raise ActionNotSupportedError(
                "Element does not support the Action interface"
            )

        # Check if the named action exists
        n_actions = action_interface.get_n_actions()
        for i in range(n_actions):
            try:
                if action_interface.get_action_name(i) == action_name:
                    return action_interface
            except Exception:
                continue

        raise ActionNotSupportedError(
            f"Element does not support the '{action_name}' action"
        )

    def _do_action_by_name(self, accessible: Any, action_name: str) -> None:
        """Execute an AT-SPI action by name.

        Args:
            accessible: A ``pyatspi.Accessible`` object.
            action_name: The AT-SPI action name to execute.

        Raises:
            ActionNotSupportedError: If the action is not available.
        """
        action_interface = self._get_action_interface(accessible, action_name)
        try:
            action_interface.do_action(action_name)
        except ActionNotSupportedError:
            raise
        except Exception as exc:
            raise ActionNotSupportedError(f"Action '{action_name}' failed: {exc}") from exc

    def _action_click(self, accessible: Any) -> None:
        """Click an element via AT-SPI action.

        Tries 'click' action first, then falls back to 'press' and 'activate'.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If no click action is available.
        """
        # First check if the Action interface exists at all
        try:
            accessible.queryAction()
        except Exception:
            raise ActionNotSupportedError(
                "Element does not support the Action interface"
            ) from None

        for action_name in ("click", "press", "activate"):
            try:
                self._do_action_by_name(accessible, action_name)
                return
            except ActionNotSupportedError:
                continue
        raise ActionNotSupportedError(
            "Element does not support any click action (click, press, activate)"
        )

    def _action_type(self, accessible: Any, **kwargs: Any) -> None:
        """Type text into an element.

        Sets focus on the element, then simulates keyboard input via
        ``pynput``.  Falls back to setting focus only if pynput is unavailable.

        Args:
            accessible: A ``pyatspi.Accessible`` object.
            **kwargs: Must contain ``text`` (str).

        Raises:
            ActionNotSupportedError: If text parameter is missing.
        """
        text = kwargs.get("text")
        if text is None:
            raise ActionNotSupportedError("TYPE action requires a 'text' parameter")

        # Set focus on the element
        self._grab_focus(accessible)

        # Simulate keyboard input via pynput
        self._send_text(str(text))

    def _action_press_key(self, accessible: Any, **kwargs: Any) -> None:
        """Press a key while an element has focus.

        Sets focus on the element, then simulates the key press via
        ``pynput``.

        Args:
            accessible: A ``pyatspi.Accessible`` object.
            **kwargs: Must contain ``key`` (str).

        Raises:
            ActionNotSupportedError: If key parameter is missing.
        """
        key = kwargs.get("key")
        if key is None:
            raise ActionNotSupportedError("PRESS_KEY action requires a 'key' parameter")

        # Set focus on the element
        self._grab_focus(accessible)

        # Simulate key press via pynput
        self._send_key(str(key))

    def _action_set_value(self, accessible: Any, **kwargs: Any) -> None:
        """Set the value of an element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.
            **kwargs: Must contain ``value`` (str).

        Raises:
            ActionNotSupportedError: If value parameter is missing or the
                action is not supported.
        """
        value = kwargs.get("value")
        if value is None:
            raise ActionNotSupportedError("SET_VALUE action requires a 'value' parameter")

        # Try AT-SPI 'edit' action first
        for action_name in ("edit",):
            try:
                action_interface = self._get_action_interface(accessible, action_name)
                try:
                    action_interface.do_action(action_name)
                    return
                except Exception:
                    pass
            except ActionNotSupportedError:
                continue

        # Try setting via Text interface
        try:
            text_interface = accessible.queryText()
            if text_interface is not None:
                text_interface.set_text_content(str(value))
                return
        except Exception:
            pass

        raise ActionNotSupportedError(
            "Element does not support setting value (no edit action or Text interface)"
        )

    def _action_select(self, accessible: Any) -> None:
        """Select an element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If select action is not available.
        """
        self._do_action_by_name(accessible, "select")

    def _action_scroll(self, accessible: Any) -> None:
        """Scroll an element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If scroll action is not available.
        """
        for action_name in ("scroll", "scrollUp", "scrollDown", "scrollLeft", "scrollRight"):
            try:
                self._do_action_by_name(accessible, action_name)
                return
            except ActionNotSupportedError:
                continue
        raise ActionNotSupportedError(
            "Element does not support any scroll action"
        )

    def _action_get_text(self, accessible: Any) -> str:
        """Get the text value of an element.

        Tries the AT-SPI Text interface first, then falls back to the
        accessible name.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Returns:
            The current text string.

        Raises:
            ActionNotSupportedError: If text cannot be retrieved.
        """
        # Try the Text interface first
        try:
            text_interface = accessible.queryText()
            if text_interface is not None:
                text = text_interface.get_text(0, text_interface.character_count)
                return str(text) if text else ""
        except Exception:
            pass

        # Fall back to accessible name
        try:
            name = accessible.get_name()
            return str(name) if name else ""
        except Exception as exc:
            raise ActionNotSupportedError(f"Failed to get text: {exc}") from exc

    def _action_toggle(self, accessible: Any) -> None:
        """Toggle an element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If toggle action is not available.
        """
        self._do_action_by_name(accessible, "toggle")

    def _action_expand(self, accessible: Any) -> None:
        """Expand an element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If expand action is not available.
        """
        self._do_action_by_name(accessible, "expand")

    def _action_collapse(self, accessible: Any) -> None:
        """Collapse an element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If collapse action is not available.
        """
        self._do_action_by_name(accessible, "collapse")

    def _action_increment(self, accessible: Any) -> None:
        """Increment a value element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If increment action is not available.
        """
        self._do_action_by_name(accessible, "increment")

    def _action_decrement(self, accessible: Any) -> None:
        """Decrement a value element via AT-SPI action.

        Args:
            accessible: A ``pyatspi.Accessible`` object.

        Raises:
            ActionNotSupportedError: If decrement action is not available.
        """
        self._do_action_by_name(accessible, "decrement")

    # -- Keyboard simulation helpers -------------------------------------------

    @staticmethod
    def _grab_focus(accessible: Any) -> None:
        """Set accessibility focus on an element.

        Uses the AT-SPI ``grabFocus`` action if available, otherwise
        uses the ``setState`` method.

        Args:
            accessible: A ``pyatspi.Accessible`` object.
        """
        try:
            action = accessible.queryAction()
            if action is not None:
                n_actions = action.get_n_actions()
                for i in range(n_actions):
                    if action.get_action_name(i) == "grabFocus":
                        action.do_action(i)
                        return
        except Exception:
            pass

    @staticmethod
    def _send_text(text: str) -> None:
        """Simulate typing text via ``pynput`` keyboard simulation.

        Falls back silently if pynput is not available (Linux server
        environments may lack a display).

        Args:
            text: The text string to type.
        """
        try:
            from pynput.keyboard import Controller

            keyboard = Controller()
            keyboard.type(text)
        except Exception:
            logger.debug("pynput keyboard simulation unavailable", exc_info=True)

    @staticmethod
    def _send_key(key: str) -> None:
        """Simulate a single key press via ``pynput`` keyboard simulation.

        Falls back silently if pynput is not available.

        Args:
            key: The key name (e.g. ``"Enter"``, ``"Tab"``, ``"escape"``).
        """
        try:
            from pynput.keyboard import Controller, Key

            keyboard = Controller()
            key_map: dict[str, Any] = {
                "enter": Key.enter,
                "tab": Key.tab,
                "escape": Key.esc,
                "backspace": Key.backspace,
                "delete": Key.delete,
                "arrowup": Key.up,
                "arrowdown": Key.down,
                "arrowleft": Key.left,
                "arrowright": Key.right,
                "home": Key.home,
                "end": Key.end,
                "pageup": Key.page_up,
                "pagedown": Key.page_down,
                "space": Key.space,
                "f1": Key.f1,
                "f2": Key.f2,
                "f3": Key.f3,
                "f4": Key.f4,
                "f5": Key.f5,
                "f6": Key.f6,
                "f7": Key.f7,
                "f8": Key.f8,
                "f9": Key.f9,
                "f10": Key.f10,
                "f11": Key.f11,
                "f12": Key.f12,
            }

            mapped = key_map.get(key.lower())
            if mapped is not None:
                keyboard.press(mapped)
                keyboard.release(mapped)
            elif len(key) == 1:
                keyboard.press(key)
                keyboard.release(key)
        except Exception:
            logger.debug("pynput keyboard simulation unavailable", exc_info=True)

    def get_element_info(self, handle: NativeHandle) -> dict[str, Any]:
        """Return element metadata as a dict (GW-032).

        Reads the following AT-SPI2 properties from the accessible:
        - ``getRoleName()`` → normalized role via ``resolve_role``
        - ``get_name()`` → ``name``
        - State set → normalized states via ``normalize_states``

        Args:
            handle: Opaque native element handle (``pyatspi.Accessible``).

        Returns:
            Dict with keys ``role``, ``name``, ``states``.

        Raises:
            ElementNotFoundError: If the handle is ``None`` or invalid.
            StaleElementReferenceError: If the backend is disposed.
        """
        if self._disposed:
            raise StaleElementReferenceError("LinuxBackend has been disposed")

        accessible = self._unwrap_element(handle)

        try:
            from dataclasses import fields as _dc_fields

            from guidewire.backends.normalize import normalize_states
            from guidewire.models.mappings import resolve_role

            # Read role
            atspi_role_name = accessible.getRoleName()
            role = resolve_role("linux", atspi_role_name) or atspi_role_name

            # Read name
            name = accessible.get_name()
            name_str = str(name) if name else None

            # Read states from the AT-SPI state set
            # Only include states that map to ElementStates fields
            state_set = accessible.getState()
            raw_states: dict[str, Any] = {}

            import pyatspi

            state_key_to_constant = {
                "enabled": pyatspi.STATE_ENABLED,
                "focused": pyatspi.STATE_FOCUSED,
                "selected": pyatspi.STATE_SELECTED,
                "checked": pyatspi.STATE_CHECKED,
                "expanded": pyatspi.STATE_EXPANDED,
                "visible": pyatspi.STATE_VISIBLE,
                "showing": pyatspi.STATE_SHOWING,
                "offscreen": pyatspi.STATE_OFFSCREEN,
                "read-only": pyatspi.STATE_READ_ONLY,
                "required": pyatspi.STATE_REQUIRED,
            }

            for state_key, state_const in state_key_to_constant.items():
                try:
                    if state_set.contains(state_const):
                        raw_states[state_key] = True
                    else:
                        raw_states[state_key] = False
                except Exception:
                    pass

            norm_states = normalize_states("linux", raw_states)
            states_dict = {
                f.name: getattr(norm_states, f.name)
                for f in _dc_fields(norm_states)
                if getattr(norm_states, f.name) is not None
            }

            return {
                "role": role,
                "name": name_str,
                "states": states_dict,
            }
        except ElementNotFoundError:
            raise
        except StaleElementReferenceError:
            raise
        except Exception as exc:
            raise ElementNotFoundError(f"Failed to read element info: {exc}") from exc

    def is_valid(self, element: NativeHandle) -> bool:
        """Check whether a native element reference is still valid (GW-032).

        Uses a lightweight ``getState`` probe on the underlying
        ``pyatspi.Accessible`` to detect stale handles.

        This method must **never** raise — the tool layer calls it outside
        any ``try / except`` block, so any exception would propagate as an
        unhandled MCP error.

        Args:
            element: Opaque native element handle (``pyatspi.Accessible``).

        Returns:
            ``True`` if the element still exists in the accessibility tree,
            ``False`` otherwise (including when the backend is disposed).
        """
        if self._disposed:
            return False

        if element is None:
            return False

        try:
            element.getState()
            return True
        except Exception:
            return False

    def dispose(self) -> None:
        """Release all resources held by this backend.

        Clears the desktop reference and marks the backend as disposed.

        Called when the MCP server shuts down.
        """
        if self._disposed:
            return
        self._desktop = None
        self._disposed = True
