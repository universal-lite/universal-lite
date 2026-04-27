"""Tests for the Universal-Lite start menu stylesheet."""

import importlib.machinery
import importlib.util
import json
import os
import signal
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "files/usr/bin/universal-lite-app-menu"
_loader = importlib.machinery.SourceFileLoader("app_menu", str(_SCRIPT))
_spec = importlib.util.spec_from_loader("app_menu", _loader, origin=str(_SCRIPT))
app_menu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_menu)


def _css() -> str:
    return app_menu.CSS.decode("utf-8")


def test_start_menu_uses_waybar_aligned_theme_tokens():
    css = _css()
    assert 'font-family: "Roboto", "Adwaita Sans", sans-serif' in css
    assert "background-color: alpha(@window_bg_color, 0.90)" in css
    assert "background-color: transparent" in css
    assert "border-radius: 24px" in css
    assert ".app-menu-surface-compact {" in css
    assert "border-radius: 18px" in css
    assert "background: alpha(@window_fg_color, 0.08)" in css
    assert "background: alpha(@accent_color, 0.14)" in css


def test_start_menu_borders_use_adwaita_border_token():
    css = _css()
    assert "border: 1px solid @borders" in css
    assert "border-top: 1px solid @borders" in css
    assert "border: 1px solid alpha(@window_fg_color" not in css
    assert "border-top: 1px solid alpha(@window_fg_color" not in css


def test_secondary_text_keeps_light_theme_contrast_headroom():
    css = _css()
    assert "color: alpha(@window_fg_color, 0.70)" in css
    assert "color: alpha(@window_fg_color, 0.72)" in css


def test_app_tiles_are_flat_until_interaction():
    css = _css()
    assert "padding: 4px 2px 6px 2px;" in css
    assert ".app-menu-tile {\n    background: transparent;" in css
    assert "border: 1px solid transparent;" in css
    assert ".app-menu-tile:hover,\n.app-menu-tile:focus {" in css
    assert "background: alpha(@accent_color, 0.10)" in css
    assert "0 0 0 2px alpha(@accent_color, 0.20)" in css
    assert ".app-menu-tile:active {\n    background: @accent_color;" in css
    assert "color: @accent_fg_color;" in css


def test_twilight_mode_chooses_opposite_menu_palette():
    assert app_menu._shell_theme_class({"theme": "light"}) is None
    assert app_menu._shell_theme_class(
        {"theme": "light", "panel_twilight": True}
    ) == "app-menu-shell-dark"
    assert app_menu._shell_theme_class(
        {"theme": "dark", "panel_twilight": True}
    ) == "app-menu-shell-light"


def test_twilight_menu_palette_matches_waybar_surface_tokens():
    css = _css()
    palette = json.loads(
        (Path(__file__).resolve().parents[1]
         / "files/usr/share/universal-lite/palette.json").read_text(
             encoding="utf-8"
         )
    )
    dark = app_menu._twilight_palette_tokens(palette["dark"])
    light = app_menu._twilight_palette_tokens(palette["light"])

    assert "window.app-menu.app-menu-shell-dark .app-menu-surface" in css
    assert f"background-color: {dark['surface']}" in css
    assert f"color: {dark['fg']}" in css
    assert f"border: 1px solid {dark['border']}" in css
    assert "window.app-menu.app-menu-shell-light .app-menu-surface" in css
    assert f"background-color: {light['surface']}" in css
    assert f"color: {light['fg']}" in css
    assert f"border: 1px solid {light['border']}" in css


def test_twilight_css_is_generated_from_palette_values():
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "background-color: rgba(34, 34, 38, 0.90)" not in source
    assert "background-color: rgba(250, 250, 250, 0.90)" not in source

    css = app_menu._build_twilight_css({
        "dark": {
            "window_bg": "#010203",
            "fg": "#f0e0d0",
        },
        "light": {
            "window_bg": "#f9f8f7",
            "fg": "#102030",
        },
    })

    assert "background-color: rgba(1, 2, 3, 0.90)" in css
    assert "color: #f0e0d0" in css
    assert "border: 1px solid rgba(240, 224, 208, 0.14)" in css
    assert "background-color: rgba(249, 248, 247, 0.90)" in css
    assert "color: #102030" in css
    assert "border: 1px solid rgba(16, 32, 48, 0.10)" in css


def test_start_menu_metrics_fit_1024x600_bottom_panel():
    metrics = app_menu._menu_metrics(
        {"density": "comfortable", "font_size": 11},
        {"edge": "bottom", "section": "start"},
        (1024, 600),
    )

    assert metrics["width"] == app_menu.MENU_WIDTH_IDEAL
    assert metrics["height"] == 496
    assert metrics["columns"] == app_menu.GRID_COLUMNS_MAX
    assert metrics["mode"] == "popover"
    assert metrics["show_frequent"] is True


def test_start_menu_metrics_scale_tiles_and_reduce_columns_for_large_text():
    metrics = app_menu._menu_metrics(
        {"density": "comfortable", "font_size": 24},
        {"edge": "bottom", "section": "start"},
        (1024, 600),
    )

    assert metrics["height"] <= 600 - 56 - round(48 * 1.35)
    assert metrics["tile_width"] > app_menu.TILE_WIDTH_BASE
    assert metrics["tile_height"] > app_menu.TILE_HEIGHT_BASE
    assert metrics["columns"] < app_menu.GRID_COLUMNS_MAX
    assert metrics["mode"] == "popover"


def test_start_menu_metrics_fit_1360x768_at_200_percent_scale():
    # GDK widget sizes are in logical/application pixels. A 1360x768
    # output at 200% scale leaves a 680x384 logical viewport; the menu
    # must fit that viewport, not the raw physical mode.
    metrics = app_menu._menu_metrics(
        {"density": "comfortable", "font_size": 11},
        {"edge": "bottom", "section": "start"},
        (680, 384),
    )

    assert metrics["mode"] == "compact"
    assert metrics["show_frequent"] is False
    assert metrics["surface_margin"] == app_menu.COMPACT_INSET
    assert metrics["width"] == 680 - (2 * app_menu.COMPACT_INSET)
    assert metrics["height"] <= 384 - (
        2 * app_menu.COMPACT_INSET
    ) - app_menu._panel_extent({"density": "comfortable", "font_size": 11}, "bottom")
    assert metrics["columns"] == app_menu.GRID_COLUMNS_MAX


def test_display_size_normalization_uses_configured_output_scale_once():
    assert app_menu._logical_display_size(1360, 768, 2.0) == (680, 384)
    assert app_menu._logical_display_size(680, 384, 2.0) == (680, 384)


def test_toggle_or_lock_replaces_foreign_live_pid_without_signalling(monkeypatch, tmp_path):
    lock = tmp_path / "universal-lite-app-menu.pid"
    lock.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(app_menu, "PID_LOCK_PATH", lock)
    monkeypatch.setattr(app_menu, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(app_menu, "_process_matches_lock_identity", lambda pid: False)

    def fail_kill(pid, sig):
        raise AssertionError(f"unexpected signal {sig} to pid {pid}")

    monkeypatch.setattr(app_menu.os, "kill", fail_kill)

    assert app_menu._toggle_or_lock() is True
    assert lock.read_text(encoding="utf-8") == str(os.getpid())
    app_menu._release_lock()


def test_toggle_or_lock_signals_verified_app_menu_process(monkeypatch, tmp_path):
    lock = tmp_path / "universal-lite-app-menu.pid"
    lock.write_text("12345", encoding="utf-8")
    monkeypatch.setattr(app_menu, "PID_LOCK_PATH", lock)
    monkeypatch.setattr(app_menu, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(app_menu, "_process_matches_lock_identity", lambda pid: True)

    sent = []

    def record_kill(pid, sig):
        sent.append((pid, sig))

    monkeypatch.setattr(app_menu.os, "kill", record_kill)

    assert app_menu._toggle_or_lock() is False
    assert sent == [(12345, signal.SIGTERM)]
