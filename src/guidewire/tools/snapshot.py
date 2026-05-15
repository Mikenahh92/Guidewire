"""desktop.snapshot tool stub."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    """Register the desktop.snapshot tool stub."""

    @mcp.tool(name="desktop.snapshot")
    def snapshot(
        window_ref: str,
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> str:
        """Capture an accessibility snapshot of a window's UI tree.

        Returns a depth-limited tree of accessibility elements suitable for
        LLM consumption (PRD §5.3).

        Args:
            window_ref: Short reference handle for the target window.
            max_depth: Maximum tree depth to traverse (default 4).
            max_nodes: Maximum number of nodes to include (default 500).

        Returns:
            A JSON tree of desktop elements with ``ref``, ``role``, ``name``,
            ``states``, ``bounds``, ``actions``, and ``children`` fields.
        """
        return (
            '{"ref":"w1","role":"window","name":"","states":[],'
            '"bounds":{"x":0,"y":0,"width":0,"height":0},'
            '"actions":[],"children":[]}'
        )
