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
        "panel_alpha": "0.90",
        "panel_border": "rgba(255, 255, 255, 0.14)",
        "panel_control_bg": "rgba(255, 255, 255, 0.10)",
        "panel_control_hover": "rgba(255, 255, 255, 0.14)",
        "panel_control_border": "rgba(255, 255, 255, 0.12)",
        "panel_status_bg": "rgba(255, 255, 255, 0.14)",
        "panel_status_border": "rgba(255, 255, 255, 0.18)",
        "panel_accent_bg": "rgba(53, 132, 228, 0.26)",
        "panel_accent_border": "rgba(53, 132, 228, 0.42)",
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

    def test_vertical_active_state_avoids_edge_strip_indicator(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = (
            apply_settings._waybar_css_common(tokens)
            + apply_settings._waybar_css_vertical(tokens)
        )
        active = re.search(r"#taskbar button\.active \{(?P<body>.*?)\n\}", css, re.S)
        assert active is not None
        assert "border-left:" not in active.group("body")
        assert "border-right:" not in active.group("body")
        assert "border-bottom:" not in active.group("body")

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
    def test_common_has_launcher_pill(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "border-radius: 999px" in css

    def test_common_has_active_taskbar_state(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "#taskbar button.active" in css
        assert "rgba(53, 132, 228, 0.26)" in css
        assert "rgba(53, 132, 228, 0.42)" in css
        assert "::after" not in css

    def test_common_avoids_unsupported_gtk_css(self):
        css = apply_settings._waybar_css_common(_make_tokens())
        assert "::" not in css
        assert "transition:" not in css
        assert "box-shadow:" not in css
        assert "position:" not in css
        assert "border-radius: 50%" not in css

    def test_complete_css_avoids_unsupported_gtk_css(self):
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
            assert "transition:" not in css
            assert "box-shadow:" not in css
            assert "position:" not in css
            assert "border-radius: 50%" not in css
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

    def test_horizontal_active_state_avoids_edge_strip_indicator(self):
        tokens = _make_tokens(edge="bottom")
        css = (
            apply_settings._waybar_css_common(tokens)
            + apply_settings._waybar_css_horizontal(tokens)
        )
        active = re.search(r"#taskbar button\.active \{(?P<body>.*?)\n\}", css, re.S)
        assert active is not None
        assert "border-bottom:" not in active.group("body")

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
    def test_config_does_not_use_group_module(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        assert "group/status" not in config

    def test_status_modules_remain_direct_modules(self, tmp_path):
        tokens = _make_tokens()
        with patch.object(apply_settings, "WAYBAR_DIR", tmp_path):
            apply_settings.write_waybar_config(tokens)
        config = json.loads((tmp_path / "config.jsonc").read_text())
        modules = (
            config["modules-left"]
            + config["modules-center"]
            + config["modules-right"]
        )
        for m in ["pulseaudio", "backlight", "battery", "clock"]:
            assert m in modules

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
# Faux grouped status pill CSS
# ---------------------------------------------------------------------------

class TestStatusPillCss:
    def test_horizontal_status_modules_share_background(self):
        tokens = _make_tokens(edge="bottom", is_vertical=False)
        css = apply_settings._waybar_css_horizontal(tokens)
        assert "#pulseaudio, #backlight, #battery, #clock" in css
        assert "background: rgba(255, 255, 255, 0.14)" in css
        assert "border-top: 1px solid rgba(255, 255, 255, 0.18)" in css
        assert "border-bottom: 1px solid rgba(255, 255, 255, 0.18)" in css
        assert "border-top-left-radius: 999px" in css
        assert "border-bottom-left-radius: 999px" in css
        assert "border-top-right-radius: 999px" in css
        assert "border-bottom-right-radius: 999px" in css
        assert "#tray" in css
        assert not re.search(r"border-radius:\s+[^;\n]+\s+[^;\n]+;", css)
        assert "margin-left: -10px" in css

    def test_vertical_status_modules_stack_as_pill(self):
        tokens = _make_tokens(edge="left", is_vertical=True)
        css = apply_settings._waybar_css_vertical(tokens)
        assert "#pulseaudio, #backlight, #battery, #clock" in css
        assert "background: rgba(255, 255, 255, 0.14)" in css
        assert "border-left: 1px solid rgba(255, 255, 255, 0.18)" in css
        assert "border-right: 1px solid rgba(255, 255, 255, 0.18)" in css
        assert "border-top-left-radius: 999px" in css
        assert "border-top-right-radius: 999px" in css
        assert "border-bottom-left-radius: 999px" in css
        assert "border-bottom-right-radius: 999px" in css
        assert "#tray" in css
        assert not re.search(r"border-radius:\s+[^;\n]+\s+[^;\n]+;", css)
        assert "margin-top: -10px" in css
