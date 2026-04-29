from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_beta_package_list_avoids_removed_fedora_44_theme_package():
    build_script = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

    assert "gnome-themes-extra" not in build_script


def test_beta_tolerates_unready_fedora_44_rpmfusion_multimedia_packages():
    build_script = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

    assert 'if [[ "$FEDORA_MAJOR" -ge 44 ]]; then' in build_script
    assert "--skip-unavailable" in build_script
    assert "rpmfusion multimedia packages are unavailable on Fedora ${FEDORA_MAJOR}" in build_script
