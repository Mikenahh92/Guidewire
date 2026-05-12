"""Tests for guidewire.errors — PRD R14 structured error codes."""

import pytest

from guidewire.errors import (
    ActionNotSupportedError,
    AmbiguousSelectorError,
    BackendUnavailableError,
    ElementNotFoundError,
    GuidewireError,
    PermissionRequiredError,
    StaleElementReferenceError,
    WindowNotFoundError,
)

# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------


class TestInheritance:
    """Every concrete error must inherit from GuidewireError."""

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_concrete_errors_inherit_base(self, cls: type) -> None:
        assert issubclass(cls, GuidewireError)

    def test_base_is_exception(self) -> None:
        assert issubclass(GuidewireError, Exception)


# ---------------------------------------------------------------------------
# Machine-readable error codes
# ---------------------------------------------------------------------------


class TestCodes:
    """Each error class carries a unique, snake_case error_code string."""

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (BackendUnavailableError, "backend_unavailable"),
            (ElementNotFoundError, "element_not_found"),
            (StaleElementReferenceError, "stale_element_reference"),
            (ActionNotSupportedError, "action_not_supported"),
            (PermissionRequiredError, "permission_required"),
            (AmbiguousSelectorError, "ambiguous_selector"),
            (WindowNotFoundError, "window_not_found"),
        ],
    )
    def test_error_code_value(self, cls: type[GuidewireError], expected: str) -> None:
        assert cls.error_code == expected

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_error_code_on_instance(self, cls: type[GuidewireError]) -> None:
        instance = cls()
        assert instance.error_code == cls.error_code

    def test_error_codes_are_unique(self) -> None:
        codes = [
            BackendUnavailableError.error_code,
            ElementNotFoundError.error_code,
            StaleElementReferenceError.error_code,
            ActionNotSupportedError.error_code,
            PermissionRequiredError.error_code,
            AmbiguousSelectorError.error_code,
            WindowNotFoundError.error_code,
        ]
        assert len(codes) == len(set(codes))

    def test_base_code_is_not_reused(self) -> None:
        concrete_codes = [
            BackendUnavailableError.error_code,
            ElementNotFoundError.error_code,
            StaleElementReferenceError.error_code,
            ActionNotSupportedError.error_code,
            PermissionRequiredError.error_code,
            AmbiguousSelectorError.error_code,
            WindowNotFoundError.error_code,
        ]
        assert GuidewireError.error_code not in concrete_codes


# ---------------------------------------------------------------------------
# Constructibility & message handling
# ---------------------------------------------------------------------------


class TestConstruction:
    """Errors can be raised with an optional human-readable message."""

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_default_message(self, cls: type[GuidewireError]) -> None:
        err = cls()
        assert isinstance(err.message, str)
        assert len(err.message) > 0

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_custom_message(self, cls: type[GuidewireError]) -> None:
        err = cls("custom detail")
        assert err.message == "custom detail"

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_str_representation(self, cls: type[GuidewireError]) -> None:
        err = cls("something went wrong")
        assert str(err) == "something went wrong"

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_catchability(self, cls: type[GuidewireError]) -> None:
        with pytest.raises(GuidewireError):
            raise cls("boom")

    @pytest.mark.parametrize(
        "cls",
        [
            BackendUnavailableError,
            ElementNotFoundError,
            StaleElementReferenceError,
            ActionNotSupportedError,
            PermissionRequiredError,
            AmbiguousSelectorError,
            WindowNotFoundError,
        ],
    )
    def test_catch_specific(self, cls: type[GuidewireError]) -> None:
        with pytest.raises(cls):
            raise cls("boom")

    def test_catch_by_base_does_not_match_unrelated(self) -> None:
        """GuidewireError should not catch standard Python exceptions."""
        with pytest.raises(ValueError):
            try:
                raise ValueError("not a guidewire error")
            except GuidewireError:
                pytest.fail("GuidewireError caught a ValueError")


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


class TestExports:
    """All error classes and the base must be importable from errors."""

    def test_all_contains_eight_entries(self) -> None:
        from guidewire import errors

        assert len(errors.__all__) == 8

    def test_all_entries_are_error_classes(self) -> None:
        from guidewire import errors

        for name in errors.__all__:
            obj = getattr(errors, name)
            assert issubclass(obj, GuidewireError), f"{name} is not a GuidewireError subclass"
