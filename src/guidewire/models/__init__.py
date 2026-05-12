"""Guidewire cross-platform element model.

This package defines the shared data model that all platform backends
(Windows UIA, Linux AT-SPI) normalize into.

Public API::

    from guidewire.models import (
        Bounds,
        DesktopAction,
        ElementStates,
        NormalizedElement,
    )

Submodules
----------
element
    Core dataclasses: :class:`NormalizedElement`, :class:`Bounds`,
    :class:`ElementStates`, and the :data:`DesktopAction` type alias.
mappings
    Platform role/state/action mapping tables keyed by ``(platform, key)``
    tuples.
"""

from dataclasses import dataclass, field, fields
from typing import Any, Literal

# ---------------------------------------------------------------------------
# DesktopAction type
# ---------------------------------------------------------------------------

DesktopAction = Literal[
    "click",
    "focus",
    "type",
    "set_value",
    "select",
    "toggle",
    "expand",
    "collapse",
    "scroll",
    "increment",
    "decrement",
    "open_menu",
    "invoke",
]


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Bounds:
    """Screen-coordinate bounding rectangle for an element.

    Attributes:
        x: Left edge in screen pixels (float for DPI-aware coordinates).
        y: Top edge in screen pixels.
        width: Width in pixels.
        height: Height in pixels.
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def is_empty(self) -> bool:
        """Return ``True`` when the rectangle has zero area."""
        return self.width <= 0 or self.height <= 0

    @property
    def center(self) -> tuple[float, float]:
        """Return the ``(x, y)`` center of the rectangle."""
        return (self.x + self.width / 2, self.y + self.height / 2)


# ---------------------------------------------------------------------------
# ElementStates
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ElementStates:
    """Normalized accessibility states for an element.

    All fields default to ``None`` (unknown / not reported) rather than
    ``False`` so that consumers can distinguish "explicitly off" from
    "not applicable".

    Attributes:
        enabled: Whether the element is interactive.
        focused: Whether the element currently has keyboard focus.
        selected: Whether the element is selected within its container.
        checked: Whether a checkable element is checked.  May be
            ``"mixed"`` for tri-state controls.
        expanded: Whether a collapsible element is expanded.
        visible: Whether the element is visible on screen.
        offscreen: Whether the element is clipped or positioned offscreen.
        read_only: Whether the element rejects value changes.
        required: Whether the element must be filled for form submission.
    """

    enabled: bool | None = None
    focused: bool | None = None
    selected: bool | None = None
    checked: bool | Literal["mixed"] | None = None
    expanded: bool | None = None
    visible: bool | None = None
    offscreen: bool | None = None
    read_only: bool | None = None
    required: bool | None = None

    # --- Convenience helpers ------------------------------------------------

    @property
    def is_interactive(self) -> bool:
        """Return ``True`` when the element accepts user input."""
        return self.enabled is not False

    @property
    def is_checked(self) -> bool | None:
        """Return the checked state as a strict bool (``None`` if mixed)."""
        if self.checked == "mixed":
            return None
        return bool(self.checked) if self.checked is not None else None


# ---------------------------------------------------------------------------
# NormalizedElement
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class NormalizedElement:
    """The cross-platform, normalized accessibility element.

    Every backend (Windows UIA, Linux AT-SPI) produces instances
    of this class so that downstream tooling and MCP clients see a uniform
    shape regardless of the underlying platform.

    Attributes:
        ref: Short-lived reference handle (e.g. ``"e42"``).  Assigned by
            the reference store and valid only for the current snapshot
            generation.
        backend_id: Opaque platform-specific identifier that the backend
            can use to re-acquire the native element.
        role: Normalized role string (e.g. ``"button"``, ``"text_input"``).
            Use :func:`~guidewire.models.mappings.resolve_role` to produce this
            from a platform-specific role.
        native_role: The original platform role string, kept for debugging
            and diagnostics.
        control_type: Platform-specific control-type identifier (Windows
            UIA ``ControlType`` name).  ``None`` on non-Windows platforms.
        name: Accessible name reported by the element.
        description: Accessible description / help text.
        value: Current value of the element (e.g. slider position).
        text: Text content exposed by the element.
        states: Normalized state flags.
        bounds: Screen-coordinate bounding rectangle.
        actions: List of normalized actions the element supports.
        children: Child elements, if populated by the snapshot.
    """

    ref: str
    backend_id: str
    role: str
    native_role: str | None = None
    control_type: str | None = None
    name: str | None = None
    description: str | None = None
    value: str | None = None
    text: str | None = None
    states: ElementStates = field(default_factory=ElementStates)
    bounds: Bounds | None = None
    actions: list[DesktopAction] = field(default_factory=list)
    children: list["NormalizedElement"] | None = None

    # --- Convenience helpers ------------------------------------------------

    def walk(self) -> list["NormalizedElement"]:
        """Return a flat list of this element and all descendants."""
        result: list[NormalizedElement] = [self]
        for child in self.children or []:
            result.extend(child.walk())
        return result

    def find_by_role(self, role: str) -> list["NormalizedElement"]:
        """Return all descendants (including self) matching *role*."""
        return [e for e in self.walk() if e.role == role]

    def find_by_ref(self, ref: str) -> "NormalizedElement | None":
        """Return the descendant (or self) matching *ref*, if any."""
        for e in self.walk():
            if e.ref == ref:
                return e
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary (useful for JSON encoding)."""
        result: dict[str, Any] = {
            "ref": self.ref,
            "backend_id": self.backend_id,
            "role": self.role,
        }
        if self.native_role is not None:
            result["native_role"] = self.native_role
        if self.control_type is not None:
            result["control_type"] = self.control_type
        if self.name is not None:
            result["name"] = self.name
        if self.description is not None:
            result["description"] = self.description
        if self.value is not None:
            result["value"] = self.value
        if self.text is not None:
            result["text"] = self.text
        result["states"] = {
            f.name: getattr(self.states, f.name)
            for f in fields(self.states)
            if getattr(self.states, f.name) is not None
        }
        if self.bounds is not None:
            result["bounds"] = {
                "x": self.bounds.x,
                "y": self.bounds.y,
                "width": self.bounds.width,
                "height": self.bounds.height,
            }
        result["actions"] = list(self.actions)
        children = self.children
        if children:
            result["children"] = [c.to_dict() for c in children]
        return result


__all__ = [
    "Bounds",
    "DesktopAction",
    "ElementStates",
    "NormalizedElement",
]
