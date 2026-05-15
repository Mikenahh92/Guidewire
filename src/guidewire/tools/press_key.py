"""desktop.press_key tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, **kwargs: object) -> None:
    """Register the desktop.press_key tool stub."""

    @mcp.tool(name="desktop.press_key")
    def press_key(key: str) -> str:
        """Press a keyboard key or key combination.

        Args:
            key: The key to press (e.g. ``"Enter"``, ``"Tab"``, ``"Ctrl+C"``).

        Returns:
            A confirmation message.
        """
        return f'Pressed "{key}"'
