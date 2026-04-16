from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage


class MouseTouchpadPage(BasePage):
    @property
    def search_keywords(self):
        return [
            (_("Touchpad"), _("Tap to click")), (_("Touchpad"), _("Natural scrolling")),
            (_("Touchpad"), _("Pointer speed")), (_("Touchpad"), _("Scroll speed")),
            (_("Mouse"), _("Natural scrolling")), (_("Mouse"), _("Pointer speed")),
            (_("Mouse"), _("Acceleration")),
        ]

    def build(self):
        page = self.make_page_box()

        # -- Touchpad --
        tp_tap = Gtk.Switch()
        tp_tap.set_active(self.store.get("touchpad_tap_to_click", True))
        tp_tap.connect("state-set", lambda _, s: self.store.save_and_apply("touchpad_tap_to_click", s) or False)

        tp_natural = Gtk.Switch()
        tp_natural.set_active(self.store.get("touchpad_natural_scroll", False))
        tp_natural.connect("state-set", lambda _, s: self.store.save_and_apply("touchpad_natural_scroll", s) or False)

        tp_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.1)
        tp_speed.set_value(self.store.get("touchpad_pointer_speed", 0.0))
        tp_speed.set_size_request(200, -1)
        tp_speed.set_draw_value(False)
        tp_speed.connect("value-changed", lambda s: self.store.save_debounced(
            "touchpad_pointer_speed", round(s.get_value(), 1)))

        tp_scroll = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1.0, 10.0, 1.0)
        tp_scroll.set_value(self.store.get("touchpad_scroll_speed", 5))
        tp_scroll.set_size_request(200, -1)
        tp_scroll.set_draw_value(False)
        tp_scroll.connect("value-changed", lambda s: self.store.save_debounced(
            "touchpad_scroll_speed", int(s.get_value())))

        page.append(self.make_group(_("Touchpad"), [
            self.make_setting_row(_("Tap to click"), "", tp_tap),
            self.make_setting_row(_("Natural scrolling"), _("Content moves with your fingers"), tp_natural),
            self.make_setting_row(_("Pointer speed"), "", tp_speed),
            self.make_setting_row(_("Scroll speed"), "", tp_scroll),
        ]))

        # -- Mouse --
        mouse_natural = Gtk.Switch()
        mouse_natural.set_active(self.store.get("mouse_natural_scroll", False))
        mouse_natural.connect("state-set", lambda _, s: self.store.save_and_apply("mouse_natural_scroll", s) or False)

        mouse_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.1)
        mouse_speed.set_value(self.store.get("mouse_pointer_speed", 0.0))
        mouse_speed.set_size_request(200, -1)
        mouse_speed.set_draw_value(False)
        mouse_speed.connect("value-changed", lambda s: self.store.save_debounced(
            "mouse_pointer_speed", round(s.get_value(), 1)))

        page.append(self.make_group(_("Mouse"), [
            self.make_setting_row(_("Natural scrolling"), "", mouse_natural),
            self.make_setting_row(_("Pointer speed"), "", mouse_speed),
            self.make_setting_row(_("Acceleration"), "", self.make_toggle_cards(
                [("adaptive", _("Adaptive")), ("flat", _("Flat"))],
                self.store.get("mouse_accel_profile", "adaptive"),
                lambda v: self.store.save_and_apply("mouse_accel_profile", v),
            )),
        ]))
        return page
