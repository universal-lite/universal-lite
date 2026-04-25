"""Tests for the Universal-Lite start menu stylesheet."""

import ast
import importlib.machinery
import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "files/usr/bin/universal-lite-app-menu"
_loader = importlib.machinery.SourceFileLoader("app_menu", str(_SCRIPT))
_spec = importlib.util.spec_from_loader("app_menu", _loader, origin=str(_SCRIPT))
app_menu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_menu)


def _css() -> str:
    module = ast.parse(_SCRIPT.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "CSS":
                return ast.literal_eval(node.value).decode("utf-8")
    raise AssertionError("CSS assignment not found")


def test_start_menu_uses_waybar_aligned_theme_tokens():
    css = _css()
    assert 'font-family: "Roboto", "Adwaita Sans", sans-serif' in css
    assert "background-color: alpha(@window_bg_color, 0.90)" in css
    assert "background-color: transparent" in css
    assert "border-radius: 24px" in css
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
    assert "window.app-menu.app-menu-shell-dark .app-menu-surface" in css
    assert "background-color: rgba(34, 34, 38, 0.90)" in css
    assert "color: #ffffff" in css
    assert "border: 1px solid rgba(255, 255, 255, 0.14)" in css
    assert "window.app-menu.app-menu-shell-light .app-menu-surface" in css
    assert "background-color: rgba(250, 250, 250, 0.90)" in css
    assert "color: #1e1e1e" in css
    assert "border: 1px solid rgba(30, 30, 30, 0.10)" in css
