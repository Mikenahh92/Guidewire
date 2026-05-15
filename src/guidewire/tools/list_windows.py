"""desktop.list_windows tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the desktop.list_windows tool stub."""

    @mcp.tool(name="desktop.list_windows")
    def list_windows() -> str:
        """List all visible top-level desktop windows.

        Returns:
            A JSON array of window descriptors with ``title``, ``app_name``,
            ``focused``, and ``bounds`` fields.
        """
        return "[]"
