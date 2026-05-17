"""Test assertions for verifying agent tool usage.

Provides helper functions to check that specific MCP tools were called
(or not called) during an agent interaction.
"""

from typing import Any

from tests.harness.agent import AgentResult, ToolCallRecord

__all__ = ["assert_call_order", "assert_tool_called", "assert_tool_not_called"]


def assert_tool_called(
    result: AgentResult,
    tool_name: str,
    *,
    count: int | None = None,
    input_contains: dict[str, Any] | None = None,
) -> list[ToolCallRecord]:
    """Assert that a specific tool was called in the agent result.

    Args:
        result: The :class:`AgentResult` to check.
        tool_name: Expected tool name (e.g. ``"desktop.list_windows"``).
        count: If set, assert exactly this many calls were made.
        input_contains: If set, each matching call must contain these keys
            with the specified values.

    Returns:
        List of matching :class:`ToolCallRecord` entries.

    Raises:
        AssertionError: If the tool was not called, count doesn't match,
            or input doesn't contain expected values.
    """
    matches = [tc for tc in result.tool_calls if tc.name == tool_name]

    if not matches:
        available = [tc.name for tc in result.tool_calls] if result.tool_calls else []
        raise AssertionError(
            f"Expected tool {tool_name!r} to be called, but it was not. Tools called: {available}"
        )

    if count is not None and len(matches) != count:
        raise AssertionError(
            f"Expected tool {tool_name!r} to be called {count} time(s), "
            f"but it was called {len(matches)} time(s)."
        )

    if input_contains is not None:
        for match in matches:
            for key, expected_value in input_contains.items():
                actual = match.input.get(key)
                assert actual == expected_value, (
                    f"Tool {tool_name!r} call input key {key!r}: "
                    f"expected {expected_value!r}, got {actual!r}"
                )

    return matches


def assert_tool_not_called(result: AgentResult, tool_name: str) -> None:
    """Assert that a specific tool was NOT called in the agent result.

    Args:
        result: The :class:`AgentResult` to check.
        tool_name: Tool name that should not appear.

    Raises:
        AssertionError: If the tool was called.
    """
    matches = [tc for tc in result.tool_calls if tc.name == tool_name]
    if matches:
        raise AssertionError(
            f"Expected tool {tool_name!r} to NOT be called, "
            f"but it was called {len(matches)} time(s)."
        )


def assert_call_order(result: AgentResult, expected_order: list[str]) -> None:
    """Assert that tool calls occurred in the specified order.

    Only the tools listed in ``expected_order`` are checked; any
    intervening tool calls not in the list are ignored.

    Args:
        result: The :class:`AgentResult` to check.
        expected_order: List of tool names in the expected call sequence.

    Raises:
        AssertionError: If the tools were not called in the expected order
            or if a listed tool was never called.
    """
    if not expected_order:
        return

    actual_names = [tc.name for tc in result.tool_calls]

    # Find positions of each expected tool in the actual call list.
    # Use a running start position so that duplicate tool names in
    # expected_order resolve to their correct sequential occurrences.
    positions: list[int] = []
    start_pos = 0
    for expected in expected_order:
        try:
            idx = actual_names.index(expected, start_pos)
            positions.append(idx)
            start_pos = idx + 1
        except ValueError as exc:
            raise AssertionError(
                f"Expected tool {expected!r} to be called, but it was not. "
                f"Tools called: {actual_names}"
            ) from exc

    # Positions must be strictly increasing.
    if positions != sorted(positions):
        raise AssertionError(
            f"Tools not called in expected order {expected_order!r}. "
            f"Actual call sequence: {[actual_names[p] for p in positions]}"
        )
