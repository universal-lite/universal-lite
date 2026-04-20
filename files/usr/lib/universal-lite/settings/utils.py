"""Standalone helpers used across settings pages.

Home for utilities that don't belong as instance methods on
BasePage - they don't depend on page state, and threading them
through BasePage just so pages can call self.foo() is gratuitous.
"""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk


def enable_escape_close(dialog: Gtk.Window) -> None:
    """Close *dialog* when the user presses Escape.

    GTK4's Gtk.Window does not wire Escape -> close by default
    (only the old Gtk.Dialog did). This matches the GNOME HIG
    expectation that every dialog is dismissible via the keyboard.

    For Adw.AlertDialog and Adw.Dialog, Escape-to-close is already
    built in - use this helper only on plain Gtk.Window instances
    (e.g. custom modal flows on pages that have not yet migrated to
    AdwNavigationView push navigation).
    """
    controller = Gtk.EventControllerKey()

    def _on_key(_c: Gtk.EventControllerKey, keyval: int, _kc: int,
                _state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            dialog.close()
            return True
        return False

    controller.connect("key-pressed", _on_key)
    dialog.add_controller(controller)
