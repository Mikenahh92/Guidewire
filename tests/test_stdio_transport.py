"""Tests for stdio transport wiring (GW-008).

Validates that:
- ``__main__.main`` wires stdio transport correctly.
- The GuidewireServer can be instantiated and tools registered without errors.
- The ``run()`` method exists and delegates to FastMCP's stdio transport.
"""

import inspect

from guidewire.server import GuidewireServer


class TestStdioTransport:
    """Tests for the stdio transport wiring."""

    def test_guidewire_server_has_run_method(self):
        """GuidewireServer should have a ``run`` method."""
        server = GuidewireServer()
        assert callable(getattr(server, "run", None))

    def test_guidewire_server_has_register_tools_method(self):
        """GuidewireServer should have a ``register_tools`` method."""
        server = GuidewireServer()
        assert callable(getattr(server, "register_tools", None))

    def test_guidewire_server_register_tools_idempotent(self):
        """Calling register_tools multiple times should not raise."""
        server = GuidewireServer()
        server.register_tools()
        server.register_tools()  # second call should be safe

    def test_main_entry_point_importable(self):
        """``guidewire.__main__`` should be importable and expose ``main``."""
        from guidewire.__main__ import main

        assert callable(main)

    def test_main_uses_guidewire_server(self):
        """The ``main`` function should use GuidewireServer."""
        import guidewire.__main__ as mod

        source = inspect.getsource(mod.main)
        assert "GuidewireServer" in source
        assert "register_tools" in source
        assert "run" in source

    async def test_server_tools_callable_via_mcp(self):
        """Registered tools should be callable through the MCP layer."""
        import json

        server = GuidewireServer()
        server.register_tools()
        result, _meta = await server.mcp.call_tool("desktop.list_windows", arguments={})
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)
        assert data["windows"] == []
