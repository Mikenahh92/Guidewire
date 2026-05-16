"""X11 EWMH _NET_ACTIVE_WINDOW helper for LinuxBackend (architecture v2 §3.2).

This module is a lazy import target for the xlib fallback path in
:meth:`~guidewire.backends.linux.LinuxBackend.focus_window`.  Keeping the
``python-xlib`` dependency isolated here follows architecture §10 tradeoffs:
the import only fires when AT-SPI activation fails and xlib is actually needed,
so users without ``python-xlib`` are unaffected.
"""

from typing import Any


def xlib_activate(accessible: Any) -> None:
    """Send ``_NET_ACTIVE_WINDOW`` via python-xlib EWMH helper.

    Args:
        accessible: A live ``pyatspi.Accessible`` representing the window.

    Raises:
        ImportError: If ``python-xlib`` is not installed.
        Exception: If the xlib activation fails (display, D-Bus, etc.).
    """
    from Xlib import X
    from Xlib.display import Display
    from Xlib.ext import net_wm

    xid = (
        accessible.getApplication()
        .queryInterface(
            "org.freedesktop.atspi.Component",
        )
        .get_position()
    )

    display = Display()
    window = display.create_resource_object("window", xid[0])
    screen = display.screen()
    root = screen.root

    client_message = net_wm.ActiveWindow(
        window=window,
        source_indication=1,
    )
    root.send_event(client_message, event_mask=X.SubstructureRedirectMask)
    display.flush()
    display.close()


__all__ = ["xlib_activate"]
