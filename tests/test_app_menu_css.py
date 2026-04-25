"""Tests for the Universal-Lite start menu stylesheet."""

import ast
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "files/usr/bin/universal-lite-app-menu"


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
    assert "background-color: alpha(@window_bg_color, 0.88)" in css
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
