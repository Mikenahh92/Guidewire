"""Harness assertion helper unit tests (GW-037).

Tests the assertion helpers (assert_tool_called, assert_tool_not_called,
assert_call_order) without booting any server subprocess.
"""

from typing import Any

import pytest

from tests.harness.agent import AgentResult, ToolCallRecord
from tests.harness.assertions import assert_call_order, assert_tool_called, assert_tool_not_called


class TestAssertions:
    """Tests for assert_tool_called and assert_tool_not_called."""

    def _make_result(self, tool_calls: list[tuple[str, dict]]) -> Any:
        """Create an AgentResult with the given tool calls."""
        return AgentResult(
            text="test response",
            tool_calls=[ToolCallRecord(name=name, input=input_) for name, input_ in tool_calls],
            stop_reason="end_turn",
        )

    def test_assert_tool_called_single(self) -> None:
        """assert_tool_called should pass when tool was called."""
        result = self._make_result([("desktop.list_windows", {})])
        matches = assert_tool_called(result, "desktop.list_windows")
        assert len(matches) == 1

    def test_assert_tool_called_missing(self) -> None:
        """assert_tool_called should fail when tool was not called."""
        result = self._make_result([("desktop.snapshot", {"window_ref": "w1"})])
        with pytest.raises(AssertionError, match="was not"):
            assert_tool_called(result, "desktop.list_windows")

    def test_assert_tool_called_exact_count(self) -> None:
        """assert_tool_called with count should match exact invocations."""
        result = self._make_result(
            [
                ("desktop.list_windows", {}),
                ("desktop.snapshot", {"window_ref": "w1"}),
                ("desktop.list_windows", {}),
            ]
        )
        assert_tool_called(result, "desktop.list_windows", count=2)

    def test_assert_tool_called_wrong_count(self) -> None:
        """assert_tool_called should fail when count doesn't match."""
        result = self._make_result([("desktop.list_windows", {})])
        with pytest.raises(AssertionError, match="1 time"):
            assert_tool_called(result, "desktop.list_windows", count=2)

    def test_assert_tool_called_input_contains(self) -> None:
        """assert_tool_called with input_contains should check values."""
        result = self._make_result(
            [
                ("desktop.snapshot", {"window_ref": "w1", "max_depth": 2}),
            ]
        )
        matches = assert_tool_called(
            result,
            "desktop.snapshot",
            input_contains={"window_ref": "w1"},
        )
        assert len(matches) == 1

    def test_assert_tool_called_input_mismatch(self) -> None:
        """assert_tool_called should fail when input value doesn't match."""
        result = self._make_result(
            [
                ("desktop.snapshot", {"window_ref": "w1"}),
            ]
        )
        with pytest.raises(AssertionError, match="expected"):
            assert_tool_called(
                result,
                "desktop.snapshot",
                input_contains={"window_ref": "w99"},
            )

    def test_assert_tool_not_called_passes(self) -> None:
        """assert_tool_not_called should pass when tool was not called."""
        result = self._make_result([("desktop.list_windows", {})])
        assert_tool_not_called(result, "desktop.click")

    def test_assert_tool_not_called_fails(self) -> None:
        """assert_tool_not_called should fail when tool was called."""
        result = self._make_result([("desktop.click", {"element_ref": "e1"})])
        with pytest.raises(AssertionError, match="NOT be called"):
            assert_tool_not_called(result, "desktop.click")

    def test_assert_tool_not_called_multiple(self) -> None:
        """assert_tool_not_called should report the correct call count."""
        result = self._make_result(
            [
                ("desktop.click", {"element_ref": "e1"}),
                ("desktop.click", {"element_ref": "e2"}),
            ]
        )
        with pytest.raises(AssertionError, match="2 time"):
            assert_tool_not_called(result, "desktop.click")


class TestAssertCallOrder:
    """Tests for assert_call_order."""

    def _make_result(self, tool_calls: list[tuple[str, dict]]) -> AgentResult:
        """Create an AgentResult with the given tool calls."""
        return AgentResult(
            text="test response",
            tool_calls=[ToolCallRecord(name=name, input=input_) for name, input_ in tool_calls],
            stop_reason="end_turn",
        )

    def test_correct_order(self) -> None:
        """assert_call_order should pass for correct sequential order."""
        result = self._make_result(
            [
                ("desktop.list_windows", {}),
                ("desktop.snapshot", {"window_ref": "w1"}),
                ("desktop.click", {"element_ref": "e1"}),
            ]
        )
        assert_call_order(result, ["desktop.list_windows", "desktop.snapshot", "desktop.click"])

    def test_order_with_intervening_tools(self) -> None:
        """Intervening tools not in expected_order should be ignored."""
        result = self._make_result(
            [
                ("desktop.list_windows", {}),
                ("desktop.find", {"role": "button"}),
                ("desktop.snapshot", {"window_ref": "w1"}),
                ("desktop.click", {"element_ref": "e1"}),
            ]
        )
        assert_call_order(result, ["desktop.list_windows", "desktop.snapshot", "desktop.click"])

    def test_wrong_order_fails(self) -> None:
        """assert_call_order should fail when tools are in wrong order."""
        result = self._make_result(
            [
                ("desktop.list_windows", {}),
                ("desktop.click", {"element_ref": "e1"}),
                ("desktop.snapshot", {"window_ref": "w1"}),
            ]
        )
        # Expected order is snapshot before list_windows — but snapshot
        # comes after, so the positions check should catch it.
        with pytest.raises(AssertionError, match="not called in expected order"):
            assert_call_order(result, ["desktop.snapshot", "desktop.list_windows"])

    def test_missing_tool_fails(self) -> None:
        """assert_call_order should fail when a listed tool was not called."""
        result = self._make_result([("desktop.list_windows", {})])
        with pytest.raises(AssertionError, match="was not"):
            assert_call_order(result, ["desktop.list_windows", "desktop.snapshot"])

    def test_single_tool(self) -> None:
        """assert_call_order should pass with a single expected tool."""
        result = self._make_result([("desktop.snapshot", {"window_ref": "w1"})])
        assert_call_order(result, ["desktop.snapshot"])

    def test_empty_expected_order(self) -> None:
        """assert_call_order should pass with empty expected list."""
        result = self._make_result([("desktop.list_windows", {})])
        assert_call_order(result, [])
