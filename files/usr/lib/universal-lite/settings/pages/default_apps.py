import subprocess
from gettext import gettext as _
from pathlib import Path

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gio, Gtk

from ..base import BasePage

APP_MIME_TYPES = [
    (_("Web Browser"), "x-scheme-handler/http"),
    (_("File Manager"), "inode/directory"),
    (_("Terminal"), None),
    (_("Text Editor"), "text/plain"),
    (_("Image Viewer"), "image/png"),
    (_("PDF Viewer"), "application/pdf"),
    (_("Media Player"), "video/x-matroska"),
    (_("Email Client"), "x-scheme-handler/mailto"),
]


class DefaultAppsPage(BasePage, Adw.PreferencesPage):
    def __init__(self, store, event_bus):
        BasePage.__init__(self, store, event_bus)
        Adw.PreferencesPage.__init__(self)

    @property
    def search_keywords(self):
        return [(_("Default Applications"), label) for label, _ in APP_MIME_TYPES] + [
            (_("Default Applications"), _("Image Viewer")),
            (_("Default Applications"), _("PDF Viewer")),
            (_("Default Applications"), _("Email Client")),
        ]

    def build(self):
        group = Adw.PreferencesGroup()
        group.set_title(_("Default Applications"))

        for label, mime_type in APP_MIME_TYPES:
            apps = self._get_apps_for_mime(mime_type)
            if not apps:
                continue
            desktop_ids = [did for did, _ in apps]
            display_names = [name for _, name in apps]

            row = Adw.ComboRow()
            row.set_title(label)
            row.set_model(Gtk.StringList.new(display_names))

            _loading = [True]
            current = self._get_default_app(mime_type)
            try:
                row.set_selected(desktop_ids.index(current))
            except ValueError:
                row.set_selected(0)
            _loading[0] = False

            if mime_type is None:
                # Terminal: write a wrapper desktop file so the choice takes effect
                row.connect(
                    "notify::selected",
                    lambda r, _, ids=desktop_ids, _l=_loading:
                        None if _l[0] else self._set_terminal_by_id(ids[r.get_selected()]),
                )
            else:
                row.connect(
                    "notify::selected",
                    lambda r, _, mt=mime_type, ids=desktop_ids, _l=_loading:
                        None if _l[0] else subprocess.run(
                            ["xdg-mime", "default", ids[r.get_selected()], mt],
                            check=False,
                        ),
                )

            group.add(row)

        self.add(group)
        return self

    @staticmethod
    def _set_terminal_by_id(desktop_id):
        app_info = Gio.DesktopAppInfo.new(desktop_id)
        if app_info:
            DefaultAppsPage._set_terminal(app_info)

    @staticmethod
    def _set_terminal(app_info):
        cmd = app_info.get_commandline() or app_info.get_executable() or ""
        name = app_info.get_display_name() or "Terminal"

        # Sanitize: .desktop format uses newlines as field separators
        # and = as key-value delimiter — strip both from values
        name = name.replace("\n", " ").replace("\r", " ")
        cmd = cmd.replace("\n", " ").replace("\r", " ")

        # Reject obviously invalid commands (empty or containing shell operators)
        if not cmd or not cmd.split()[0].replace("/", "").replace("-", "").replace("_", "").isalnum():
            return

        desktop_dir = Path.home() / ".local/share/applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        dest = desktop_dir / "terminal.desktop"
        tmp = dest.with_suffix(".desktop.tmp")
        tmp.write_text(
            f"[Desktop Entry]\nName={name}\nExec={cmd}\nType=Application\nTerminal=false\nCategories=TerminalEmulator;\n"
        )
        tmp.rename(dest)

    @staticmethod
    def _get_apps_for_mime(mime_type):
        if mime_type is None:
            apps, seen = [], set()
            for app in Gio.AppInfo.get_all():
                did = app.get_id()
                if not did or did in seen:
                    continue
                cats = app.get_categories() or ""
                if "TerminalEmulator" in cats:
                    seen.add(did)
                    apps.append((did, app.get_display_name()))
            return apps
        seen, apps = set(), []
        for app in Gio.AppInfo.get_all_for_type(mime_type):
            did = app.get_id()
            if not did or did in seen:
                continue
            seen.add(did)
            apps.append((did, app.get_display_name()))
        return apps

    @staticmethod
    def _get_default_app(mime_type):
        if mime_type is None:
            return ""
        try:
            return subprocess.run(["xdg-mime", "query", "default", mime_type],
                                  capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            return ""
