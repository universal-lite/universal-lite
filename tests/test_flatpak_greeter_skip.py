import importlib.machinery
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GREETER = ROOT / "files/usr/bin/universal-lite-greeter"
SKIP_MARKER = "/var/lib/universal-lite/flatpak-setup.skip"
SKIP_HELPER = "/usr/libexec/universal-lite-flatpak-skip"


def _load_greeter_module():
    loader = importlib.machinery.SourceFileLoader("universal_lite_greeter", str(GREETER))
    spec = importlib.util.spec_from_loader(
        "universal_lite_greeter", loader, origin=str(GREETER)
    )
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(GREETER)
    spec.loader.exec_module(module)
    return module


class _FakeSpinner:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeStack:
    def __init__(self):
        self.visible_child = None

    def set_visible_child_name(self, name):
        self.visible_child = name


class _FakeLabel:
    def __init__(self):
        self.text = ""
        self.visible = False

    def set_text(self, text):
        self.text = text

    def set_visible(self, visible):
        self.visible = visible


class _FakeWidget:
    def __init__(self):
        self.visible = True

    def set_visible(self, visible):
        self.visible = visible


class _FakePath:
    def __init__(self, exists):
        self._exists = exists

    def exists(self):
        return self._exists



def test_greeter_defines_skip_marker_path():
    module = _load_greeter_module()

    assert str(module.FLATPAK_SKIP_PATH) == SKIP_MARKER


def test_greeter_setup_in_progress_treats_skip_marker_as_non_blocking(monkeypatch):
    module = _load_greeter_module()
    window = module.GreeterWindow.__new__(module.GreeterWindow)

    monkeypatch.setattr(module, "SETUP_DONE_PATH", _FakePath(True))
    monkeypatch.setattr(module, "FLATPAK_DONE_PATH", _FakePath(False))
    monkeypatch.setattr(module, "FLATPAK_LOGIN_READY_PATH", _FakePath(False))
    monkeypatch.setattr(module, "FLATPAK_SKIP_PATH", _FakePath(True), raising=False)

    assert module.GreeterWindow._is_setup_in_progress(window) is False


def test_greeter_poll_reveals_login_when_skip_marker_exists(monkeypatch):
    module = _load_greeter_module()
    window = module.GreeterWindow.__new__(module.GreeterWindow)
    window._setup_spinner = _FakeSpinner()
    window._stack = _FakeStack()
    window._setup_progress_label = _FakeLabel()
    window._setup_elapsed_s = 0

    monkeypatch.setattr(module, "FLATPAK_DONE_PATH", _FakePath(False))
    monkeypatch.setattr(module, "FLATPAK_LOGIN_READY_PATH", _FakePath(False))
    monkeypatch.setattr(module, "FLATPAK_SKIP_PATH", _FakePath(True), raising=False)

    result = module.GreeterWindow._poll_setup_progress(window)

    assert result == module.GLib.SOURCE_REMOVE
    assert window._setup_spinner.stopped is True
    assert window._stack.visible_child == "login"


def test_greeter_skip_confirmation_copy_mentions_flatpak_not_bazaar():
    source = GREETER.read_text()

    assert "Selected apps will not be installed automatically" in source
    assert "flatpak from the terminal" in source
    copy_start = source.index("Selected apps will not be installed automatically")
    confirmation_copy = source[max(copy_start - 200, 0) : copy_start + 400]
    assert "Bazaar" not in confirmation_copy


def test_greeter_skip_confirmation_is_inline_and_actionable():
    module = _load_greeter_module()
    window = module.GreeterWindow.__new__(module.GreeterWindow)
    window._setup_skip_confirm_label = _FakeLabel()
    window._setup_skip_confirm_actions = _FakeWidget()
    window._setup_skip_btn = _FakeWidget()

    module.GreeterWindow._confirm_flatpak_setup_skip(window)

    assert "Selected apps will not be installed automatically" in (
        window._setup_skip_confirm_label.text
    )
    assert "flatpak from the terminal" in window._setup_skip_confirm_label.text
    assert window._setup_skip_confirm_label.visible is True
    assert window._setup_skip_confirm_actions.visible is True
    assert window._setup_skip_btn.visible is False


def test_greeter_skip_confirmation_can_be_cancelled():
    module = _load_greeter_module()
    window = module.GreeterWindow.__new__(module.GreeterWindow)
    window._setup_skip_confirm_label = _FakeLabel()
    window._setup_skip_confirm_actions = _FakeWidget()
    window._setup_skip_btn = _FakeWidget()

    module.GreeterWindow._cancel_flatpak_setup_skip(window)

    assert window._setup_skip_confirm_label.visible is False
    assert window._setup_skip_confirm_actions.visible is False
    assert window._setup_skip_btn.visible is True


def test_greeter_uses_privileged_skip_helper():
    source = GREETER.read_text()

    assert SKIP_HELPER in source
    assert "sudo" in source
    assert "subprocess.run" in source


def test_apply_flatpak_skip_runs_helper_and_reveals_login(monkeypatch):
    module = _load_greeter_module()
    window = module.GreeterWindow.__new__(module.GreeterWindow)
    window._setup_spinner = _FakeSpinner()
    window._stack = _FakeStack()
    window._setup_progress_label = _FakeLabel()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module.GreeterWindow._apply_flatpak_setup_skip(window)

    assert calls == [
        (
            ["sudo", "-n", SKIP_HELPER],
            {"check": True, "timeout": 10},
        )
    ]
    assert window._setup_spinner.stopped is True
    assert window._stack.visible_child == "login"
    assert window._setup_progress_label.text == ""


def test_apply_flatpak_skip_failure_keeps_overlay_visible(monkeypatch):
    module = _load_greeter_module()
    window = module.GreeterWindow.__new__(module.GreeterWindow)
    window._setup_spinner = _FakeSpinner()
    window._stack = _FakeStack()
    window._setup_progress_label = _FakeLabel()

    def fake_run(command, **kwargs):
        raise module.subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module.GreeterWindow._apply_flatpak_setup_skip(window)
    assert window._setup_spinner.stopped is False
    assert window._stack.visible_child is None
    assert "Could not skip app setup" in window._setup_progress_label.text
