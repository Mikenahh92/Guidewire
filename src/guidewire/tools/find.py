"""desktop.find tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the desktop.find tool stub."""

    @mcp.tool(name="desktop.find")
    def find(
        window_ref: str,
        role: str | None = None,
        name: str | None = None,
    ) -> str:
        """Find accessibility elements matching criteria within a window.

        Args:
            window_ref: Short reference handle for the target window.
            role: Normalized role to match (e.g. ``"button"``, ``"text_input"``).
            name: Accessible name to match (case-insensitive substring).

        Returns:
            A JSON array of matching element references.
        """
        return "[]"
