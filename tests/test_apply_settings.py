"""Tests for waybar-related functions in universal-lite-apply-settings."""

import importlib.machinery
import importlib.util
import json
import os
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
        # Styling tokens
        "font_ui": "Roboto",
        "font_size_ui": 13,
        "text_primary": "#1e1e1e",
        "text_secondary": "#5e5c64",
        "surface_base": "#fafafa",
        "surface_card": "#ffffff",
        "border_default": "#d3d3d3",
        "state_hover": "rgba(30, 30, 30, 0.08)",
        "accent_hex": "#3584e4",
        "accent_rgba_15": "rgba(53, 132, 228, 0.15)",
        "color_warning": "#e5a50a",
        "color_error": "#c01c28",
        "panel_surface": "#1e1e1e",
        "panel_fg": "#ffffff",
        "panel_secondary_fg": "#9a9a9a",
        "panel_hover": "rgba(255, 255, 255, 0.08)",
        "panel_bar_inset": 4,
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
        assert "custom/pin-0" in left
        assert left.index("custom/pin-0") == left.index("custom/launcher") + 1

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
        assert "custom/pin-0" not in config["modules-left"]
        center = config["modules-center"]
        assert center.index("custom/pin-0") == center.index("custom/launcher") + 1
        assert center.index("custom/pin-1") == center.index("custom/launcher") + 2

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
        assert "custom/pin-0" not in config["modules-left"]
        right = config["modules-right"]
        assert right.index("custom/pin-0") == right.index("custom/launcher") + 1

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
        assert config["modules-left"][0] == "custom/pin-0"

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

    def test_vertical_no_border_direction(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = apply_settings._waybar_css_vertical(tokens)
        assert "border-right:" not in css
        assert "border-left:" not in css
        assert "border-bottom:" not in css

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
    def test_common_has_launcher_circle(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "border-radius: 50%" in css

    def test_common_has_dot_indicator(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "::after" in css
        assert "width: 6px" in css
        assert "width: 16px" in css

    def test_common_has_transitions(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "transition:" in css

    def test_common_pill_radius_on_window(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "border-radius: 999px" in css

    def test_common_hover_on_modules(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "#custom-launcher:hover" in css
        assert "#clock:hover" in css
        assert "#battery:hover" in css
        assert "#pulseaudio:hover" in css


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

    def test_horizontal_no_border_bottom_active(self):
        tokens = _make_tokens(edge="bottom")
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "border-bottom:" not in css

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
# group/status module
# ---------------------------------------------------------------------------

class TestStatusGroup:
    def test_group_status_in_config(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "group/status" in config

    def test_group_status_orientation_horizontal(self, tmp_path):
        tokens = _make_tokens(edge="bottom", is_vertical=False)
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert config["group/status"]["orientation"] == "horizontal"

    def test_group_status_orientation_vertical(self, tmp_path):
        tokens = _make_tokens(edge="left", is_vertical=True)
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert config["group/status"]["orientation"] == "vertical"

    def test_status_modules_in_group(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        modules = config["group/status"]["modules"]
        for m in ["pulseaudio", "backlight", "battery", "clock"]:
            assert m in modules

    def test_tray_not_in_group(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "tray" not in config["group/status"]["modules"]

    def test_module_list_uses_group_not_individual(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        all_modules = (
            config["modules-left"]
            + config["modules-center"]
            + config["modules-right"]
        )
        for m in ["pulseaudio", "backlight", "battery", "clock"]:
            assert m not in all_modules
        assert "group/status" in all_modules

    def test_no_group_when_no_status_modules(self, tmp_path):
        tokens = _make_tokens(
            layout={
                "start": ["custom/launcher"],
                "center": ["wlr/taskbar"],
                "end": ["custom/power", "tray"],
            },
        )
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "group/status" not in config

    def test_no_group_when_status_modules_not_contiguous(self, tmp_path):
        tokens = _make_tokens(layout={
            "start": ["custom/launcher"],
            "center": ["wlr/taskbar"],
            "end": ["pulseaudio", "tray", "battery", "clock"],
        })
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "group/status" not in config
        all_modules = config["modules-left"] + config["modules-center"] + config["modules-right"]
        assert "pulseaudio" in all_modules
        assert "battery" in all_modules
