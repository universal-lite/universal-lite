from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from ..base import BasePage

BACKGROUNDS_ROOT = Path("/usr/share/backgrounds")
WALLPAPER_EXTS = frozenset({".svg", ".jpg", ".jpeg", ".png", ".webp"})
ACCENT_COLORS = [
    ("blue", "#3584e4"), ("teal", "#2190a4"), ("green", "#3a944a"),
    ("yellow", "#c88800"), ("orange", "#ed5b00"), ("red", "#e62d42"),
    ("pink", "#d56199"), ("purple", "#9141ac"), ("slate", "#6f8396"),
]


class AppearancePage(BasePage):
    @property
    def search_keywords(self):
        return [
            ("Theme", "Light"), ("Theme", "Dark"),
            ("Accent color", "Color"),
            ("Font size", "Font"),
            ("Wallpaper", "Background"),
        ]

    def build(self):
        page = self.make_page_box()

        # -- Theme group --
        page.append(self.make_group_label("Theme"))
        page.append(self.make_toggle_cards(
            [("light", "Light"), ("dark", "Dark")],
            self.store.get("theme", "light"),
            lambda v: self.store.save_and_apply("theme", v),
        ))

        # -- Accent color group --
        page.append(self.make_group_label("Accent color"))
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
        page.append(accent_box)

        # -- Font size group --
        page.append(self.make_group_label("Font size"))
        font_sizes = [("10", "Small"), ("11", "Default"), ("13", "Large"), ("15", "Larger")]
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
        page.append(self.make_setting_row("Font size", "Affects all text throughout the interface", font_dd))

        # -- Wallpaper group --
        page.append(self.make_group_label("Wallpaper"))
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_column_spacing(8)
        flow.set_row_spacing(8)
        wallpaper_buttons: list[tuple[Gtk.ToggleButton, str]] = []
        current_wallpaper = self.store.get("wallpaper", "")

        def _on_wallpaper_toggled(btn, path):
            if not btn.get_active():
                return
            for other_btn, _ in wallpaper_buttons:
                if other_btn is not btn and other_btn.get_active():
                    other_btn.set_active(False)
            self.store.save_and_apply("wallpaper", path)

        wallpaper_paths: list[Path] = []
        if BACKGROUNDS_ROOT.is_dir():
            for p in sorted(BACKGROUNDS_ROOT.rglob("*")):
                if p.is_file() and p.suffix.lower() in WALLPAPER_EXTS:
                    wallpaper_paths.append(p)

        for wp_path in wallpaper_paths:
            pic = Gtk.Picture.new_for_filename(str(wp_path))
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_size_request(120, 80)
            btn = Gtk.ToggleButton()
            btn.add_css_class("toggle-card")
            btn.set_child(pic)
            btn.set_active(str(wp_path) == current_wallpaper)
            btn.connect("toggled", _on_wallpaper_toggled, str(wp_path))
            wallpaper_buttons.append((btn, str(wp_path)))
            flow.append(btn)

        def _on_custom_clicked(_btn):
            dialog = Gtk.FileDialog()
            dialog.set_title("Choose Wallpaper")
            image_filter = Gtk.FileFilter()
            image_filter.set_name("Images")
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.svg"):
                image_filter.add_pattern(ext)
            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(image_filter)
            dialog.set_filters(filters)

            def _on_open_finish(d, result):
                try:
                    file = d.open_finish(result)
                    if file is not None:
                        path = file.get_path()
                        self.store.save_and_apply("wallpaper", path)
                        for other_btn, _ in wallpaper_buttons:
                            if other_btn.get_active():
                                other_btn.set_active(False)
                except Exception:
                    pass

            dialog.open(self._get_window(page), None, _on_open_finish)

        custom_btn = Gtk.Button(label="Custom...")
        custom_btn.connect("clicked", _on_custom_clicked)
        flow.append(custom_btn)
        page.append(flow)
        return page

    @staticmethod
    def _get_window(widget):
        root = widget.get_root()
        return root if isinstance(root, Gtk.Window) else None
