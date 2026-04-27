from pathlib import Path


CSS_PATH = (
    Path(__file__).resolve().parents[1]
    / "files/usr/lib/universal-lite/settings/css/style.css"
)


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def test_sidebar_pane_owns_full_height_separator():
    css = _css()

    assert ".settings-sidebar-pane {" in css
    assert "border-right: 1px solid @borders;" in css
    assert ".sidebar {\n" not in css


def test_sidebar_children_are_transparent_inside_pane():
    css = _css()

    assert ".settings-sidebar-pane headerbar," in css
    assert ".settings-sidebar-pane scrolledwindow," in css
    assert ".settings-sidebar-pane list," in css
    assert ".settings-sidebar-pane row {" in css
    assert "background: transparent;" in css
