from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from ..base import BasePage

CURSOR_SIZES = [
    ("24", _("Default (24px)")),
    ("32", _("Large (32px)")),
    ("48", _("Larger (48px)")),
]


class AccessibilityPage(BasePage):
    @property
    def search_keywords(self):
        return [
            (_("Accessibility"), _("Large text")),
            (_("Accessibility"), _("Cursor size")),
            (_("Accessibility"), _("High contrast")),
            (_("Accessibility"), _("Reduce motion")),
        ]

    def build(self):
        page = self.make_page_box()

        # Large text toggle
        large_text = Gtk.Switch()
        large_text.set_active(self.store.get("font_size", 11) >= 15)

        def _on_large_text(_, state):
            if state:
                prev = self.store.get("font_size", 11)
                if prev < 15:
                    self.store.save_and_apply("_large_text_prev_font", prev)
                self.store.save_and_apply("font_size", 15)
            else:
                prev = self.store.get("_large_text_prev_font", 11)
                self.store.save_and_apply("font_size", prev)
            return False

        large_text.connect("state-set", _on_large_text)

        # Cursor size
        labels = [label for _, label in CURSOR_SIZES]
        values = [val for val, _ in CURSOR_SIZES]
        cursor_dd = Gtk.DropDown.new_from_strings(labels)
        current = str(self.store.get("cursor_size", 24))
        try:
            cursor_dd.set_selected(values.index(current))
        except ValueError:
            cursor_dd.set_selected(0)
        cursor_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("cursor_size", int(values[d.get_selected()])))

        # High contrast
        contrast = Gtk.Switch()
        contrast.set_active(self.store.get("high_contrast", False))

        def _on_contrast(_, state):
            self.store.save_and_apply("high_contrast", state)
            return False

        contrast.connect("state-set", _on_contrast)

        # Reduce motion
        motion = Gtk.Switch()
        motion.set_active(self.store.get("reduce_motion", False))

        def _on_motion(_, state):
            self.store.save_and_apply("reduce_motion", state)
            return False

        motion.connect("state-set", _on_motion)

        page.append(self.make_group(_("Accessibility"), [
            self.make_setting_row(
                _("Large text"), _("Increases font size for better readability"), large_text),
            self.make_setting_row(_("Cursor size"), "", cursor_dd),
            self.make_setting_row(
                _("High contrast"), _("Forces dark theme with stronger borders"), contrast),
            self.make_setting_row(
                _("Reduce motion"), _("Disables animations throughout the interface"), motion),
        ]))

        return page
