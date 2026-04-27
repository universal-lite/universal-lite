import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "files/usr/lib/universal-lite"))

from settings import app as settings_app  # noqa: E402


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
