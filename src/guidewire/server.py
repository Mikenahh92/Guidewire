"""Guidewire MCP server — wires the FastMCP server with all tool stubs.

Provides :class:`GuidewireServer` which wraps :class:`~mcp.server.fastmcp.FastMCP`
with :meth:`register_tools` and :meth:`run` methods (architecture v2 §2.2).

PRD R1: agents can discover Guidewire's tools via ``tools/list`` and
invoke them through stdio transport.
"""

import asyncio

from mcp.server.fastmcp import FastMCP

from guidewire.tools import register_all

__all__ = ["GuidewireServer"]


class GuidewireServer:
    """Guidewire MCP server wrapping FastMCP with tool registration and run.

    Architecture v2 §2.2: ``GuidewireServer`` is the single entry-point for
    creating, configuring, and launching the Guidewire MCP server.
    """

    def __init__(self) -> None:
        self._mcp = FastMCP(
            name="guidewire",
            instructions=(
                "Guidewire Desktop Accessibility MCP — provides tools for "
                "inspecting and interacting with desktop application UIs via "
                "OS accessibility APIs."
            ),
        )

    @property
    def mcp(self) -> FastMCP:
        """The underlying FastMCP instance."""
        return self._mcp

    def register_tools(self) -> None:
        """Register all tool stubs on the MCP server."""
        register_all(self._mcp)

    def run(self) -> None:
        """Run the server with stdio transport (blocking)."""
        asyncio.run(self._mcp.run_stdio_async())
