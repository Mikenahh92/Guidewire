"""desktop.focus_window tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the desktop.focus_window tool stub."""

    @mcp.tool(name="desktop.focus_window")
    def focus_window(window_ref: str) -> str:
        """Bring a window to the foreground.

        Args:
            window_ref: Short reference handle for the target window.

        Returns:
            A confirmation message.
        """
        return f"Focused window {window_ref}"
