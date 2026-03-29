import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk


class ToastWidget(Gtk.Revealer):
    """Adwaita-style toast notification. Slides up from the bottom of the overlay."""

    def __init__(self) -> None:
        super().__init__()
        self.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.set_transition_duration(200)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.set_margin_bottom(16)

        self._box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._box.add_css_class("toast")

        self._label = Gtk.Label()
        self._label.set_wrap(True)
        self._label.set_max_width_chars(50)
        self._box.append(self._label)

        dismiss = Gtk.Button.new_from_icon_name("window-close-symbolic")
        dismiss.add_css_class("flat")
        dismiss.connect("clicked", lambda _: self.dismiss())
        self._box.append(dismiss)

        self.set_child(self._box)
        self._timer_id: int | None = None

    def show_toast(self, message: str, is_error: bool = False, timeout: int = 3) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
        self._label.set_text(message)
        if is_error:
            self._box.add_css_class("toast-error")
        else:
            self._box.remove_css_class("toast-error")
        self.set_reveal_child(True)
        self._timer_id = GLib.timeout_add_seconds(timeout, self._auto_dismiss)

    def dismiss(self) -> None:
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        self.set_reveal_child(False)

    def _auto_dismiss(self) -> int:
        self._timer_id = None
        self.set_reveal_child(False)
        return GLib.SOURCE_REMOVE
