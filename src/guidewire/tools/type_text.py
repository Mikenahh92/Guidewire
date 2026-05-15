"""desktop.type_text tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP, **kwargs: object) -> None:
    """Register the desktop.type_text tool stub."""

    @mcp.tool(name="desktop.type_text")
    def type_text(element_ref: str, text: str) -> str:
        """Type text into a desktop element.

        Args:
            element_ref: Short reference handle for the target element.
            text: The text to type.

        Returns:
            A confirmation message.
        """
        return f'Typed "{text}" into {element_ref}'
