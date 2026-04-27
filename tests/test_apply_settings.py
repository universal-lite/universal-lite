"""Tests for waybar-related functions in universal-lite-apply-settings."""

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Import the apply-settings script as a module (no .py extension).
_SCRIPT = Path(__file__).resolve().parents[1] / "files/usr/libexec/universal-lite-apply-settings"
_loader = importlib.machinery.SourceFileLoader("apply_settings", str(_SCRIPT))
_spec = importlib.util.spec_from_loader("apply_settings", _loader, origin=str(_SCRIPT))
apply_settings = importlib.util.module_from_spec(_spec)
apply_settings.__file__ = str(_SCRIPT)
_spec.loader.exec_module(apply_settings)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tokens(**overrides):
    """Return a minimal tokens dict suitable for write_waybar_config."""
    base = {
        "edge": "bottom",
        "theme": "light",
        "accent": "blue",
        "is_vertical": False,
        "layout": {
            "start": ["custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["pulseaudio", "backlight", "battery", "clock", "custom/power", "tray"],
        },
        "pinned": [],
        "panel_height": 46,
        "panel_width": 64,
        "panel_icon_size": 18,
        "panel_spacing": 10,
        "panel_margin": 8,
        "panel_pad_module": 10,
        "panel_pad_launcher": 14,
        "panel_pad_clock": 14,
        "panel_pad_tray": 6,
        "panel_pad_pin": 8,
        "clock_24h": False,
        "high_contrast": False,
        # Styling tokens
        "font_ui": "Roboto",
        "font_mono": "Roboto Mono",
        "font_size_ui": 13,
        "font_size_mono": 11,
        "cursor_size": 24,
        "reduce_motion": False,
        "text_primary": "#1e1e1e",
        "text_secondary": "#5e5c64",
        "surface_base": "#fafafa",
        "surface_card": "#ffffff",
        "border_default": "#d3d3d3",
        "state_hover": "rgba(30, 30, 30, 0.08)",
        "accent_hex": "#3584e4",
        "accent_fg_hex": "#ffffff",
        "accent_rgba_15": "rgba(53, 132, 228, 0.15)",
        "color_warning": "#e5a50a",
        "color_error": "#c01c28",
        "panel_surface": "#1e1e1e",
        "panel_fg": "#ffffff",
        "panel_secondary_fg": "#9a9a9a",
        "panel_alpha": "0.90",
        "panel_border": "rgba(255, 255, 255, 0.14)",
        "panel_control_bg": "rgba(255, 255, 255, 0.10)",
        "panel_control_hover": "rgba(255, 255, 255, 0.14)",
        "panel_control_border": "rgba(255, 255, 255, 0.12)",
        "panel_status_bg": "rgba(255, 255, 255, 0.14)",
        "panel_status_border": "rgba(255, 255, 255, 0.18)",
        "panel_accent_bg": "rgba(53, 132, 228, 0.26)",
        "panel_accent_border": "rgba(53, 132, 228, 0.42)",
        "panel_transition": "background-color 120ms ease, border-color 120ms ease, color 120ms ease",
        "panel_bar_inset": 4,
        "mako_anchor": "top-right",
    }
    base.update(overrides)
    return base


def _make_settings(**overrides):
    """Return a minimal settings dict for ensure_settings tests."""
    base = {
        "edge": "bottom",
        "density": "normal",
        "theme": "light",
        "accent": "blue",
        "scale": 1.0,
        "wallpaper": "/usr/share/backgrounds/universal-lite/chrome-dawn.svg",
        "layout": {
            "start": ["custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["pulseaudio", "backlight", "battery", "clock", "custom/power", "tray"],
        },
        "pinned": [],
        "font_size": 11,
        "cursor_size": 24,
        "high_contrast": False,
        "reduce_motion": False,
        "night_light_enabled": False,
        "night_light_temp": 4500,
        "night_light_schedule": "sunset-sunrise",
        "night_light_start": "20:00",
        "night_light_end": "06:00",
        "power_profile": "balanced",
        "suspend_timeout": 0,
        "lid_close_action": "suspend",
        "clock_24h": False,
        "capslock_behavior": "default",
    }
    base.update(overrides)
    return base


def _run_ensure_settings(data, tmp_path):
    """Write data to a temp settings.json and run ensure_settings on it."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(data))
    with patch.object(apply_settings, "SETTINGS_DIR", tmp_path), \
         patch.object(apply_settings, "SETTINGS_PATH", settings_file):
        return apply_settings.ensure_settings()


def _run_ensure_settings_raw(raw_text, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(raw_text)
    defaults_file = tmp_path / "defaults.json"
    defaults_file.write_text(json.dumps(_make_settings()))
    with patch.object(apply_settings, "SETTINGS_DIR", tmp_path), \
         patch.object(apply_settings, "SETTINGS_PATH", settings_file), \
         patch.object(apply_settings, "DEFAULTS_PATH", defaults_file):
        return apply_settings.ensure_settings()


def test_invalid_settings_json_is_preserved_before_defaults_are_written(tmp_path):
    result = _run_ensure_settings_raw("{invalid json", tmp_path)

    assert result["theme"] == "light"
    assert (tmp_path / "settings.json.invalid").read_text(encoding="utf-8") == "{invalid json"
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["theme"] == "light"


def test_config_mode_writes_files_without_live_sync(monkeypatch):
    calls = []
    settings = _make_settings()
    tokens = _make_tokens()

    monkeypatch.setattr(apply_settings, "ensure_settings", lambda: settings)
    monkeypatch.setattr(apply_settings, "_build_tokens", lambda s: tokens)
    monkeypatch.setattr(
        apply_settings,
        "_write_config_files",
        lambda s, t: calls.append(("config", s, t)) or {"waybar_changed": False},
    )
    monkeypatch.setattr(
        apply_settings,
        "_sync_live_session",
        lambda s, t, c: calls.append(("live", s, t, c)),
    )

    assert apply_settings._main_locked("config") == 0
    assert calls == [("config", settings, tokens)]


def test_live_mode_writes_config_then_syncs_live(monkeypatch):
    calls = []
    settings = _make_settings()
    tokens = _make_tokens()
    changes = {"waybar_changed": True}

    monkeypatch.setattr(apply_settings, "ensure_settings", lambda: settings)
    monkeypatch.setattr(apply_settings, "_build_tokens", lambda s: tokens)
    monkeypatch.setattr(
        apply_settings,
        "_write_config_files",
        lambda s, t: calls.append(("config", s, t)) or changes,
    )
    monkeypatch.setattr(
        apply_settings,
        "_sync_live_session",
        lambda s, t, c: calls.append(("live", s, t, c)),
    )

    assert apply_settings._main_locked("live") == 0
    assert calls == [("config", settings, tokens), ("live", settings, tokens, changes)]


def test_write_gtk_settings_can_skip_gsettings_for_pre_compositor_mode(
    monkeypatch, tmp_path
):
    calls = []
    monkeypatch.setattr(apply_settings, "GTK3_DIR", tmp_path / "gtk3")
    monkeypatch.setattr(apply_settings, "GTK4_DIR", tmp_path / "gtk4")
    monkeypatch.setattr(
        apply_settings,
        "_run_best_effort",
        lambda cmd, **kwargs: calls.append(cmd) or True,
    )

    apply_settings.write_gtk_settings(_make_tokens(), sync_live=False)

    assert (tmp_path / "gtk3/settings.ini").exists()
    assert (tmp_path / "gtk4/settings.ini").exists()
    assert calls == []


def test_session_startup_uses_config_then_autostart_uses_live_mode():
    root = Path(__file__).resolve().parents[1]
    session = (root / "files/usr/libexec/universal-lite-session").read_text(
        encoding="utf-8"
    )
    autostart = (root / "files/etc/xdg/labwc/autostart").read_text(
        encoding="utf-8"
    )

    assert "universal-lite-apply-settings --mode=config" in session
    assert "universal-lite-apply-settings --mode=live" in autostart


# ---------------------------------------------------------------------------
# Theme-derived panel colors
# ---------------------------------------------------------------------------

class TestPanelThemeTokens:
    def test_light_theme_panel_controls_are_visible_neutral_tints(self):
        tokens = apply_settings._build_tokens(_make_settings(theme="light"))
        assert tokens["panel_surface"] == "#fafafa"
        assert tokens["panel_fg"] == "#1e1e1e"
        assert tokens["panel_alpha"] == "0.90"
        assert tokens["panel_border"] == "rgba(30, 30, 30, 0.1)"
        assert tokens["panel_control_bg"] == "rgba(30, 30, 30, 0.1)"
        assert tokens["panel_control_hover"] == "rgba(30, 30, 30, 0.15)"
        assert tokens["panel_status_bg"] == "rgba(30, 30, 30, 0.13)"
        assert tokens["panel_status_border"] == "rgba(30, 30, 30, 0.14)"
        assert tokens["panel_accent_bg"] == "rgba(53, 132, 228, 0.2)"

    def test_dark_theme_panel_controls_are_visible_neutral_tints(self):
        tokens = apply_settings._build_tokens(_make_settings(theme="dark"))
        assert tokens["panel_surface"] == "#222226"
        assert tokens["panel_fg"] == "#ffffff"
        assert tokens["panel_alpha"] == "0.90"
        assert tokens["panel_border"] == "rgba(255, 255, 255, 0.14)"
        assert tokens["panel_control_bg"] == "rgba(255, 255, 255, 0.1)"
        assert tokens["panel_control_hover"] == "rgba(255, 255, 255, 0.16)"
        assert tokens["panel_status_bg"] == "rgba(255, 255, 255, 0.14)"
        assert tokens["panel_status_border"] == "rgba(255, 255, 255, 0.18)"
        assert tokens["panel_accent_bg"] == "rgba(53, 132, 228, 0.26)"

    def test_twilight_panel_uses_opposite_theme_control_tints(self):
        tokens = apply_settings._build_tokens(
            _make_settings(theme="light", panel_twilight=True)
        )
        assert tokens["panel_surface"] == "#222226"
        assert tokens["panel_fg"] == "#ffffff"
        assert tokens["panel_control_bg"] == "rgba(255, 255, 255, 0.1)"
        assert tokens["panel_status_bg"] == "rgba(255, 255, 255, 0.14)"


# ---------------------------------------------------------------------------
# C1: Pin injection follows launcher across sections
# ---------------------------------------------------------------------------

class TestPinInjection:
    def test_pins_follow_launcher_in_start(self, tmp_path):
        tokens = _make_tokens(
            pinned=[{"name": "Chrome", "command": "chrome", "icon": "chrome"}],
        )
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        left = config["modules-left"]
        assert "custom/launcher" in left
        assert "image#pin-0" in left
        assert left.index("image#pin-0") == left.index("custom/launcher") + 1

    def test_pins_follow_launcher_in_center(self, tmp_path):
        tokens = _make_tokens(
            layout={
                "start": ["wlr/taskbar"],
                "center": ["custom/launcher", "clock"],
                "end": ["tray"],
            },
            pinned=[
                {"name": "App1", "command": "app1", "icon": "app1"},
                {"name": "App2", "command": "app2", "icon": "app2"},
            ],
        )
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        # Pins should be in modules-center, not modules-left
        assert "image#pin-0" not in config["modules-left"]
        center = config["modules-center"]
        assert center.index("image#pin-0") == center.index("custom/launcher") + 1
        assert center.index("image#pin-1") == center.index("custom/launcher") + 2

    def test_pins_follow_launcher_in_end(self, tmp_path):
        tokens = _make_tokens(
            layout={
                "start": ["wlr/taskbar"],
                "center": [],
                "end": ["custom/launcher", "tray"],
            },
            pinned=[{"name": "App", "command": "app", "icon": "app"}],
        )
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "image#pin-0" not in config["modules-left"]
        right = config["modules-right"]
        assert right.index("image#pin-0") == right.index("custom/launcher") + 1

    def test_pins_fallback_to_left_when_no_launcher(self, tmp_path):
        tokens = _make_tokens(
            layout={
                "start": ["wlr/taskbar"],
                "center": ["clock"],
                "end": ["tray"],
            },
            pinned=[{"name": "App", "command": "app", "icon": "app"}],
        )
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert config["modules-left"][0] == "image#pin-0"

    def test_no_pins_no_injection(self, tmp_path):
        tokens = _make_tokens(pinned=[])
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert not any("pin" in m for m in config["modules-left"])


# ---------------------------------------------------------------------------
# Vertical CSS — pill consistency
# ---------------------------------------------------------------------------

class TestVerticalCss:
    def test_vertical_has_min_width_and_min_height(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = apply_settings._waybar_css_vertical(tokens)
        assert "min-width:" in css
        assert "min-height:" in css

    def test_vertical_pill_radius_on_modules(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = apply_settings._waybar_css_vertical(tokens)
        assert "border-radius: 999px" in css

    def test_vertical_active_state_uses_edge_running_indicator(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = (
            apply_settings._waybar_css_common(tokens)
            + apply_settings._waybar_css_vertical(tokens)
        )
        active = re.search(r"#taskbar button\.active \{(?P<body>.*?)\n\}", css, re.S)
        assert active is not None
        assert "background: rgba(255, 255, 255, 0.10)" in active.group("body")
        assert "border-left: 3px solid #3584e4" in css
        assert "rgba(53, 132, 228, 0.26)" not in active.group("body")

    def test_vertical_window_has_min_width(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = apply_settings._waybar_css_vertical(tokens)
        assert "window#waybar" in css
        assert "min-width:" in css

    def test_vertical_window_padding_both_axes(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        inset = tokens["panel_bar_inset"]
        css = apply_settings._waybar_css_vertical(tokens)
        assert f"padding: {inset}px {inset // 2}px" in css

    def test_vertical_pinned_pill_radius(self):
        tokens = _make_tokens(
            edge="left",
            is_vertical=True,
            pinned=[{"name": "Chrome", "command": "chrome", "icon": "chrome"}],
        )
        css = apply_settings._waybar_css_vertical(tokens)
        assert "#image.pin-0" in css
        assert "border-radius: 999px" in css


# ---------------------------------------------------------------------------
# H4: Deterministic module recovery order
# ---------------------------------------------------------------------------

class TestModuleRecoveryOrder:
    def test_missing_modules_appended_in_canonical_order(self, tmp_path):
        data = _make_settings(layout={"start": [], "center": [], "end": []})
        result = _run_ensure_settings(data, tmp_path)
        # All modules should be in end, in canonical order
        assert result["layout"]["end"] == apply_settings.ALL_MODULES_ORDER

    def test_partial_layout_fills_missing_deterministically(self, tmp_path):
        data = _make_settings(layout={
            "start": ["custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["clock"],
        })
        result1 = _run_ensure_settings(data, tmp_path)

        # Run again — order must be identical
        data2 = _make_settings(layout={
            "start": ["custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["clock"],
        })
        result2 = _run_ensure_settings(data2, tmp_path)
        assert result1["layout"] == result2["layout"]

    def test_duplicate_modules_deduped(self, tmp_path):
        data = _make_settings(layout={
            "start": ["custom/launcher", "custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["clock", "clock"],
        })
        result = _run_ensure_settings(data, tmp_path)
        all_mods = result["layout"]["start"] + result["layout"]["center"] + result["layout"]["end"]
        assert len(all_mods) == len(set(all_mods))


# ---------------------------------------------------------------------------
# Layout validation — invalid structures
# ---------------------------------------------------------------------------

class TestLayoutValidation:
    def test_non_dict_layout_falls_back_to_default(self, tmp_path):
        data = _make_settings(layout="not a dict")
        result = _run_ensure_settings(data, tmp_path)
        assert result["layout"] == apply_settings.DEFAULT_LAYOUT

    def test_missing_section_falls_back_to_default(self, tmp_path):
        data = _make_settings(layout={"start": ["custom/launcher"], "center": ["wlr/taskbar"]})
        result = _run_ensure_settings(data, tmp_path)
        assert result["layout"] == apply_settings.DEFAULT_LAYOUT

    def test_non_list_section_falls_back_to_default(self, tmp_path):
        data = _make_settings(layout={
            "start": "custom/launcher",
            "center": ["wlr/taskbar"],
            "end": ["tray"],
        })
        result = _run_ensure_settings(data, tmp_path)
        assert result["layout"] == apply_settings.DEFAULT_LAYOUT

    def test_invalid_module_names_filtered(self, tmp_path):
        data = _make_settings(layout={
            "start": ["custom/launcher", "bogus_module"],
            "center": ["wlr/taskbar"],
            "end": ["clock"],
        })
        result = _run_ensure_settings(data, tmp_path)
        all_mods = result["layout"]["start"] + result["layout"]["center"] + result["layout"]["end"]
        assert "bogus_module" not in all_mods


class TestSettingsRecovery:
    def test_corrupt_settings_json_recovers_from_defaults(self, tmp_path):
        result = _run_ensure_settings_raw("{not json", tmp_path)
        assert result["theme"] == "light"
        assert result["edge"] == "bottom"

    def test_non_object_settings_json_recovers_from_defaults(self, tmp_path):
        result = _run_ensure_settings_raw("[]", tmp_path)
        assert result["theme"] == "light"
        assert result["edge"] == "bottom"

    def test_string_false_booleans_do_not_enable_features(self, tmp_path):
        data = _make_settings(
            high_contrast="false",
            night_light_enabled="false",
            reduce_motion="false",
            touchpad_tap_to_click="false",
        )
        result = _run_ensure_settings(data, tmp_path)
        assert result["high_contrast"] is False
        assert result["theme"] == "light"
        assert result["night_light_enabled"] is False
        assert result["reduce_motion"] is False
        assert result["touchpad_tap_to_click"] is False

    def test_bad_night_light_values_are_normalized(self, tmp_path):
        data = _make_settings(
            night_light_temp="hot",
            night_light_start="25:90",
            night_light_end="bad",
        )
        result = _run_ensure_settings(data, tmp_path)
        assert result["night_light_temp"] == 4500
        assert result["night_light_start"] == "20:00"
        assert result["night_light_end"] == "06:00"

    def test_invalid_wallpaper_falls_back_to_bundled_background(self, tmp_path):
        bundled = tmp_path / "backgrounds/universal-lite"
        bundled.mkdir(parents=True)
        light = bundled / "chrome-dawn.svg"
        dark = bundled / "chrome-sky.svg"
        light.write_text("<svg/>")
        dark.write_text("<svg/>")

        with patch.object(apply_settings, "_resolve_wallpaper", return_value=None), \
             patch.object(apply_settings, "FALLBACK_WALLPAPER_PATHS", {
                 "light": (light,),
                 "dark": (dark, light),
             }):
            result = _run_ensure_settings(
                _make_settings(theme="dark", wallpaper="missing-wallpaper"),
                tmp_path,
            )

        assert result["wallpaper"] == str(dark)
        written = json.loads((tmp_path / "settings.json").read_text())
        assert written["wallpaper"] == "universal-lite"


class TestWallpaperSwap:
    class _Proc:
        def __init__(self, pid: int, alive: bool):
            self.pid = pid
            self._alive = alive

        def poll(self):
            return None if self._alive else 1

    def test_failed_replacement_keeps_existing_swaybg(self, tmp_path):
        requested = tmp_path / "bad.svg"
        requested.write_text("<svg/>")

        with patch.object(apply_settings.shutil, "which", return_value="/usr/bin/swaybg"), \
             patch.object(apply_settings, "_pids_for_program", return_value=[101]), \
             patch.object(apply_settings, "_wallpaper_fallback_candidates", return_value=[]), \
             patch.object(apply_settings, "_start_swaybg", return_value=self._Proc(202, False)), \
             patch.object(apply_settings.time, "sleep"), \
             patch.object(apply_settings.os, "kill") as kill:
            apply_settings._swap_swaybg_wallpaper(str(requested), "dark")

        kill.assert_not_called()

    def test_fallback_must_survive_before_old_swaybg_is_retired(self, tmp_path):
        requested = tmp_path / "bad.svg"
        fallback = tmp_path / "fallback.svg"
        requested.write_text("<svg/>")
        fallback.write_text("<svg/>")

        with patch.object(apply_settings.shutil, "which", return_value="/usr/bin/swaybg"), \
             patch.object(apply_settings, "_pids_for_program", return_value=[101]), \
             patch.object(
                 apply_settings,
                 "_wallpaper_fallback_candidates",
                 return_value=[("fallback", str(fallback))],
             ), \
             patch.object(
                 apply_settings,
                 "_start_swaybg",
                 side_effect=[self._Proc(202, False), self._Proc(303, True)],
             ), \
             patch.object(apply_settings.time, "sleep"), \
             patch.object(apply_settings.os, "kill") as kill:
            apply_settings._swap_swaybg_wallpaper(str(requested), "dark")

        kill.assert_called_once_with(101, apply_settings.signal.SIGTERM)


class TestApplyLock:
    def test_apply_lock_uses_user_runtime_dir(self, tmp_path):
        with patch.dict(apply_settings.os.environ, {"XDG_RUNTIME_DIR": str(tmp_path)}):
            handle = apply_settings._open_apply_lock()
            try:
                assert handle is not None
                assert (tmp_path / "universal-lite-apply-settings.lock").exists()
            finally:
                apply_settings._close_apply_lock(handle)


class TestKeybindingMerge:
    def test_rebinding_default_key_removes_old_default_binding(self, tmp_path):
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        (settings_dir / "keybindings.json").write_text(json.dumps([
            {
                "key": "C-A-Y",
                "action": "Execute",
                "command": "foot",
            }
        ]))

        defaults = {
            "C-A-T": '<action name="Execute" command="foot"/>',
            "W-l": '<action name="Execute" command="swaylock -f"/>',
        }

        with patch.object(apply_settings, "SETTINGS_DIR", settings_dir):
            xml = apply_settings._build_merged_keybinds_xml(defaults)

        assert 'key="C-A-Y"' in xml
        assert 'key="C-A-T"' not in xml
        assert 'key="W-l"' in xml

    def test_empty_keybinding_action_removes_default(self, tmp_path):
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        (settings_dir / "keybindings.json").write_text(json.dumps([
            {"key": "C-A-T", "action": ""}
        ]))

        defaults = {"C-A-T": '<action name="Execute" command="foot"/>'}

        with patch.object(apply_settings, "SETTINGS_DIR", settings_dir):
            xml = apply_settings._build_merged_keybinds_xml(defaults)

        assert 'key="C-A-T"' not in xml


# ---------------------------------------------------------------------------
# M3: Pinned name fallback
# ---------------------------------------------------------------------------

class TestPinnedValidation:
    def test_empty_command_skipped(self, tmp_path):
        data = _make_settings(pinned=[{"name": "Bad", "command": ""}])
        result = _run_ensure_settings(data, tmp_path)
        assert result["pinned"] == []

    def test_missing_name_uses_binary_basename(self, tmp_path):
        data = _make_settings(pinned=[{"command": "/usr/bin/firefox %U"}])
        result = _run_ensure_settings(data, tmp_path)
        assert result["pinned"][0]["name"] == "firefox"

    def test_missing_name_uses_command_basename_no_flags(self, tmp_path):
        data = _make_settings(pinned=[{"command": "flatpak run com.example.App"}])
        result = _run_ensure_settings(data, tmp_path)
        assert result["pinned"][0]["name"] == "flatpak"

    def test_missing_icon_gets_default(self, tmp_path):
        data = _make_settings(pinned=[{"command": "app"}])
        result = _run_ensure_settings(data, tmp_path)
        assert result["pinned"][0]["icon"] == "application-x-executable"

    def test_non_dict_entry_skipped(self, tmp_path):
        data = _make_settings(pinned=["not-a-dict", {"command": "app"}])
        result = _run_ensure_settings(data, tmp_path)
        assert len(result["pinned"]) == 1


# ---------------------------------------------------------------------------
# L3: Config-change detection
# ---------------------------------------------------------------------------

class TestConfigChangeDetection:
    def test_returns_true_on_first_write(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            assert apply_settings.write_waybar_config(tokens) is True

    def test_returns_false_on_identical_write(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
            assert apply_settings.write_waybar_config(tokens) is False

    def test_returns_true_when_config_changes(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
            tokens["clock_24h"] = True
            assert apply_settings.write_waybar_config(tokens) is True

    def test_returns_true_when_css_changes(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
            tokens["panel_height"] = 36
            assert apply_settings.write_waybar_config(tokens) is True


# ---------------------------------------------------------------------------
# ChromeOS design language — common CSS
# ---------------------------------------------------------------------------

class TestCommonCssDesign:
    def test_common_has_launcher_pill(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "border-radius: 999px" in css

    def test_common_has_active_taskbar_state(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "#taskbar button.active" in css
        active = re.search(r"#taskbar button\.active \{(?P<body>.*?)\n\}", css, re.S)
        assert active is not None
        assert "background: rgba(255, 255, 255, 0.10)" in active.group("body")
        assert "rgba(53, 132, 228, 0.26)" not in active.group("body")
        assert "::after" not in css

    def test_common_avoids_pseudo_element_taskbar_indicator(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "::" not in css
        assert "box-shadow:" not in css
        assert "position:" not in css
        assert "border-radius: 50%" not in css
        assert "transition:" in css

    def test_complete_css_avoids_pseudo_element_taskbar_indicator(self):
        for tokens, layout_css in (
            (
                _make_tokens(edge="bottom", is_vertical=False),
                apply_settings._waybar_css_horizontal,
            ),
            (
                _make_tokens(edge="left", is_vertical=True),
                apply_settings._waybar_css_vertical,
            ),
        ):
            css = apply_settings._waybar_css_common(tokens) + layout_css(tokens)
            assert "::" not in css
            assert "box-shadow:" not in css
            assert "position:" not in css
            assert "border-radius: 50%" not in css
            assert "transition:" in css
            assert not re.search(r"border-radius:\s+[^;\n]+\s+[^;\n]+;", css)

    def test_common_pill_radius_on_window(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "border-radius: 999px" in css

    def test_common_hover_on_modules(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "#custom-launcher:hover" in css
        assert "#clock:hover" in css
        assert "#battery:hover" in css
        assert "#pulseaudio:hover" in css

    def test_common_has_modern_floating_panel_frame(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert 'font-family: "Roboto", "Adwaita Sans"' in css
        assert "background: rgba(30, 30, 30, 0.90)" in css
        assert "border: 1px solid rgba(255, 255, 255, 0.14)" in css

    def test_icon_modules_force_material_icons_font(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        icon_block = re.search(
            r"#custom-launcher,\n#pulseaudio, #backlight, #battery \{(?P<body>.*?)\n\}",
            css,
            re.S,
        )
        assert icon_block is not None
        assert 'font-family: "Material Icons Outlined", "Roboto"' in icon_block.group("body")


# ---------------------------------------------------------------------------
# Horizontal CSS — pill consistency
# ---------------------------------------------------------------------------

class TestHorizontalCss:
    def test_horizontal_pill_radius_on_modules(self):
        tokens = _make_tokens(edge="bottom")
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "border-radius: 999px" in css

    def test_horizontal_has_min_height_not_min_width(self):
        tokens = _make_tokens(edge="bottom")
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "min-height:" in css
        assert "min-width:" not in css

    def test_horizontal_active_state_uses_edge_running_indicator(self):
        tokens = _make_tokens(edge="bottom")
        css = (
            apply_settings._waybar_css_common(tokens)
            + apply_settings._waybar_css_horizontal(tokens)
        )
        active = re.search(r"#taskbar button\.active \{(?P<body>.*?)\n\}", css, re.S)
        assert active is not None
        assert "background: rgba(255, 255, 255, 0.10)" in active.group("body")
        assert "border-bottom: 3px solid #3584e4" in css
        assert "rgba(53, 132, 228, 0.26)" not in active.group("body")

    def test_horizontal_window_padding_horizontal_only(self):
        tokens = _make_tokens(edge="bottom")
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "padding: 0 " in css

    def test_horizontal_pinned_pill_radius(self):
        tokens = _make_tokens(
            edge="bottom",
            pinned=[
                {"name": "Chrome", "command": "chrome", "icon": "chrome"},
                {"name": "Firefox", "command": "firefox", "icon": "firefox"},
            ],
        )
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "#image.pin-0" in css
        assert "#image.pin-1" in css
        assert "border-radius: 999px" in css


# ---------------------------------------------------------------------------
# Waybar module compatibility
# ---------------------------------------------------------------------------

class TestWaybarModuleCompatibility:
    def test_taskbar_click_toggles_active_window_minimized(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert config["wlr/taskbar"]["on-click"] == "minimize-raise"
        assert config["wlr/taskbar"]["on-click-middle"] == "close"

    def test_config_groups_contiguous_status_modules(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "group/status-0" in config
        assert config["group/status-0"]["orientation"] == "inherit"
        assert config["group/status-0"]["modules"] == [
            "pulseaudio",
            "backlight",
            "battery",
            "clock",
        ]

    def test_status_group_preserves_user_order_and_excludes_tray(self, tmp_path):
        tokens = _make_tokens(
            layout={
                "start": ["custom/launcher"],
                "center": ["wlr/taskbar"],
                "end": ["clock", "battery", "tray", "pulseaudio", "backlight"],
            }
        )
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert config["modules-right"] == ["group/status-0", "tray", "group/status-1"]
        assert config["group/status-0"]["modules"] == ["clock", "battery"]
        assert config["group/status-1"]["modules"] == ["pulseaudio", "backlight"]
        assert "tray" not in config["group/status-0"]["modules"]
        assert "tray" not in config["group/status-1"]["modules"]

    def test_single_status_module_remains_direct_module(self, tmp_path):
        tokens = _make_tokens()
        tokens["layout"] = {
            "start": ["custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["clock", "tray"],
        }
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        modules = (
            config["modules-left"]
            + config["modules-center"]
            + config["modules-right"]
        )
        assert "clock" in modules
        assert not any(m.startswith("group/status") for m in modules)

    def test_tray_remains_direct_module(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        all_modules = (
            config["modules-left"]
            + config["modules-center"]
            + config["modules-right"]
        )
        assert "tray" in all_modules


# ---------------------------------------------------------------------------
# Grouped status pill CSS
# ---------------------------------------------------------------------------

class TestStatusPillCss:
    def test_horizontal_status_group_owns_single_pill_surface(self):
        tokens = _make_tokens(edge="bottom", is_vertical=False)
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "#group-status-0, #status-0 {" in css
        assert "border: 1px solid rgba(255, 255, 255, 0.18)" in css
        assert "border-radius: 999px" in css
        assert "#pulseaudio, #backlight, #battery, #clock" in css
        assert "background: rgba(255, 255, 255, 0.14)" in css
        assert "background: transparent" in css
        assert "border: none" in css
        assert "#tray" in css
        assert not re.search(r"border-radius:\s+[^;\n]+\s+[^;\n]+;", css)
        assert "margin-left:" not in css
        assert "margin-top:" not in css

    def test_vertical_status_group_owns_single_pill_surface(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = apply_settings._waybar_css_vertical(tokens)
        assert "#group-status-0, #status-0 {" in css
        assert "border: 1px solid rgba(255, 255, 255, 0.18)" in css
        assert "border-radius: 999px" in css
        assert "#pulseaudio, #backlight, #battery, #clock" in css
        assert "background: rgba(255, 255, 255, 0.14)" in css
        assert "background: transparent" in css
        assert "border: none" in css
        assert "#tray" in css
        assert not re.search(r"border-radius:\s+[^;\n]+\s+[^;\n]+;", css)
        assert "margin-left:" not in css
        assert "margin-top:" not in css

    def test_status_css_follows_layout_order_and_excludes_tray(self):
        tokens = _make_tokens(
            layout={
                "start": ["custom/launcher"],
                "center": ["wlr/taskbar"],
                "end": ["clock", "battery", "tray", "pulseaudio", "backlight"],
            }
        )
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "#group-status-0, #status-0, #group-status-1, #status-1 {" in css
        assert "#clock, #battery, #pulseaudio, #backlight" in css
        assert "#clock, #battery, #tray" not in css
        assert "margin-left:" not in css
        assert "margin-top:" not in css

    def test_single_status_module_remains_standalone_pill(self):
        tokens = _make_tokens(
            layout={
                "start": ["custom/launcher"],
                "center": ["wlr/taskbar"],
                "end": ["clock", "tray"],
            }
        )
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "#clock {" in css
        assert "#group-status-0" not in css
        assert "background: transparent" not in css


class TestAccentForegroundContrast:
    def test_yellow_accent_uses_dark_foreground(self):
        tokens = apply_settings._build_tokens(_make_settings(accent="yellow"))
        assert tokens["accent_hex"] == "#c88800"
        assert tokens["accent_fg_hex"] == "#1e1e1e"

    def test_foot_selection_foreground_follows_accent_contrast(self, tmp_path):
        tokens = apply_settings._build_tokens(_make_settings(accent="yellow"))
        with patch.object(apply_settings, "FOOT_DIR", tmp_path):
            apply_settings.write_foot_config(tokens)
        ini = (tmp_path / "foot.ini").read_text()
        assert "selection-background=c88800" in ini
        assert "selection-foreground=1e1e1e" in ini

    def test_labwc_menu_active_text_follows_accent_contrast(self, tmp_path):
        tokens = apply_settings._build_tokens(_make_settings(accent="yellow"))
        with patch.object(apply_settings, "LABWC_DIR", tmp_path):
            apply_settings.write_labwc_themerc(tokens)
        themerc = (tmp_path / "themerc-override").read_text()
        assert "menu.items.active.bg.color: #c88800" in themerc
        assert "menu.items.active.text.color: #1e1e1e" in themerc


class TestHighContrastShellConfigs:
    def test_high_contrast_resolves_dark_wallpaper_variant(self, monkeypatch, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps(_make_settings(
            high_contrast=True,
            wallpaper="universal-lite",
        )))
        light = tmp_path / "light.svg"
        dark = tmp_path / "dark.svg"
        light.write_text("<svg/>")
        dark.write_text("<svg/>")

        def fake_resolve(value, theme):
            assert value == "universal-lite"
            return str(dark if theme == "dark" else light)

        monkeypatch.setattr(apply_settings, "_resolve_wallpaper", fake_resolve)
        with patch.object(apply_settings, "SETTINGS_DIR", tmp_path), \
             patch.object(apply_settings, "SETTINGS_PATH", settings_file):
            result = apply_settings.ensure_settings()

        assert result["theme"] == "dark"
        assert result["wallpaper"] == str(dark)

    def test_high_contrast_tokens_strengthen_waybar_surfaces(self):
        tokens = apply_settings._build_tokens(
            _make_settings(theme="dark", high_contrast=True)
        )
        assert tokens["surface_base"] == "#000000"
        assert tokens["border_default"] == "#ffffff"
        assert tokens["panel_surface"] == "#000000"
        assert tokens["panel_alpha"] == "0.98"
        assert tokens["panel_border"] == "rgba(255, 255, 255, 0.55)"
        assert tokens["panel_status_border"] == "rgba(255, 255, 255, 0.55)"

    def test_high_contrast_mako_uses_stronger_border_and_surface(self, tmp_path):
        tokens = apply_settings._build_tokens(
            _make_settings(theme="dark", high_contrast=True)
        )
        with patch.object(apply_settings, "MAKO_DIR", tmp_path):
            apply_settings.write_mako_config(tokens)
        config = (tmp_path / "config").read_text()
        assert "background-color=#1d1d20FF" in config
        assert "border-color=#ffffffFF" in config
        assert "border-size=3" in config

    def test_high_contrast_foot_uses_opaque_black_surface(self, tmp_path):
        tokens = apply_settings._build_tokens(
            _make_settings(theme="dark", high_contrast=True)
        )
        with patch.object(apply_settings, "FOOT_DIR", tmp_path):
            apply_settings.write_foot_config(tokens)
        ini = (tmp_path / "foot.ini").read_text()
        assert "alpha=1.00" in ini
        assert "foreground=ffffff" in ini
        assert "background=000000" in ini

    def test_high_contrast_labwc_uses_stronger_borders(self, tmp_path):
        tokens = apply_settings._build_tokens(
            _make_settings(theme="dark", high_contrast=True)
        )
        with patch.object(apply_settings, "LABWC_DIR", tmp_path):
            apply_settings.write_labwc_themerc(tokens)
        themerc = (tmp_path / "themerc-override").read_text()
        assert "border.width: 2" in themerc
        assert "menu.border.width: 2" in themerc
        assert "menu.border.color: #ffffff" in themerc
        assert "osd.border.width: 2" in themerc
        assert "window.active.button.hover.bg.color: #434349" in themerc

    def test_high_contrast_swaylock_uses_stronger_indicator(self, tmp_path):
        tokens = apply_settings._build_tokens(
            _make_settings(theme="dark", high_contrast=True)
        )
        with patch.object(apply_settings, "SWAYLOCK_DIR", tmp_path):
            apply_settings.write_swaylock_config(tokens)
        config = (tmp_path / "config").read_text()
        assert "color=000000" in config
        assert "indicator-thickness=14" in config
        assert "inside-color=1d1d20cc" in config
        assert "ring-color=ffffff" in config


class TestSwaybgWallpaperSwap:
    def test_current_swaybg_wallpaper_parses_exact_quoted_command(self, monkeypatch):
        monkeypatch.setattr(apply_settings.os, "getuid", lambda: 1000)

        def fake_check_output(cmd, **_kwargs):
            assert cmd == ["pgrep", "-U", "1000", "-a", "-x", "swaybg"]
            return '123 swaybg -i "/home/user/My Wallpaper.svg" -m fill\n'

        monkeypatch.setattr(apply_settings.subprocess, "check_output", fake_check_output)

        assert apply_settings._current_swaybg_wallpaper() == "/home/user/My Wallpaper.svg"

    def test_swap_swaybg_starts_new_before_stopping_old(self, monkeypatch, tmp_path):
        wallpaper = tmp_path / "wall.svg"
        wallpaper.write_text("<svg/>")
        calls = []

        class Proc:
            pid = 222

            def poll(self):
                return None

        def fake_popen(cmd, **_kwargs):
            calls.append(("popen", cmd))
            return Proc()

        monkeypatch.setattr(apply_settings.shutil, "which", lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr(apply_settings, "_pids_for_program", lambda name: [111])
        monkeypatch.setattr(apply_settings.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(apply_settings.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(apply_settings.os, "kill", lambda pid, sig: calls.append(("kill", pid, sig)))

        apply_settings._swap_swaybg_wallpaper(str(wallpaper))

        assert calls[0] == ("popen", ["swaybg", "-i", str(wallpaper), "-m", "fill"])
        assert calls[1] == ("kill", 111, apply_settings.signal.SIGTERM)

    def test_swap_swaybg_keeps_old_wallpaper_if_new_exits(self, monkeypatch, tmp_path):
        wallpaper = tmp_path / "wall.svg"
        wallpaper.write_text("<svg/>")
        killed = []

        class Proc:
            pid = 222

            def poll(self):
                return 1

        monkeypatch.setattr(apply_settings.shutil, "which", lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr(apply_settings, "_pids_for_program", lambda name: [111])
        monkeypatch.setattr(apply_settings.subprocess, "Popen", lambda *_args, **_kwargs: Proc())
        monkeypatch.setattr(apply_settings.time, "sleep", lambda _seconds: None)
        monkeypatch.setattr(apply_settings.os, "kill", lambda pid, sig: killed.append((pid, sig)))

        apply_settings._swap_swaybg_wallpaper(str(wallpaper))

        assert killed == []
