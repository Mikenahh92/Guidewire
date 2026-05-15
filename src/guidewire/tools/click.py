"""desktop.click tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, **kwargs: object) -> None:
    """Register the desktop.click tool stub."""

    @mcp.tool(name="desktop.click")
    def click(element_ref: str) -> str:
        """Click a desktop element.

        Args:
            element_ref: Short reference handle for the target element.

        Returns:
            A confirmation message.
        """
        return f"Clicked {element_ref}"
