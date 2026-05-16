"""Cross-platform element normalization.

Converts raw platform property dicts into :class:`NormalizedElement`
dataclass instances using the mapping tables from :mod:`guidewire.models.mappings`.

Usage::

    from guidewire.backends.normalize import normalize_element

    element = normalize_element(
        platform="windows",
        ref="e0",
        backend_id="hwnd:12345",
        role="Button",
        name="OK",
        native_role="Button",
        control_type="Button",
        raw_states={"IsEnabled": True, "HasKeyboardFocus": False},
        bounds=(10, 20, 100, 30),
        raw_actions=["InvokePattern", "TogglePattern"],
        description=None,
        value=None,
        text=None,
        children=None,
    )
"""

from typing import Any, Literal

from guidewire.models import Bounds, DesktopAction, ElementStates, NormalizedElement
from guidewire.models.mappings import (
    resolve_action,
    resolve_role,
    resolve_state,
)

__all__ = [
    "normalize_element",
    "normalize_states",
]

# -- Platform literal type ---------------------------------------------------

Platform = Literal["windows", "linux"]


def normalize_states(
    platform: str,
    raw_states: dict[str, Any],
) -> ElementStates:
    """Convert a raw platform state dict into an :class:`ElementStates` instance.

    Iterates over the *raw_states* dict and resolves each key via
    :func:`~guidewire.models.mappings.resolve_state`.  Only recognized
    state keys produce fields in the result; unknown keys are silently
    skipped so that future platform additions are safe.

    Args:
        platform: ``"windows"`` or ``"linux"``.
        raw_states: Mapping of native state/property names to their raw values
            (e.g. ``{"IsEnabled": True, "ToggleState": 1}``).

    Returns:
        A frozen :class:`ElementStates` with all resolved fields populated.
    """
    resolved: dict[str, Any] = {}
    for key, value in raw_states.items():
        result = resolve_state(platform, key, value)
        if result is not None:
            field_name, normalized_value = result
            resolved[field_name] = normalized_value

    return ElementStates(**resolved)


def normalize_actions(
    platform: str,
    raw_actions: list[str],
) -> list[DesktopAction]:
    """Convert a list of raw platform action/pattern names to normalized actions.

    Filters to only recognized actions and deduplicates while preserving order.

    Args:
        platform: ``"windows"`` or ``"linux"``.
        raw_actions: List of native action or pattern identifiers
            (e.g. ``["InvokePattern", "ValuePattern"]``).

    Returns:
        Deduplicated list of normalized :class:`DesktopAction` strings.
    """
    seen: set[str] = set()
    result: list[DesktopAction] = []
    for raw in raw_actions:
        action = resolve_action(platform, raw)
        if action is not None and action not in seen:
            seen.add(action)
            result.append(action)
    return result


def normalize_bounds(raw_bounds: Any) -> Bounds | None:
    """Convert a raw bounds tuple/dict into a :class:`Bounds` instance.

    Accepts:
        - A tuple/list of ``(x, y, width, height)`` (int or float).
        - A dict with keys ``x``, ``y``, ``width``, ``height``.
        - ``None`` — returns ``None``.

    Returns:
        A :class:`Bounds` instance, or ``None`` if *raw_bounds* is falsy or
        has zero area.
    """
    if raw_bounds is None:
        return None

    if isinstance(raw_bounds, dict):
        x = float(raw_bounds.get("x", 0))
        y = float(raw_bounds.get("y", 0))
        w = float(raw_bounds.get("width", 0))
        h = float(raw_bounds.get("height", 0))
    elif hasattr(raw_bounds, "__len__") and len(raw_bounds) == 4:
        x, y, w, h = (float(v) for v in raw_bounds)
    else:
        return None

    return Bounds(x=x, y=y, width=w, height=h)


def normalize_element(
    platform: str,
    ref: str,
    backend_id: str,
    role: str,
    *,
    native_role: str | None = None,
    control_type: str | None = None,
    name: str | None = None,
    description: str | None = None,
    value: str | None = None,
    text: str | None = None,
    raw_states: dict[str, Any] | None = None,
    bounds: Any = None,
    raw_actions: list[str] | None = None,
    children: list[NormalizedElement] | None = None,
) -> NormalizedElement:
    """Build a :class:`NormalizedElement` from raw platform properties.

    This is the single entry-point that the Windows and Linux backends call
    to convert raw accessibility API output into the cross-platform model.

    Role resolution falls back to the raw *role* string when the mapping
    tables have no entry, so the consumer always gets *some* role string.

    Args:
        platform: ``"windows"`` or ``"linux"``.
        ref: Short-lived reference handle (e.g. ``"e42"``).
        backend_id: Opaque platform-specific identifier.
        role: The raw platform role string (e.g. ``"Button"``, ``"push button"``).
            Will be resolved via :func:`resolve_role`; falls back to the raw value.
        native_role: The original platform role string (for diagnostics).
        control_type: Platform-specific control type name (Windows only).
        name: Accessible name.
        description: Accessible description / help text.
        value: Current element value (e.g. slider position).
        text: Text content exposed by the element.
        raw_states: Dict of native state/property names to raw values.
        bounds: Bounding rectangle as tuple ``(x, y, w, h)`` or dict.
        raw_actions: List of native action/pattern identifiers.
        children: Already-normalized child elements.

    Returns:
        A fully-populated :class:`NormalizedElement`.
    """
    # Resolve role — fall back to the raw value so we never return an empty role.
    normalized_role = resolve_role(platform, role) or role.lower()

    # Resolve states.
    states = normalize_states(platform, raw_states or {})

    # Resolve bounds.
    norm_bounds = normalize_bounds(bounds)

    # Resolve actions.
    actions = normalize_actions(platform, raw_actions or [])

    return NormalizedElement(
        ref=ref,
        backend_id=backend_id,
        role=normalized_role,
        native_role=native_role,
        control_type=control_type,
        name=name,
        description=description,
        value=value,
        text=text,
        states=states,
        bounds=norm_bounds,
        actions=actions,
        children=children,
    )
