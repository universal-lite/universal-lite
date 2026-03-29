import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from ..base import BasePage

APP_MIME_TYPES = [
    ("Web Browser", "x-scheme-handler/http"),
    ("File Manager", "inode/directory"),
    ("Terminal", None),
    ("Text Editor", "text/plain"),
    ("Image Viewer", "image/png"),
    ("PDF Viewer", "application/pdf"),
    ("Media Player", "video/x-matroska"),
    ("Email Client", "x-scheme-handler/mailto"),
]


class DefaultAppsPage(BasePage):
    @property
    def search_keywords(self):
        return [("Default Applications", label) for label, _ in APP_MIME_TYPES] + [
            ("Default Applications", "Image Viewer"),
            ("Default Applications", "PDF Viewer"),
            ("Default Applications", "Email Client"),
        ]

    def build(self):
        page = self.make_page_box()
        page.append(self.make_group_label("Default Applications"))
        for label, mime_type in APP_MIME_TYPES:
            apps = self._get_apps_for_mime(mime_type)
            if not apps:
                continue
            desktop_ids = [did for did, _ in apps]
            display_names = [name for _, name in apps]
            dropdown = Gtk.DropDown.new_from_strings(display_names)
            current = self._get_default_app(mime_type)
            try:
                dropdown.set_selected(desktop_ids.index(current))
            except ValueError:
                dropdown.set_selected(0)
            if mime_type is None:
                # Terminal: write a wrapper desktop file so the choice takes effect
                dropdown.connect("notify::selected", lambda d, _, ids=desktop_ids:
                    self._set_terminal_by_id(ids[d.get_selected()]))
            else:
                dropdown.connect("notify::selected", lambda d, _, mt=mime_type, ids=desktop_ids:
                    subprocess.run(["xdg-mime", "default", ids[d.get_selected()], mt], check=False))
            page.append(self.make_setting_row(label, "", dropdown))
        return page

    @staticmethod
    def _set_terminal_by_id(desktop_id):
        app_info = Gio.DesktopAppInfo.new(desktop_id)
        if app_info:
            DefaultAppsPage._set_terminal(app_info)

    @staticmethod
    def _set_terminal(app_info):
        cmd = app_info.get_commandline() or app_info.get_executable() or ""
        name = app_info.get_display_name()
        desktop_dir = Path.home() / ".local/share/applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        (desktop_dir / "terminal.desktop").write_text(
            f"[Desktop Entry]\nName={name}\nExec={cmd}\nType=Application\nTerminal=false\nCategories=TerminalEmulator;\n"
        )

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
