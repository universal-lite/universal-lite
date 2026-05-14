from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OOMD_CONF = REPO / "files/usr/lib/systemd/oomd.conf.d/10-universal-lite.conf"
ROOT_SLICE_OOMD = (
    REPO / "files/usr/lib/systemd/system/-.slice.d/10-universal-lite-oomd.conf"
)
USER_SERVICE_OOMD = (
    REPO
    / "files/usr/lib/systemd/system/user@.service.d/10-universal-lite-oomd.conf"
)


def test_oomd_global_thresholds_fire_before_zram_is_exhausted():
    conf = OOMD_CONF.read_text(encoding="utf-8")

    assert "SwapUsedLimit=80%" in conf
    assert "DefaultMemoryPressureLimit=50%" in conf
    assert "DefaultMemoryPressureDurationSec=20s" in conf


def test_oomd_monitors_root_slice_for_swap_exhaustion():
    conf = ROOT_SLICE_OOMD.read_text(encoding="utf-8")

    assert "[Slice]" in conf
    assert "ManagedOOMSwap=kill" in conf


def test_oomd_monitors_user_sessions_for_memory_pressure():
    conf = USER_SERVICE_OOMD.read_text(encoding="utf-8")

    assert "[Service]" in conf
    assert "ManagedOOMMemoryPressure=kill" in conf
    assert "ManagedOOMMemoryPressureLimit=50%" in conf
