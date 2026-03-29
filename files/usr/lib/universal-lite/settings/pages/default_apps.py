import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from ..base import BasePage

APP_MIME_TYPES = [
    ("Web Browser", "x-scheme-handler/http"),
    ("File Manager", "inode/directory"),
    ("Terminal", None),
    ("Text Editor", "text/plain"),
    ("Media Player", "video/x-matroska"),
]


class DefaultAppsPage(BasePage):
    @property
    def search_keywords(self):
        return [("Default Applications", label) for label, _ in APP_MIME_TYPES]

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
            if mime_type:
                dropdown.connect("notify::selected", lambda d, _, mt=mime_type, ids=desktop_ids:
                    subprocess.run(["xdg-mime", "default", ids[d.get_selected()], mt], check=False))
            page.append(self.make_setting_row(label, "", dropdown))
        return page

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
