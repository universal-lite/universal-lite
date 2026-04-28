import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "files/usr/lib/universal-lite"))

from settings import app as settings_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CSS_PATH = ROOT / "files/usr/lib/universal-lite/settings/css/style.css"
APPEARANCE_PATH = ROOT / "files/usr/lib/universal-lite/settings/pages/appearance.py"
BUILD_PATH = ROOT / "build_files/build.sh"
THUMBNAILER_PATH = ROOT / "files/usr/libexec/universal-lite-wallpaper-thumbnailer"


def test_accent_css_uses_contrast_aware_selected_check_color(
    monkeypatch, tmp_path
):
    palette_path = tmp_path / "palette.json"
    palette_path.write_text(
        """
        {
          "accents": {
            "purple": "#9141ac",
            "yellow": "#c88800"
          }
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_app, "PALETTE_PATH", palette_path)

    css = settings_app._build_accent_css()

    assert ".accent-purple { background-color: #9141ac; }" in css
    assert ".accent-purple:checked image { color: #ffffff; }" in css
    assert ".accent-yellow { background-color: #c88800; }" in css
    assert ".accent-yellow:checked image { color: #2e3436; }" in css


def test_picker_css_uses_adwaita_style_selection_states():
    css = CSS_PATH.read_text(encoding="utf-8")

    assert ".accent-swatch" in css
    assert ".accent-swatch:focus-visible" in css
    assert ".accent-circle" not in css
    assert ".wallpaper-check" in css
    assert ".wallpaper-tile:focus-visible" in css
    assert "background: alpha(@window_fg_color, 0.05);" in css
    assert ".wallpaper-placeholder" in css


def test_wallpaper_tiles_use_non_interactive_selection_badge():
    source = APPEARANCE_PATH.read_text(encoding="utf-8")

    assert 'check.add_css_class("wallpaper-check")' in source
    assert "check.set_can_target(False)" in source
    assert "self._sync_wallpaper_selection()" in source


def test_theme_toggle_defers_wallpaper_refresh_out_of_signal_handler():
    source = APPEARANCE_PATH.read_text(encoding="utf-8")

    assert "self._queue_wallpaper_refresh()" in source
    assert "GLib.idle_add(_refresh)" in source
    assert "def _safe_populate_wallpapers" in source


def test_risky_wallpaper_thumbnails_use_isolated_helper_with_placeholder_fallback():
    source = APPEARANCE_PATH.read_text(encoding="utf-8")
    helper = THUMBNAILER_PATH.read_text(encoding="utf-8")
    build = BUILD_PATH.read_text(encoding="utf-8")

    assert 'RISKY_THUMBNAIL_EXTS = {".jxl", ".avif", ".heif", ".heic"}' in source
    assert "def _load_external_thumbnail" in source
    assert "subprocess.run(" in source
    assert "THUMBNAIL_TIMEOUT_SECONDS" in source
    risky_branch = source.split("def _load_thumbnail", 1)[1].split("try:", 1)[0]
    assert "return _load_external_thumbnail(path) or _thumbnail_placeholder()" in risky_branch
    assert "return _thumbnail_placeholder()" in source.split(
        "except Exception as exc:  # GLib.Error, etc.", 1
    )[1]
    assert "GdkPixbuf.PixbufLoader.new()" in helper
    assert "loader.write(chunk)" in helper
    assert 'os.environ.setdefault("GIO_USE_VFS", "local")' in helper
    assert 'pixbuf.savev(str(tmp), "png", [], [])' in helper
    assert "os.replace(tmp, dest)" in helper
    assert "/usr/libexec/universal-lite-wallpaper-thumbnailer" in build
