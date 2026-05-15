"""Tool stubs for the Guidewire MCP server.

Each sub-module provides a ``register(mcp)`` function that registers one
tool stub on a :class:`~mcp.server.fastmcp.FastMCP` instance.  Stubs return
static placeholder responses because no platform backend is wired yet.

Tool set (architecture v2 §3.1):

    desktop.list_windows   — list visible windows
    desktop.focus_window   — bring a window to the foreground
    desktop.snapshot       — capture accessibility tree
    desktop.find           — find elements by role/name
    desktop.click          — click an element
    desktop.type_text      — type text into an element
    desktop.press_key      — press a keyboard key
    desktop.get_text       — get element text content
"""

import importlib

from mcp.server.fastmcp import FastMCP

__all__ = ["register_all"]

# Each tool lives in its own module; add new tools here.
_TOOL_MODULES = [
    ".list_windows",
    ".focus_window",
    ".snapshot",
    ".find",
    ".click",
    ".type_text",
    ".press_key",
    ".get_text",
]


def register_all(mcp: FastMCP) -> None:
    """Register every tool stub on *mcp*."""
    for module_name in _TOOL_MODULES:
        mod = importlib.import_module(module_name, package="guidewire.tools")
        mod.register(mcp)
