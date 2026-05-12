"""Entry point for the Guidewire MCP server."""

import sys


def main() -> None:
    """Run the Guidewire MCP server."""
    print(f"guidewire v{__import__('guidewire').__version__}", file=sys.stderr)
    print("MCP server not yet implemented — scaffold only.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
