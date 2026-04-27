from pathlib import Path


CSS_PATH = (
    Path(__file__).resolve().parents[1]
    / "files/usr/lib/universal-lite/settings/css/style.css"
)
WINDOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "files/usr/lib/universal-lite/settings/window.py"
)


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _window_source() -> str:
    return WINDOW_PATH.read_text(encoding="utf-8")


def test_sidebar_uses_stock_libadwaita_split_view_styling():
    css = _css()
    source = _window_source()

    assert ".settings-split-view > .sidebar-pane" not in css
    assert ".settings-sidebar-pane" not in css
    assert ".settings-sidebar-separator" not in css
    assert "content-area" not in css
    assert "box-shadow: inset -1px 0 @borders;" not in css
    assert "border-right: 1px solid @borders;" not in css
    assert ".sidebar {\n" not in css
    assert 'add_css_class("settings-split-view")' not in source
    assert 'add_css_class("settings-sidebar-pane")' not in source
    assert 'add_css_class("settings-sidebar-header")' not in source
    assert 'add_css_class("content-area")' not in source


def test_sidebar_does_not_override_navigation_sidebar_children():
    css = _css()
    source = _window_source()

    assert ".settings-sidebar-pane headerbar" not in css
    assert ".settings-sidebar-pane scrolledwindow" not in css
    assert ".settings-sidebar-pane list" not in css
    assert ".settings-sidebar-pane row" not in css
    assert ".sidebar row" not in css
    assert 'add_css_class("navigation-sidebar")' in source
    assert 'add_css_class("sidebar")' not in source
    assert 'add_css_class("category-icon")' not in source
    assert 'add_css_class("category-label")' not in source
    assert "self._sidebar.set_margin_top" not in source
    assert "self._sidebar.set_margin_bottom" not in source
