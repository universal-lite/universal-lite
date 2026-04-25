from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MIMEAPPS = REPO / "files/etc/xdg/mimeapps.list"
APPLICATIONS = REPO / "files/usr/share/applications"


def _defaults() -> dict[str, str]:
    defaults = {}
    in_default_section = False
    for raw_line in MIMEAPPS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_default_section = line == "[Default Applications]"
            continue
        if in_default_section and "=" in line:
            mime_type, desktop_id = line.split("=", 1)
            defaults[mime_type] = desktop_id
    return defaults


def test_text_defaults_use_current_mousepad_desktop_id():
    defaults = _defaults()

    assert defaults["text/plain"] == "org.xfce.mousepad.desktop"
    assert defaults["text/x-python"] == "org.xfce.mousepad.desktop"


def test_legacy_mousepad_desktop_id_stays_launchable_but_hidden():
    alias = (APPLICATIONS / "mousepad.desktop").read_text(encoding="utf-8")

    assert "Exec=mousepad %U" in alias
    assert "NoDisplay=true" in alias
    assert "MimeType=text/plain;application/x-zerosize;text/x-python;" in alias
