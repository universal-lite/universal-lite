import json
import subprocess
import xml.etree.ElementTree as ET
from gettext import gettext as _
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk

from ..base import BasePage

LAYOUT_NAMES = {
    "us": "English (US)", "gb": "English (UK)", "de": "German",
    "fr": "French", "es": "Spanish", "it": "Italian", "pt": "Portuguese",
    "ru": "Russian", "jp": "Japanese", "kr": "Korean", "cn": "Chinese",
    "ar": "Arabic", "br": "Portuguese (Brazil)", "ca": "Canadian",
    "dk": "Danish", "fi": "Finnish", "nl": "Dutch", "no": "Norwegian",
    "pl": "Polish", "se": "Swedish", "ch": "Swiss", "tr": "Turkish",
    "ua": "Ukrainian", "in": "Indian", "il": "Hebrew", "th": "Thai",
    "cz": "Czech", "hu": "Hungarian", "ro": "Romanian", "sk": "Slovak",
    "hr": "Croatian", "si": "Slovenian", "bg": "Bulgarian", "gr": "Greek",
    "ir": "Persian", "et": "Amharic", "vn": "Vietnamese",
    "ke": "Swahili (Kenya)", "tz": "Swahili (Tanzania)", "ng": "Nigerian",
}

SYSTEM_RC_XML = Path("/etc/xdg/labwc/rc.xml")
USER_KEYBINDINGS = Path.home() / ".config/universal-lite/keybindings.json"

# Human-readable names for action+command combos
SHORTCUT_NAMES = {
    ("Execute", "foot"): "Open Terminal",
    ("Execute", "Thunar"): "Open File Manager",
    ("Execute", "universal-lite-app-menu"): "App Launcher",
    ("Execute", "universal-lite-settings"): "Open Settings",
    ("Execute", "swaylock -f"): "Lock Screen",
    ("Execute", "foot -e htop"): "System Monitor",
    ("NextWindow", ""): "Switch Windows",
    ("PreviousWindow", ""): "Switch Windows (Reverse)",
    ("Close", ""): "Close Window",
    ("ToggleMaximize", ""): "Maximize / Restore",
    ("Iconify", ""): "Minimize",
    ("ToggleFullscreen", ""): "Toggle Fullscreen",
    ("SnapToEdge", "left"): "Snap Left",
    ("SnapToEdge", "right"): "Snap Right",
}

# Keys to skip in the shortcuts editor (internal bindings)
_SKIP_KEYS = {"C-F12"}

# Modifier key names that should be ignored during capture
_MODIFIER_KEYVALS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Super_L", "Super_R",
    "Meta_L", "Meta_R", "ISO_Level3_Shift", "Hyper_L", "Hyper_R",
    "Caps_Lock", "Num_Lock",
}


def _human_key_label(key_str: str) -> str:
    """Convert labwc key string like 'C-A-T' to 'Ctrl+Alt+T' for display."""
    parts = key_str.split("-")
    display = []
    for p in parts:
        if p == "C":
            display.append("Ctrl")
        elif p == "A":
            display.append("Alt")
        elif p == "S":
            display.append("Shift")
        elif p == "W":
            display.append("Super")
        elif p.startswith("XF86"):
            # Make XF86 keys readable
            name = p[4:]
            # Insert spaces before capitals
            readable = ""
            for i, ch in enumerate(name):
                if ch.isupper() and i > 0 and not name[i - 1].isupper():
                    readable += " "
                readable += ch
            display.append(readable)
        else:
            display.append(p.capitalize() if len(p) == 1 else p)
    return " + ".join(display)


def _get_action_name(action_name, command, direction):
    """Resolve a human-readable name for an action."""
    # Check SnapToEdge with direction
    if action_name == "SnapToEdge" and direction:
        key = ("SnapToEdge", direction)
        if key in SHORTCUT_NAMES:
            return SHORTCUT_NAMES[key]
        return f"Snap {direction.capitalize()}"

    # Check exact match first
    key = (action_name, command)
    if key in SHORTCUT_NAMES:
        return SHORTCUT_NAMES[key]

    # Check without command for non-Execute actions
    if action_name != "Execute":
        key = (action_name, "")
        if key in SHORTCUT_NAMES:
            return SHORTCUT_NAMES[key]
        return action_name

    # For Execute actions, match by substring
    if command:
        cmd_lower = command.lower()
        if "volume up" in cmd_lower:
            return "Volume Up"
        if "volume down" in cmd_lower:
            return "Volume Down"
        if "volume mute" in cmd_lower:
            return "Mute"
        if "brightness up" in cmd_lower:
            return "Brightness Up"
        if "brightness down" in cmd_lower:
            return "Brightness Down"
        if "grim -g" in cmd_lower:
            return "Screenshot (Region)"
        if "grim" in cmd_lower:
            return "Screenshot"

    return f"Run: {command}" if command else action_name


def _parse_system_keybindings() -> list[dict]:
    """Parse keybindings from the system rc.xml."""
    bindings = []
    try:
        tree = ET.parse(SYSTEM_RC_XML)
        root = tree.getroot()
    except (ET.ParseError, FileNotFoundError, OSError):
        return bindings

    keyboard = root.find("keyboard")
    if keyboard is None:
        return bindings

    for keybind in keyboard.findall("keybind"):
        key = keybind.get("key", "")
        if not key or key in _SKIP_KEYS:
            continue

        action_el = keybind.find("action")
        if action_el is None:
            continue

        action_name = action_el.get("name", "")
        command = action_el.get("command", "")
        menu = action_el.get("menu", "")
        direction = ""

        # Skip ShowMenu internal bindings
        if action_name == "ShowMenu":
            continue

        dir_el = action_el.find("direction")
        if dir_el is not None and dir_el.text:
            direction = dir_el.text.strip()

        display_name = _get_action_name(action_name, command, direction)

        bindings.append({
            "key": key,
            "action": action_name,
            "command": command,
            "direction": direction,
            "menu": menu,
            "display_name": display_name,
        })

    return bindings


def _load_user_keybindings() -> list[dict] | None:
    """Load user keybinding overrides. Returns None if no overrides exist."""
    if not USER_KEYBINDINGS.exists():
        return None
    try:
        data = json.loads(USER_KEYBINDINGS.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return None
        # Reconstruct display_name for each binding
        for entry in data:
            if "display_name" not in entry:
                entry["display_name"] = _get_action_name(
                    entry.get("action", ""),
                    entry.get("command", ""),
                    entry.get("direction", ""),
                )
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_user_keybindings(bindings: list[dict]) -> None:
    """Save keybinding overrides to JSON."""
    USER_KEYBINDINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = USER_KEYBINDINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(bindings, indent=2) + "\n", encoding="utf-8")
    tmp.rename(USER_KEYBINDINGS)


class KeyboardPage(BasePage):
    def __init__(self, store, event_bus):
        super().__init__(store, event_bus)
        self._default_bindings = _parse_system_keybindings()
        user = _load_user_keybindings()
        self._bindings = user if user is not None else list(self._default_bindings)
        self._capture_controller = None
        self._capture_button = None
        self._capture_index = -1
        self._shortcut_buttons: list[Gtk.Button] = []

    @property
    def search_keywords(self):
        return [
            (_("Layout"), _("Keyboard layout")), (_("Layout"), _("Variant")),
            (_("Repeat"), _("Repeat delay")), (_("Repeat"), _("Repeat rate")),
            (_("Caps Lock"), _("Caps Lock behavior")), (_("Caps Lock"), _("Remap")),
            (_("Shortcuts"), _("Keyboard shortcuts")), (_("Shortcuts"), _("Keybinding")),
            (_("Shortcuts"), _("Hotkey")), (_("Shortcuts"), _("Key combo")),
        ]

    def build(self):
        page = self.make_page_box()

        # -- Layout --
        layout_codes = self._get_layouts()
        display_names = [LAYOUT_NAMES.get(c, c) for c in layout_codes]
        current_layout = self.store.get("keyboard_layout", "us")
        try:
            layout_idx = layout_codes.index(current_layout)
        except ValueError:
            layout_idx = 0

        layout_dropdown = Gtk.DropDown.new(Gtk.StringList.new(display_names), None)
        layout_dropdown.set_selected(layout_idx)
        layout_dropdown.set_size_request(240, -1)

        current_variant = self.store.get("keyboard_variant", "")
        variant_codes: list[str] = []

        variant_dropdown = Gtk.DropDown.new(Gtk.StringList.new([_("(Default)")]), None)
        variant_dropdown.set_size_request(240, -1)
        variant_row = self.make_setting_row(_("Variant"), "", variant_dropdown)

        def _build_variant_dropdown(layout_code):
            variants = self._get_variants(layout_code)
            variant_codes.clear()
            variant_codes.append("")
            variant_codes.extend(variants)
            variant_dropdown.set_model(Gtk.StringList.new([_("(Default)")] + variants))
            variant_row.set_visible(bool(variants))
            try:
                sel = variant_codes.index(current_variant if layout_code == current_layout else "")
            except ValueError:
                sel = 0
            variant_dropdown.set_selected(sel)

        def _on_variant_changed(dd, _pspec):
            idx = dd.get_selected()
            if idx == Gtk.INVALID_LIST_POSITION or not variant_codes:
                return
            code = variant_codes[idx] if idx < len(variant_codes) else ""
            self.store.save_and_apply("keyboard_variant", code)

        variant_dropdown.connect("notify::selected", _on_variant_changed)

        def _on_layout_changed(dd, _pspec):
            idx = dd.get_selected()
            if idx == Gtk.INVALID_LIST_POSITION or idx >= len(layout_codes):
                return
            code = layout_codes[idx]
            self.store.save_dict_and_apply({"keyboard_layout": code, "keyboard_variant": ""})
            _build_variant_dropdown(code)

        layout_dropdown.connect("notify::selected", _on_layout_changed)
        _build_variant_dropdown(current_layout)

        page.append(self.make_group(_("Layout"), [
            self.make_setting_row(_("Keyboard layout"), "", layout_dropdown),
            variant_row,
        ]))

        # -- Repeat --
        delay_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 150, 1000, 50)
        delay_scale.set_value(self.store.get("keyboard_repeat_delay", 300))
        delay_scale.set_size_request(200, -1)
        delay_scale.set_draw_value(True)
        delay_scale.set_format_value_func(lambda _s, v: f"{v:.0f} ms")
        delay_scale.connect("value-changed", lambda s: self.store.save_debounced(
            "keyboard_repeat_delay", int(s.get_value())))

        rate_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 80, 5)
        rate_scale.set_value(self.store.get("keyboard_repeat_rate", 40))
        rate_scale.set_size_request(200, -1)
        rate_scale.set_draw_value(True)
        rate_scale.set_format_value_func(lambda _s, v: f"{v:.0f}/s")
        rate_scale.connect("value-changed", lambda s: self.store.save_debounced(
            "keyboard_repeat_rate", int(s.get_value())))

        page.append(self.make_group(_("Repeat"), [
            self.make_setting_row(_("Repeat delay"), "", delay_scale),
            self.make_setting_row(_("Repeat rate"), "", rate_scale),
        ]))

        # -- Caps Lock --
        caps_options = [_("Default"), _("Ctrl"), _("Escape"), _("Disabled")]
        caps_values = ["default", "ctrl", "escape", "disabled"]
        caps_dd = Gtk.DropDown.new_from_strings(caps_options)
        current_caps = self.store.get("capslock_behavior", "default")
        try:
            caps_dd.set_selected(caps_values.index(current_caps))
        except ValueError:
            caps_dd.set_selected(0)
        caps_dd.connect("notify::selected", lambda d, _:
            self.store.save_and_apply("capslock_behavior", caps_values[d.get_selected()]))

        page.append(self.make_group(_("Caps Lock Behavior"), [
            self.make_setting_row(
                _("Caps Lock key"), _("Remap Caps Lock to another function"), caps_dd),
        ]))

        # -- Keyboard Shortcuts --
        self._shortcut_buttons.clear()
        shortcut_rows = [
            self._build_shortcut_row(i, binding)
            for i, binding in enumerate(self._bindings)
        ]

        # Reset All button
        reset_all_btn = Gtk.Button(label=_("Reset All Shortcuts"))
        reset_all_btn.set_halign(Gtk.Align.START)
        reset_all_btn.set_margin_top(8)
        reset_all_btn.connect("clicked", lambda _: self._reset_all_shortcuts())

        page.append(self.make_group(_("Keyboard Shortcuts"),
                                    shortcut_rows + [reset_all_btn]))

        return page

    def _build_shortcut_row(self, index: int, binding: dict) -> Gtk.Box:
        """Build a single shortcut row with label and key capture button."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("setting-row")
        row.set_valign(Gtk.Align.CENTER)

        # Left: description label
        label = Gtk.Label(label=binding["display_name"], xalign=0)
        label.set_hexpand(True)
        row.append(label)

        # Reset button (per-shortcut)
        default_key = self._get_default_key(index)
        if default_key and default_key != binding["key"]:
            reset_btn = Gtk.Button()
            reset_btn.set_icon_name("edit-undo-symbolic")
            reset_btn.set_tooltip_text(_("Reset to default"))
            reset_btn.set_valign(Gtk.Align.CENTER)
            reset_btn.connect("clicked", lambda _, idx=index: self._reset_shortcut(idx))
            row.append(reset_btn)

        # Right: key combo button
        key_btn = Gtk.Button(label=_human_key_label(binding["key"]))
        key_btn.set_valign(Gtk.Align.CENTER)
        key_btn.set_size_request(180, -1)
        key_btn.connect("clicked", lambda _, idx=index: self._start_capture(idx))
        row.append(key_btn)

        # Track the button for later updates
        while len(self._shortcut_buttons) <= index:
            self._shortcut_buttons.append(None)
        self._shortcut_buttons[index] = key_btn

        return row

    def _get_default_key(self, index: int) -> str | None:
        """Get the default key for a binding by matching its action signature."""
        if index >= len(self._bindings):
            return None
        binding = self._bindings[index]
        for default in self._default_bindings:
            if (default["action"] == binding["action"]
                    and default["command"] == binding["command"]
                    and default["direction"] == binding["direction"]):
                return default["key"]
        return None

    def _start_capture(self, index: int) -> None:
        """Enter key capture mode for the given shortcut index."""
        # Cancel any existing capture
        self._cancel_capture()

        if index >= len(self._shortcut_buttons) or self._shortcut_buttons[index] is None:
            return

        btn = self._shortcut_buttons[index]
        self._capture_button = btn
        self._capture_index = index
        btn.set_label(_("Press new shortcut..."))

        window = btn.get_root()
        if window is None:
            return

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_captured)
        window.add_controller(controller)
        self._capture_controller = controller

    def _cancel_capture(self) -> None:
        """Cancel the current key capture, restoring the button label."""
        if self._capture_controller is not None:
            window = self._capture_controller.get_widget()
            if window is not None:
                window.remove_controller(self._capture_controller)
            self._capture_controller = None

        if self._capture_button is not None and self._capture_index >= 0:
            current_key = self._bindings[self._capture_index]["key"]
            self._capture_button.set_label(_human_key_label(current_key))

        self._capture_button = None
        self._capture_index = -1

    def _on_key_captured(self, _controller, keyval, _keycode, state):
        """Handle a key press during capture mode."""
        key_name = Gdk.keyval_name(keyval)

        # Ignore lone modifier presses
        if key_name in _MODIFIER_KEYVALS:
            return True

        # Escape cancels capture
        if key_name == "Escape" and not (state & (
                Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK
                | Gdk.ModifierType.SUPER_MASK)):
            self._cancel_capture()
            return True

        new_key = self._build_key_string(keyval, state)
        if not new_key:
            return True

        index = self._capture_index
        self._cancel_capture()

        # Check for conflicts
        conflict_idx = self._find_conflict(new_key, index)
        if conflict_idx is not None:
            conflict_name = self._bindings[conflict_idx]["display_name"]
            self._show_conflict_dialog(new_key, index, conflict_idx, conflict_name)
            return True

        self._apply_new_key(index, new_key)
        return True

    def _build_key_string(self, keyval, state):
        """Build a labwc key string from GDK keyval and modifier state."""
        parts = []
        if state & Gdk.ModifierType.CONTROL_MASK:
            parts.append("C")
        if state & Gdk.ModifierType.ALT_MASK:
            parts.append("A")
        if state & Gdk.ModifierType.SHIFT_MASK:
            parts.append("S")
        if state & Gdk.ModifierType.SUPER_MASK:
            parts.append("W")
        key_name = Gdk.keyval_name(keyval)
        if key_name:
            parts.append(key_name)
        return "-".join(parts) if parts else ""

    def _find_conflict(self, new_key: str, exclude_index: int) -> int | None:
        """Find index of binding that already uses this key, or None."""
        for i, binding in enumerate(self._bindings):
            if i == exclude_index:
                continue
            if binding["key"] == new_key:
                return i
        return None

    def _show_conflict_dialog(self, new_key: str, target_idx: int,
                              conflict_idx: int, conflict_name: str) -> None:
        """Show a dialog asking the user to confirm reassigning a conflicting key."""
        btn = self._shortcut_buttons[target_idx] if target_idx < len(self._shortcut_buttons) else None
        window = btn.get_root() if btn else None

        dialog = Gtk.AlertDialog()
        dialog.set_message(_("Shortcut Conflict"))
        dialog.set_detail(
            _('"{key}" is already assigned to "{conflict}".\n\nReassign it to "{target}"?').format(
                key=_human_key_label(new_key),
                conflict=conflict_name,
                target=self._bindings[target_idx]['display_name'],
            )
        )
        dialog.set_buttons([_("Cancel"), _("Reassign")])
        dialog.set_default_button(1)
        dialog.set_cancel_button(0)

        def _on_response(dialog_obj, result):
            try:
                choice = dialog_obj.choose_finish(result)
            except GLib.Error:
                return
            if choice == 1:
                # Remove the conflicting binding's key (set to "None")
                old_default = self._get_default_key(conflict_idx)
                self._bindings[conflict_idx]["key"] = old_default or ""
                if conflict_idx < len(self._shortcut_buttons) and self._shortcut_buttons[conflict_idx]:
                    self._shortcut_buttons[conflict_idx].set_label(
                        _human_key_label(self._bindings[conflict_idx]["key"]))
                self._apply_new_key(target_idx, new_key)

        dialog.choose(window, None, _on_response)

    def _apply_new_key(self, index: int, new_key: str) -> None:
        """Set a new key for the binding at index, save, and reconfigure."""
        if index >= len(self._bindings):
            return
        self._bindings[index]["key"] = new_key
        if index < len(self._shortcut_buttons) and self._shortcut_buttons[index]:
            self._shortcut_buttons[index].set_label(_human_key_label(new_key))
        self._save_and_reconfigure()

    def _reset_shortcut(self, index: int) -> None:
        """Reset a single shortcut to its system default."""
        default_key = self._get_default_key(index)
        if default_key is None:
            return
        # Check if the default key conflicts with another modified binding
        conflict_idx = self._find_conflict(default_key, index)
        if conflict_idx is not None:
            # Reset the conflicting one too
            other_default = self._get_default_key(conflict_idx)
            if other_default:
                self._bindings[conflict_idx]["key"] = other_default
                if conflict_idx < len(self._shortcut_buttons) and self._shortcut_buttons[conflict_idx]:
                    self._shortcut_buttons[conflict_idx].set_label(
                        _human_key_label(other_default))

        self._bindings[index]["key"] = default_key
        if index < len(self._shortcut_buttons) and self._shortcut_buttons[index]:
            self._shortcut_buttons[index].set_label(_human_key_label(default_key))
        self._save_and_reconfigure()

    def _reset_all_shortcuts(self) -> None:
        """Reset all shortcuts to system defaults."""
        self._bindings = list(self._default_bindings)
        # Update all button labels
        for i, binding in enumerate(self._bindings):
            if i < len(self._shortcut_buttons) and self._shortcut_buttons[i]:
                self._shortcut_buttons[i].set_label(_human_key_label(binding["key"]))
        # Delete user overrides and reconfigure
        try:
            if USER_KEYBINDINGS.exists():
                USER_KEYBINDINGS.unlink()
        except OSError:
            pass
        # Out-of-band: the keybindings JSON lives outside settings.json,
        # so there's no key to save. Just kick apply-settings so it
        # re-reads the JSON and regenerates rc.xml.
        self.store.apply()

    def _save_and_reconfigure(self) -> None:
        """Save keybindings to JSON and trigger apply-settings + labwc reconfigure."""
        # Save the full bindings list (for apply-settings to read)
        save_data = []
        for b in self._bindings:
            save_data.append({
                "key": b["key"],
                "action": b["action"],
                "command": b.get("command", ""),
                "direction": b.get("direction", ""),
                "menu": b.get("menu", ""),
            })
        _save_user_keybindings(save_data)

        # Out-of-band: see note in _reset_all_shortcuts.
        self.store.apply()

    @staticmethod
    def _get_layouts():
        try:
            r = subprocess.run(
                ["localectl", "list-x11-keymap-layouts"],
                capture_output=True, text=True, timeout=10,
            )
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ["us"]

    @staticmethod
    def _get_variants(layout):
        try:
            r = subprocess.run(
                ["localectl", "list-x11-keymap-variants", layout],
                capture_output=True, text=True, timeout=10,
            )
            return [v.strip() for v in r.stdout.splitlines() if v.strip()]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
