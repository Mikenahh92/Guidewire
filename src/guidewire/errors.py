"""Structured error codes for the Guidewire Desktop Accessibility MCP server.

Every failure mode exposed by the MCP layer maps to a distinct, catchable
exception class carrying a machine-readable ``error_code`` string.  This allows
callers (and MCP clients) to programmatically distinguish error categories
without parsing free-text messages.

The six codes below are drawn from PRD §25 (Error Model).
"""


class GuidewireError(Exception):
    """Base exception for all Guidewire errors.

    Attributes:
        error_code: Machine-readable error identifier (e.g. ``"backend_unavailable"``).
        message: Human-readable description of the failure.
    """

    error_code: str = "guidewire_error"

    def __init__(self, message: str = "") -> None:
        self.message = message or self.__doc__ or ""
        super().__init__(self.message)


class BackendUnavailableError(GuidewireError):
    """The platform accessibility backend could not be initialized or is unreachable."""

    error_code = "backend_unavailable"


class ElementNotFoundError(GuidewireError):
    """The requested UI element could not be located."""

    error_code = "element_not_found"


class StaleElementReferenceError(GuidewireError):
    """The referenced element no longer exists in the accessibility tree."""

    error_code = "stale_element_reference"


class ActionNotSupportedError(GuidewireError):
    """The requested action is not supported by the target element."""

    error_code = "action_not_supported"


class PermissionRequiredError(GuidewireError):
    """OS-level accessibility permission is required but has not been granted."""

    error_code = "permission_required"


class AmbiguousSelectorError(GuidewireError):
    """The selector matched multiple elements instead of a single target."""

    error_code = "ambiguous_selector"


class WindowNotFoundError(GuidewireError):
    """The specified window could not be found or no longer exists."""

    error_code = "window_not_found"


__all__ = [
    "ActionNotSupportedError",
    "AmbiguousSelectorError",
    "BackendUnavailableError",
    "ElementNotFoundError",
    "GuidewireError",
    "PermissionRequiredError",
    "StaleElementReferenceError",
    "WindowNotFoundError",
]
