from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from ..base import BasePage
from ..wallpapers import Wallpaper, add_custom, list_wallpapers, remove_custom

ACCENT_COLORS = [
    ("blue", "#3584e4"), ("teal", "#2190a4"), ("green", "#3a944a"),
    ("yellow", "#c88800"), ("orange", "#ed5b00"), ("red", "#e62d42"),
    ("pink", "#d56199"), ("purple", "#9141ac"), ("slate", "#6f8396"),
]


class AppearancePage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._wallpaper_flow: Gtk.FlowBox | None = None
        self._wallpaper_buttons: list[tuple[Gtk.ToggleButton, str]] = []

    @property
    def search_keywords(self):
        return [
            (_("Theme"), _("Light")), (_("Theme"), _("Dark")),
            (_("Accent color"), _("Color")),
            (_("Font size"), _("Font")),
            (_("Wallpaper"), _("Background")),
        ]

    def build(self):
        page = self.make_page_box()

        # -- Theme group --
        theme_children = [self.make_toggle_cards(
            [("light", _("Light")), ("dark", _("Dark"))],
            self.store.get("theme", "light"),
            lambda v: self.store.save_and_apply("theme", v),
        )]
        if self.store.get("high_contrast", False):
            note = Gtk.Label(label=_("Theme is set to Dark by High Contrast mode"), xalign=0)
            note.add_css_class("setting-subtitle")
            theme_children.append(note)
        page.append(self.make_group(_("Theme"), theme_children))

        # -- Accent color group --
        accent_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        accent_buttons: list[Gtk.ToggleButton] = []
        current_accent = self.store.get("accent", "blue")

        def _on_accent_toggled(btn, name):
            if not btn.get_active():
                return
            for other in accent_buttons:
                if other is not btn and other.get_active():
                    other.set_active(False)
            self.store.save_and_apply("accent", name)

        for name, _hex in ACCENT_COLORS:
            btn = Gtk.ToggleButton()
            btn.add_css_class("accent-circle")
            btn.add_css_class(f"accent-{name}")
            btn.set_active(name == current_accent)
            btn.connect("toggled", _on_accent_toggled, name)
            accent_buttons.append(btn)
            accent_box.append(btn)
        page.append(self.make_group(_("Accent color"), [accent_box]))

        # -- Font size group --
        font_sizes = [("10", _("Small")), ("11", _("Default")), ("13", _("Large")), ("15", _("Larger"))]
        font_labels = [label for _, label in font_sizes]
        font_values = [val for val, _ in font_sizes]
        font_dd = Gtk.DropDown.new_from_strings(font_labels)
        current_font = str(self.store.get("font_size", 11))
        try:
            font_dd.set_selected(font_values.index(current_font))
        except ValueError:
            font_dd.set_selected(1)
        font_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("font_size", int(font_values[d.get_selected()])))
        page.append(self.make_group(_("Font size"), [
            self.make_setting_row(_("Font size"), _("Affects all text throughout the interface"), font_dd),
        ]))

        # -- Wallpaper group --
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_column_spacing(8)
        flow.set_row_spacing(8)
        self._wallpaper_flow = flow
        self._populate_wallpapers(page)
        page.append(self.make_group(_("Wallpaper"), [flow]))

        return page

    # ── Wallpaper grid ────────────────────────────────────────────────────

    def _populate_wallpapers(self, page: Gtk.Widget) -> None:
        flow = self._wallpaper_flow
        if flow is None:
            return

        while (child := flow.get_first_child()) is not None:
            flow.remove(child)
        self._wallpaper_buttons = []

        theme = self.store.get("theme", "light")
        current = self.store.get("wallpaper", "")

        wallpapers = list_wallpapers()
        # Map a stored absolute path (legacy settings) onto the matching manifest ID
        # so its tile shows as selected after migration.
        if current.startswith("/"):
            for wp in wallpapers:
                if current in (wp.light_path, wp.dark_path):
                    current = wp.id
                    break

        for wp in wallpapers:
            flow.append(self._make_wallpaper_tile(wp, current, theme, page))

        custom_btn = Gtk.Button(label=_("Custom..."))
        custom_btn.add_css_class("toggle-card")
        custom_btn.connect("clicked", self._on_custom_clicked, page)
        flow.append(custom_btn)

    def _make_wallpaper_tile(
        self, wp: Wallpaper, current_id: str, theme: str, page: Gtk.Widget,
    ) -> Gtk.Widget:
        pic = Gtk.Picture.new_for_filename(wp.path_for_theme(theme))
        pic.set_content_fit(Gtk.ContentFit.COVER)
        pic.set_size_request(120, 80)

        btn = Gtk.ToggleButton()
        btn.add_css_class("toggle-card")
        btn.set_child(pic)
        btn.set_active(wp.id == current_id)
        btn.set_tooltip_text(wp.name)
        btn.connect("toggled", self._on_wallpaper_toggled, wp.id)
        self._wallpaper_buttons.append((btn, wp.id))

        if not wp.is_custom:
            return btn

        # Custom tiles get a corner remove button.
        overlay = Gtk.Overlay()
        overlay.set_child(btn)
        remove = Gtk.Button.new_from_icon_name("window-close-symbolic")
        remove.add_css_class("wallpaper-remove")
        remove.add_css_class("circular")
        remove.set_halign(Gtk.Align.END)
        remove.set_valign(Gtk.Align.START)
        remove.set_margin_top(4)
        remove.set_margin_end(4)
        remove.set_tooltip_text(_("Remove"))
        remove.connect("clicked", self._on_remove_custom, wp.id, page)
        overlay.add_overlay(remove)
        return overlay

    def _on_wallpaper_toggled(self, btn: Gtk.ToggleButton, wp_id: str) -> None:
        if not btn.get_active():
            return
        for other_btn, _id in self._wallpaper_buttons:
            if other_btn is not btn and other_btn.get_active():
                other_btn.set_active(False)
        self.store.save_and_apply("wallpaper", wp_id)

    def _on_custom_clicked(self, _btn: Gtk.Button, page: Gtk.Widget) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Choose Wallpaper"))
        image_filter = Gtk.FileFilter()
        image_filter.set_name(_("Images"))
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.svg"):
            image_filter.add_pattern(ext)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(image_filter)
        dialog.set_filters(filters)

        def _on_open_finish(d, result):
            try:
                file = d.open_finish(result)
            except Exception:
                return
            if file is None:
                return
            source = file.get_path()
            if not source:
                return
            wp = add_custom(source)
            if wp is None:
                self.store.show_toast(_("Could not add wallpaper"), True)
                return
            self.store.save_and_apply("wallpaper", wp.id)
            self._populate_wallpapers(page)

        dialog.open(self._get_window(page), None, _on_open_finish)

    def _on_remove_custom(self, _btn: Gtk.Button, wp_id: str, page: Gtk.Widget) -> None:
        if not remove_custom(wp_id):
            return
        # If the removed wallpaper was selected, fall back to the default.
        if self.store.get("wallpaper", "") == wp_id:
            defaults = self.store.get_defaults()
            self.store.save_and_apply("wallpaper", defaults.get("wallpaper", ""))
        self._populate_wallpapers(page)

    @staticmethod
    def _get_window(widget):
        root = widget.get_root()
        return root if isinstance(root, Gtk.Window) else None
