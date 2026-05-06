from pathlib import Path


FLATPAK_SETUP = (
    Path(__file__).resolve().parents[1]
    / "files/usr/libexec/universal-lite-flatpak-setup"
)


def test_initial_install_completion_checks_apps_and_runtimes():
    script = FLATPAK_SETUP.read_text()

    assert "flatpak list --system --columns=application" in script
    assert "flatpak list --system --app --columns=application" not in script
