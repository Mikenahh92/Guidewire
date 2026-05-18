"""Element and system-action risk classification for the Guidewire Desktop
Accessibility MCP server.

Provides a three-tier risk model (PRD R12) so that tool handlers can attach
risk metadata to MCP responses without blocking actions.

Risk levels
-----------
READ_ONLY
    Elements that merely expose information (labels, static text, images).
    Reading or querying these elements has negligible side-effects.

INTERACTION
    Elements that accept user input but have limited blast radius
    (text inputs, combo boxes, sliders, checkboxes, menus).

SENSITIVE
    Elements whose activation can cause significant side-effects
    (buttons that submit, delete, or invoke destructive actions; password
    fields; OS-level controls).

System actions
--------------
System actions are non-element operations that the MCP server can perform,
such as launching an application or writing to the clipboard.  They are
classified with the same three-tier model via
:func:`classify_system_action`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from guidewire.models import DesktopAction, NormalizedElement

# ---------------------------------------------------------------------------
# Risk level type
# ---------------------------------------------------------------------------

RiskLevel = Literal["READ_ONLY", "INTERACTION", "SENSITIVE"]

# ---------------------------------------------------------------------------
# Sensitive roles — activation causes significant side-effects
# ---------------------------------------------------------------------------

SENSITIVE_ROLES: frozenset[str] = frozenset(
    {
        "delete_button",
        "remove_button",
        "clear_button",
        "password_field",
        "credential_field",
    }
)

# ---------------------------------------------------------------------------
# Destructive name heuristics — case-insensitive substring patterns
# ---------------------------------------------------------------------------

DESTRUCTIVE_NAME_PATTERNS: tuple[str, ...] = (
    "delete",
    "remove",
    "clear",
    "destroy",
    "erase",
    "purge",
    "drop",
    "discard",
    "nuke",
    "obliterate",
    "wipe",
    "format",
    "reset",
    "uninstall",
)

# ---------------------------------------------------------------------------
# Actions that always return READ_ONLY
# ---------------------------------------------------------------------------

_FOCUS_ONLY_ACTIONS: frozenset[str] = frozenset({"focus"})


# ---------------------------------------------------------------------------
# Risk assessment result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Result of classifying an element-action pair.

    Attributes:
        risk_level: One of ``"READ_ONLY"``, ``"INTERACTION"``, or
            ``"SENSITIVE"``.
        confirmation_required: Whether user confirmation should be requested
            before performing the action.
        reason: Human-readable explanation for the assigned risk level.
        confidence: Classification confidence (0.0-1.0).
    """

    risk_level: RiskLevel
    confirmation_required: bool
    reason: str
    confidence: float


# ---------------------------------------------------------------------------
# Classification function
# ---------------------------------------------------------------------------


def classify(
    element: NormalizedElement,
    action: DesktopAction,
) -> RiskAssessment:
    """Return a :class:`RiskAssessment` for the given element-action pair.

    The classification follows PRD R12 three-tier model:

    * ``READ_ONLY`` — informational / container elements, or focus-only
      actions on any element.
    * ``INTERACTION`` — input elements with limited blast radius (default).
    * ``SENSITIVE`` — elements whose activation may cause significant
      side-effects (delete/remove/clear buttons, destructive names, disabled
      elements).

    Args:
        element: A :class:`~guidewire.models.NormalizedElement` instance.
        action: The :data:`~guidewire.models.DesktopAction` being performed.

    Returns:
        A frozen :class:`RiskAssessment` dataclass with risk metadata.
    """
    # --- Rule 1: disabled elements are always READ_ONLY ---
    if element.states.enabled is False:
        return RiskAssessment(
            risk_level="READ_ONLY",
            confirmation_required=False,
            reason="Element is disabled",
            confidence=1.0,
        )

    # --- Rule 2: focus always returns READ_ONLY ---
    if action in _FOCUS_ONLY_ACTIONS:
        return RiskAssessment(
            risk_level="READ_ONLY",
            confirmation_required=False,
            reason="Focus action is always read-only",
            confidence=1.0,
        )

    # --- Rule 3: SENSITIVE roles from ROLE_RISK_MAP ---
    if ROLE_RISK_MAP.get(element.role) == "SENSITIVE":
        return RiskAssessment(
            risk_level="SENSITIVE",
            confirmation_required=True,
            reason=f"Sensitive role: {element.role}",
            confidence=1.0,
        )

    # --- Rule 4: destructive name heuristics ---
    name_lower = (element.name or "").lower()
    for pattern in DESTRUCTIVE_NAME_PATTERNS:
        if pattern in name_lower:
            return RiskAssessment(
                risk_level="SENSITIVE",
                confirmation_required=True,
                reason=f"Destructive name pattern matched: '{pattern}'",
                confidence=0.9,
            )

    # --- Rule 5: READ_ONLY roles from ROLE_RISK_MAP ---
    if ROLE_RISK_MAP.get(element.role) == "READ_ONLY":
        return RiskAssessment(
            risk_level="READ_ONLY",
            confirmation_required=False,
            reason=f"Read-only role: {element.role}",
            confidence=1.0,
        )

    # --- Default: INTERACTION ---
    return RiskAssessment(
        risk_level="INTERACTION",
        confirmation_required=False,
        reason="Default classification for interactive element",
        confidence=0.8,
    )


# ---------------------------------------------------------------------------
# ROLE_RISK_MAP — maps known roles to their default risk level
# ---------------------------------------------------------------------------

ROLE_RISK_MAP: dict[str, RiskLevel] = {
    # READ_ONLY — informational / container elements
    "label": "READ_ONLY",
    "text": "READ_ONLY",
    "heading": "READ_ONLY",
    "link": "READ_ONLY",
    "image": "READ_ONLY",
    "icon": "READ_ONLY",
    "list": "READ_ONLY",
    "list_item": "READ_ONLY",
    "table": "READ_ONLY",
    "table_row": "READ_ONLY",
    "table_column_header": "READ_ONLY",
    "table_header": "READ_ONLY",
    "table_cell": "READ_ONLY",
    "datagrid": "READ_ONLY",
    "data_item": "READ_ONLY",
    "header_item": "READ_ONLY",
    "progress_bar": "READ_ONLY",
    "separator": "READ_ONLY",
    "group": "READ_ONLY",
    "tab_bar": "READ_ONLY",
    "tooltip": "READ_ONLY",
    "status_bar": "READ_ONLY",
    "title_bar": "READ_ONLY",
    "chart": "READ_ONLY",
    "dialog": "READ_ONLY",
    "window": "READ_ONLY",
    "pane": "READ_ONLY",
    "document": "READ_ONLY",
    "page_tab_list": "READ_ONLY",
    # SENSITIVE — activation causes significant side-effects
    "delete_button": "SENSITIVE",
    "remove_button": "SENSITIVE",
    "clear_button": "SENSITIVE",
    "password_field": "SENSITIVE",
    "credential_field": "SENSITIVE",
}


# ---------------------------------------------------------------------------
# System-action type
# ---------------------------------------------------------------------------

SystemAction = Literal[
    "app_launch",
    "app_close",
    "clipboard_read",
    "clipboard_write",
    "screenshot",
    "window_list",
    "window_focus",
    "window_close",
    "window_manage",
    "system_info",
]

# ---------------------------------------------------------------------------
# SYSTEM_ACTION_RISK_MAP — maps system actions to their default risk level
# ---------------------------------------------------------------------------

SYSTEM_ACTION_RISK_MAP: dict[SystemAction, RiskLevel] = {
    "app_launch": "SENSITIVE",
    "app_close": "SENSITIVE",
    "clipboard_read": "INTERACTION",
    "clipboard_write": "SENSITIVE",
    "screenshot": "INTERACTION",
    "window_list": "READ_ONLY",
    "window_focus": "INTERACTION",
    "window_close": "SENSITIVE",
    "window_manage": "INTERACTION",
    "system_info": "READ_ONLY",
}


# ---------------------------------------------------------------------------
# System-action classification function
# ---------------------------------------------------------------------------


def classify_system_action(
    action: SystemAction,
    *,
    target: str | None = None,
) -> RiskAssessment:
    """Return a :class:`RiskAssessment` for a non-element system action.

    System actions are operations that do not target a specific accessibility
    element — for example launching an application or writing to the OS
    clipboard.  They use the same PRD R12 three-tier risk model as
    :func:`classify` but are keyed by action name rather than element role.

    Args:
        action: The system action being performed (e.g. ``"app_launch"``).
        target: An optional human-readable target identifier (e.g. the
            application name or clipboard data description).  Used to enrich
            the reason string but does not affect risk level.

    Returns:
        A frozen :class:`RiskAssessment` dataclass with risk metadata.
        Unknown actions default to SENSITIVE as a safe fallback.
    """
    known = action in SYSTEM_ACTION_RISK_MAP
    if not known:
        risk_level: RiskLevel = "SENSITIVE"
    else:
        risk_level = SYSTEM_ACTION_RISK_MAP[action]

    confirmation_required = risk_level == "SENSITIVE"
    target_clause = f" on '{target}'" if target else ""
    if not known:
        reason = f"Unknown system action '{action}'{target_clause} defaults to SENSITIVE"
        confidence = 0.8
    else:
        reason = _system_action_reason(action, risk_level, target_clause)
        confidence = 1.0

    return RiskAssessment(
        risk_level=risk_level,
        confirmation_required=confirmation_required,
        reason=reason,
        confidence=confidence,
    )


def _system_action_reason(
    action: SystemAction,
    risk_level: RiskLevel,
    target_clause: str,
) -> str:
    """Build a human-readable reason string for a system action."""
    if risk_level == "SENSITIVE":
        return f"System action '{action}'{target_clause} requires confirmation"
    if risk_level == "READ_ONLY":
        return f"System action '{action}'{target_clause} is read-only"
    return f"System action '{action}'{target_clause} is an interaction"


__all__ = [
    "DESTRUCTIVE_NAME_PATTERNS",
    "ROLE_RISK_MAP",
    "SENSITIVE_ROLES",
    "SYSTEM_ACTION_RISK_MAP",
    "RiskAssessment",
    "RiskLevel",
    "SystemAction",
    "classify",
    "classify_system_action",
]
