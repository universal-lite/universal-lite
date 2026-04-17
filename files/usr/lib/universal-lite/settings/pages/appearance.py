import sys
from gettext import gettext as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GdkPixbuf, Gio, Gtk

from ..base import BasePage
from ..wallpapers import Wallpaper, add_custom, list_wallpapers, remove_custom

ACCENT_COLORS = [
    ("blue", "#3584e4"), ("teal", "#2190a4"), ("green", "#3a944a"),
    ("yellow", "#c88800"), ("orange", "#ed5b00"), ("red", "#e62d42"),
    ("pink", "#d56199"), ("purple", "#9141ac"), ("slate", "#6f8396"),
]

# Tile geometry — a compact, ChromeOS-ish grid.
TILE_W = 160
TILE_H = 100
# Cap decoded pixel size so 4K WebP thumbnails don't stall the UI thread
# on low-RAM hardware. Still 2× the display size for sharp rendering.
THUMB_MAX = max(TILE_W, TILE_H) * 2


def _load_thumbnail(path: str) -> Gtk.Picture | None:
    """Load an image as a scaled thumbnail.

    Uses GdkPixbuf's scale-during-decode so large wallpapers don't blow
    through memory. Returns ``None`` if the file can't be loaded so the
    caller can skip this tile instead of crashing the whole page.
    """
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, THUMB_MAX, THUMB_MAX)
    except Exception as exc:  # GLib.Error, etc.
        print(f"appearance: thumbnail load failed for {path}: {exc}", file=sys.stderr)
        return None
    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
    pic = Gtk.Picture.new_for_paintable(texture)
    pic.set_content_fit(Gtk.ContentFit.COVER)
    pic.set_size_request(TILE_W, TILE_H)
    pic.set_can_shrink(True)
    return pic


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
        # Built inside a try/except so a broken manifest or thumbnail never
        # takes down the whole Appearance page.
        try:
            flow = Gtk.FlowBox()
            flow.set_max_children_per_line(6)
            flow.set_min_children_per_line(2)
            flow.set_selection_mode(Gtk.SelectionMode.NONE)
            flow.set_homogeneous(True)
            flow.set_column_spacing(12)
            flow.set_row_spacing(12)
            flow.add_css_class("wallpaper-grid")
            self._wallpaper_flow = flow
            self._populate_wallpapers(page)
            page.append(self.make_group(_("Wallpaper"), [flow]))
        except Exception as exc:
            print(f"appearance: wallpaper grid failed: {exc!r}", file=sys.stderr)
            err = Gtk.Label(label=_("Wallpaper picker unavailable"), xalign=0)
            err.add_css_class("setting-subtitle")
            page.append(self.make_group(_("Wallpaper"), [err]))

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
            tile = self._make_wallpaper_tile(wp, current, theme, page)
            if tile is not None:
                flow.append(tile)

        flow.append(self._make_add_tile(page))

    def _make_wallpaper_tile(
        self, wp: Wallpaper, current_id: str, theme: str, page: Gtk.Widget,
    ) -> Gtk.Widget | None:
        pic = _load_thumbnail(wp.path_for_theme(theme))
        if pic is None:
            return None

        btn = Gtk.ToggleButton()
        btn.add_css_class("wallpaper-tile")
        btn.set_child(pic)
        btn.set_active(wp.id == current_id)
        btn.set_tooltip_text(wp.name)
        btn.connect("toggled", self._on_wallpaper_toggled, wp.id)
        self._wallpaper_buttons.append((btn, wp.id))

        if not wp.is_custom:
            return btn

        # Custom tiles show an always-visible × badge in the top-right corner.
        overlay = Gtk.Overlay()
        overlay.set_child(btn)
        remove = Gtk.Button.new_from_icon_name("window-close-symbolic")
        remove.add_css_class("wallpaper-remove")
        remove.set_halign(Gtk.Align.END)
        remove.set_valign(Gtk.Align.START)
        remove.set_margin_top(6)
        remove.set_margin_end(6)
        remove.set_tooltip_text(_("Remove"))
        remove.connect("clicked", self._on_remove_custom, wp.id, page)
        overlay.add_overlay(remove)
        return overlay

    def _make_add_tile(self, page: Gtk.Widget) -> Gtk.Widget:
        btn = Gtk.Button()
        btn.add_css_class("wallpaper-add")
        btn.set_tooltip_text(_("Add picture…"))
        btn.set_size_request(TILE_W, TILE_H)
        icon = Gtk.Image.new_from_icon_name("list-add-symbolic")
        icon.set_pixel_size(24)
        btn.set_child(icon)
        btn.connect("clicked", self._on_custom_clicked, page)
        return btn

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
        if self.store.get("wallpaper", "") == wp_id:
            defaults = self.store.get_defaults()
            self.store.save_and_apply("wallpaper", defaults.get("wallpaper", ""))
        self._populate_wallpapers(page)

    @staticmethod
    def _get_window(widget):
        root = widget.get_root()
        return root if isinstance(root, Gtk.Window) else None
