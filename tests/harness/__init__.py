"""Agent test harness — boots Guidewire MCP server, connects an AI agent,
and verifies tool usage.

Public API:
    GuidewireServerProcess — spawn and manage a Guidewire MCP server subprocess
    AgentClient            — Anthropic agent that uses MCP tools
    ToolCallRecord         — captured tool invocation for assertions
    assert_tool_called     — verify a specific tool was invoked
    assert_tool_not_called — verify a tool was not invoked
    assert_call_order      — verify tools were called in a specific order
"""

from tests.harness.agent import AgentClient, ToolCallRecord
from tests.harness.assertions import assert_call_order, assert_tool_called, assert_tool_not_called
from tests.harness.server import GuidewireServerProcess

__all__ = [
    "AgentClient",
    "GuidewireServerProcess",
    "ToolCallRecord",
    "assert_call_order",
    "assert_tool_called",
    "assert_tool_not_called",
]
