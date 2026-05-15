"""desktop.get_text tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the desktop.get_text tool stub."""

    @mcp.tool(name="desktop.get_text")
    def get_text(element_ref: str) -> str:
        """Get the text value of a desktop element.

        Args:
            element_ref: Short reference handle for the target element.

        Returns:
            The element's text content as a string.
        """
        return ""
