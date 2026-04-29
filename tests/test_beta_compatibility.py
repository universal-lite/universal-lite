from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_beta_package_list_avoids_removed_fedora_44_theme_package():
    build_script = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

    assert "gnome-themes-extra" not in build_script
