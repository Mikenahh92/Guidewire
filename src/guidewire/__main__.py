"""Entry point for the Guidewire MCP server (PRD R1).

Wires stdio transport so that MCP clients can communicate with the
server over the standard input/output streams::

    python -m guidewire
"""

from guidewire.server import GuidewireServer

__all__ = ["main"]


def main() -> None:
    """Run the Guidewire MCP server with stdio transport."""
    server = GuidewireServer()
    server.register_tools()
    server.run()


if __name__ == "__main__":
    main()
