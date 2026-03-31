from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

import gi

gi.require_version("NM", "1.0")
from gi.repository import Gio, GLib, NM

from .events import EventBus


# ---------------------------------------------------------------------------
#  Data types
# ---------------------------------------------------------------------------

@dataclass
class AccessPointInfo:
    path: str
    ssid: str
    strength: int
    secured: bool
    active: bool


@dataclass
class ConnectionInfo:
    name: str
    type: str
    ip_address: str
    gateway: str
    dns: str


@dataclass
class BluetoothDevice:
    path: str
    name: str
    paired: bool
    connected: bool
    icon: str
    address: str


# ---------------------------------------------------------------------------
#  NetworkManager helper
# ---------------------------------------------------------------------------

class NetworkManagerHelper:
    """Wraps NM.Client. Publishes events: nm-ready, network-changed,
    network-connect-success, network-connect-error."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._client: NM.Client | None = None
        self._wifi_device: NM.DeviceWifi | None = None
        NM.Client.new_async(None, self._on_client_ready)

    def _on_client_ready(self, _source: object, result: Gio.AsyncResult) -> None:
        try:
            self._client = NM.Client.new_finish(result)
        except Exception:
            self._publish("nm-unavailable")
            return
        for dev in self._client.get_devices():
            if isinstance(dev, NM.DeviceWifi):
                self._wifi_device = dev
                break
        self._client.connect("notify::wireless-enabled", lambda *_: self._publish("network-changed"))
        if self._wifi_device is not None:
            self._wifi_device.connect("access-point-added", lambda *_: self._publish("network-changed"))
            self._wifi_device.connect("access-point-removed", lambda *_: self._publish("network-changed"))
        self._client.connect("active-connection-added", lambda *_: self._publish("network-changed"))
        self._client.connect("active-connection-removed", lambda *_: self._publish("network-changed"))
        self._publish("nm-ready")

    def _publish(self, event: str, data=None) -> None:
        self._event_bus.publish(event, data)

    # -- Queries --

    @property
    def ready(self) -> bool:
        return self._client is not None

    def is_wifi_enabled(self) -> bool:
        return self._client.wireless_get_enabled() if self._client else False

    def set_wifi_enabled(self, enabled: bool) -> None:
        if self._client:
            self._client.wireless_set_enabled(enabled)

    def get_access_points(self) -> list[AccessPointInfo]:
        if self._wifi_device is None:
            return []
        aps = self._wifi_device.get_access_points()
        seen: dict[str, NM.AccessPoint] = {}
        for ap in aps:
            ssid_bytes = ap.get_ssid()
            if ssid_bytes is None:
                continue
            ssid = ssid_bytes.get_data().decode("utf-8", errors="replace")
            if not ssid:
                continue
            if ssid not in seen or ap.get_strength() > seen[ssid].get_strength():
                seen[ssid] = ap
        active_ssid = self._get_active_wifi_ssid()
        result: list[AccessPointInfo] = []
        for ssid, ap in sorted(seen.items(), key=lambda x: -x[1].get_strength()):
            flags = ap.get_wpa_flags() | ap.get_rsn_flags()
            result.append(AccessPointInfo(
                path=ap.get_path(),
                ssid=ssid,
                strength=ap.get_strength(),
                secured=flags != 0,
                active=ssid == active_ssid,
            ))
        return result

    def request_scan(self) -> None:
        if self._wifi_device is not None:
            self._wifi_device.request_scan_async(None, self._on_scan_done)

    def _on_scan_done(self, device: NM.DeviceWifi, result: Gio.AsyncResult) -> None:
        try:
            device.request_scan_finish(result)
        except Exception:
            pass
        self._publish("network-changed")

    def get_active_connection_info(self) -> ConnectionInfo | None:
        if self._client is None:
            return None
        for ac in self._client.get_active_connections():
            ip4 = ac.get_ip4_config()
            if ip4 is None:
                continue
            addresses = ip4.get_addresses()
            nameservers = ip4.get_nameservers()
            return ConnectionInfo(
                name=ac.get_id(),
                type=ac.get_connection_type(),
                ip_address=addresses[0].get_address() if addresses else "N/A",
                gateway=ip4.get_gateway() or "N/A",
                dns=", ".join(str(ns) for ns in nameservers) if nameservers else "N/A",
            )
        return None

    def has_wired(self) -> bool:
        if self._client is None:
            return False
        return any(isinstance(d, NM.DeviceEthernet) for d in self._client.get_devices())

    def is_wired_connected(self) -> bool:
        if self._client is None:
            return False
        return any(
            ac.get_connection_type() == "802-3-ethernet"
            for ac in self._client.get_active_connections()
        )

    # -- Actions --

    def connect_wifi(self, ssid: str, password: str | None, hidden: bool = False) -> None:
        if self._client is None or self._wifi_device is None:
            return
        # Reuse existing saved connection when no new password is being supplied.
        if not password and not hidden:
            existing = self._find_connection_by_ssid(ssid)
            if existing is not None:
                self._client.activate_connection_async(
                    existing, self._wifi_device, None, None, self._on_activate_done,
                )
                return
        conn = NM.SimpleConnection.new()
        s_con = NM.SettingConnection.new()
        s_con.set_property("type", "802-11-wireless")
        s_con.set_property("id", ssid)
        conn.add_setting(s_con)
        s_wifi = NM.SettingWireless.new()
        s_wifi.set_property("ssid", GLib.Bytes.new(ssid.encode("utf-8")))
        if hidden:
            s_wifi.set_property("hidden", True)
        conn.add_setting(s_wifi)
        if password:
            s_sec = NM.SettingWirelessSecurity.new()
            s_sec.set_property("key-mgmt", "wpa-psk")
            s_sec.set_property("psk", password)
            conn.add_setting(s_sec)
        self._client.add_and_activate_connection_async(
            conn, self._wifi_device, None, None, self._on_connect_done,
        )

    def _on_connect_done(self, client: NM.Client, result: Gio.AsyncResult) -> None:
        try:
            client.add_and_activate_connection_finish(result)
            self._publish("network-connect-success")
        except Exception as exc:
            err = str(exc)
            if "802-11-wireless-security.psk" in err:
                self._publish("network-connect-error", "Wrong password.")
            else:
                self._publish("network-connect-error", f"Connection failed: {err}")

    def _on_activate_done(self, client: NM.Client, result: Gio.AsyncResult) -> None:
        try:
            client.activate_connection_finish(result)
            self._publish("network-connect-success")
        except Exception as exc:
            err = str(exc)
            if "802-11-wireless-security.psk" in err:
                self._publish("network-connect-error", "Wrong password.")
            else:
                self._publish("network-connect-error", f"Connection failed: {err}")

    def disconnect_wifi(self) -> None:
        if self._client is None:
            return
        for ac in self._client.get_active_connections():
            if ac.get_connection_type() == "802-11-wireless":
                self._client.deactivate_connection_async(ac, None, None)
                break

    def forget_connection(self, ssid: str) -> None:
        if self._client is None:
            return
        for conn in self._client.get_connections():
            s_con = conn.get_setting_connection()
            if s_con and s_con.get_id() == ssid:
                conn.delete_async(None, None)
                break

    def _find_connection_by_ssid(self, ssid: str) -> "NM.RemoteConnection | None":
        if self._client is None:
            return None
        ssid_bytes = ssid.encode("utf-8")
        for conn in self._client.get_connections():
            s_wifi = conn.get_setting_wireless()
            if s_wifi is None:
                continue
            stored = s_wifi.get_ssid()
            if stored is not None and stored.get_data() == ssid_bytes:
                return conn
        return None

    def _get_active_wifi_ssid(self) -> str | None:
        if self._client is None:
            return None
        for ac in self._client.get_active_connections():
            if ac.get_connection_type() == "802-11-wireless":
                return ac.get_id()
        return None


# ---------------------------------------------------------------------------
#  BlueZ helper
# ---------------------------------------------------------------------------

class BlueZHelper:
    """Wraps BlueZ D-Bus API via Gio.DBusProxy. Publishes event: bluetooth-changed."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._bus: Gio.DBusConnection | None = None
        self._adapter_path: str | None = None
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
        except GLib.Error:
            return
        self._find_adapter()
        self._subscribe_signals()

    def _find_adapter(self) -> None:
        try:
            result = self._bus.call_sync(
                "org.bluez", "/",
                "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
                None, GLib.VariantType("(a{oa{sa{sv}}})"),
                Gio.DBusCallFlags.NONE, -1, None,
            )
            objects = result.unpack()[0]
            for path, interfaces in objects.items():
                if "org.bluez.Adapter1" in interfaces:
                    self._adapter_path = path
                    break
        except GLib.Error:
            pass

    @property
    def available(self) -> bool:
        return self._adapter_path is not None

    def is_powered(self) -> bool:
        if not self.available:
            return False
        try:
            result = self._bus.call_sync(
                "org.bluez", self._adapter_path,
                "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", ("org.bluez.Adapter1", "Powered")),
                GLib.VariantType("(v)"),
                Gio.DBusCallFlags.NONE, -1, None,
            )
            return result.unpack()[0]
        except GLib.Error:
            return False

    def set_powered(self, enabled: bool) -> None:
        if not self.available:
            return
        try:
            self._bus.call_sync(
                "org.bluez", self._adapter_path,
                "org.freedesktop.DBus.Properties", "Set",
                GLib.Variant("(ssv)", ("org.bluez.Adapter1", "Powered", GLib.Variant("b", enabled))),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass

    def get_devices(self) -> list[BluetoothDevice]:
        if self._bus is None:
            return []
        try:
            result = self._bus.call_sync(
                "org.bluez", "/",
                "org.freedesktop.DBus.ObjectManager", "GetManagedObjects",
                None, GLib.VariantType("(a{oa{sa{sv}}})"),
                Gio.DBusCallFlags.NONE, -1, None,
            )
            objects = result.unpack()[0]
        except GLib.Error:
            return []
        devices: list[BluetoothDevice] = []
        for path, interfaces in objects.items():
            if "org.bluez.Device1" not in interfaces:
                continue
            props = interfaces["org.bluez.Device1"]
            devices.append(BluetoothDevice(
                path=path,
                name=props.get("Name", props.get("Alias", props.get("Address", "Unknown"))),
                paired=props.get("Paired", False),
                connected=props.get("Connected", False),
                icon=props.get("Icon", "bluetooth-symbolic"),
                address=props.get("Address", ""),
            ))
        return devices

    def start_discovery(self) -> None:
        if not self.available:
            return
        try:
            self._bus.call_sync(
                "org.bluez", self._adapter_path,
                "org.bluez.Adapter1", "StartDiscovery",
                None, None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass

    def stop_discovery(self) -> None:
        if not self.available:
            return
        try:
            self._bus.call_sync(
                "org.bluez", self._adapter_path,
                "org.bluez.Adapter1", "StopDiscovery",
                None, None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass

    def pair_device(self, device_path: str) -> None:
        if self._bus is None:
            return
        self._bus.call(
            "org.bluez", device_path,
            "org.bluez.Device1", "Pair",
            None, None, Gio.DBusCallFlags.NONE, 60000, None,
            self._on_pair_done,
        )

    def _on_pair_done(self, bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
        try:
            bus.call_finish(result)
            self._event_bus.publish("bluetooth-pair-success")
        except GLib.Error as e:
            self._event_bus.publish("bluetooth-pair-error", str(e))

    def connect_device(self, device_path: str) -> None:
        if self._bus is None:
            return
        self._bus.call(
            "org.bluez", device_path,
            "org.bluez.Device1", "Connect",
            None, None, Gio.DBusCallFlags.NONE, 30000, None,
            self._on_generic_done,
        )

    def disconnect_device(self, device_path: str) -> None:
        if self._bus is None:
            return
        try:
            self._bus.call_sync(
                "org.bluez", device_path,
                "org.bluez.Device1", "Disconnect",
                None, None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass
        self._event_bus.publish("bluetooth-changed")

    def remove_device(self, device_path: str) -> None:
        if not self.available:
            return
        try:
            self._bus.call_sync(
                "org.bluez", self._adapter_path,
                "org.bluez.Adapter1", "RemoveDevice",
                GLib.Variant("(o)", (device_path,)),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass
        self._event_bus.publish("bluetooth-changed")

    def _on_generic_done(self, bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
        try:
            bus.call_finish(result)
        except GLib.Error:
            pass
        self._event_bus.publish("bluetooth-changed")

    def _subscribe_signals(self) -> None:
        if self._bus is None:
            return
        self._bus.signal_subscribe(
            "org.bluez", "org.freedesktop.DBus.ObjectManager",
            "InterfacesAdded", "/", None,
            Gio.DBusSignalFlags.NONE, self._on_changed, None,
        )
        self._bus.signal_subscribe(
            "org.bluez", "org.freedesktop.DBus.ObjectManager",
            "InterfacesRemoved", "/", None,
            Gio.DBusSignalFlags.NONE, self._on_changed, None,
        )
        self._bus.signal_subscribe(
            "org.bluez", "org.freedesktop.DBus.Properties",
            "PropertiesChanged", None, None,
            Gio.DBusSignalFlags.NONE, self._on_props_changed, None,
        )

    def _on_changed(self, *_args) -> None:
        self._event_bus.publish("bluetooth-changed")

    def _on_props_changed(self, _conn, _sender, _path, _iface, _signal, params, _data) -> None:
        iface_name = params.unpack()[0]
        if iface_name in ("org.bluez.Adapter1", "org.bluez.Device1"):
            self._event_bus.publish("bluetooth-changed")


# ---------------------------------------------------------------------------
#  power-profiles-daemon helper
# ---------------------------------------------------------------------------

class PowerProfilesHelper:
    """Wraps net.hadess.PowerProfiles D-Bus. Publishes event: power-profile-changed."""

    BUS_NAME = "net.hadess.PowerProfiles"
    OBJECT_PATH = "/net/hadess/PowerProfiles"
    IFACE = "net.hadess.PowerProfiles"

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._bus: Gio.DBusConnection | None = None
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)
        except GLib.Error:
            return
        self._bus.signal_subscribe(
            self.BUS_NAME, "org.freedesktop.DBus.Properties",
            "PropertiesChanged", self.OBJECT_PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_props_changed, None,
        )

    @property
    def available(self) -> bool:
        return self._bus is not None

    def get_active_profile(self) -> str:
        if self._bus is None:
            return "balanced"
        try:
            result = self._bus.call_sync(
                self.BUS_NAME, self.OBJECT_PATH,
                "org.freedesktop.DBus.Properties", "Get",
                GLib.Variant("(ss)", (self.IFACE, "ActiveProfile")),
                GLib.VariantType("(v)"),
                Gio.DBusCallFlags.NONE, -1, None,
            )
            return result.unpack()[0]
        except GLib.Error:
            return "balanced"

    def set_active_profile(self, profile: str) -> None:
        if self._bus is None:
            return
        try:
            self._bus.call_sync(
                self.BUS_NAME, self.OBJECT_PATH,
                "org.freedesktop.DBus.Properties", "Set",
                GLib.Variant("(ssv)", (self.IFACE, "ActiveProfile", GLib.Variant("s", profile))),
                None, Gio.DBusCallFlags.NONE, -1, None,
            )
        except GLib.Error:
            pass

    def _on_props_changed(self, _conn, _sender, _path, _iface, _signal, params, _data) -> None:
        changed = params.unpack()[1]
        if "ActiveProfile" in changed:
            self._event_bus.publish("power-profile-changed", changed["ActiveProfile"])


# ---------------------------------------------------------------------------
#  PulseAudio event subscriber
# ---------------------------------------------------------------------------

class PulseAudioSubscriber:
    """Runs `pactl subscribe` in background thread, publishes audio-changed events.
    Automatically reconnects if the audio server restarts."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._proc: subprocess.Popen | None = None
        self._stopped = False
        self._start()

    def _start(self) -> None:
        import shutil
        import threading
        import time

        if shutil.which("pactl") is None:
            return

        def _reader():
            while not self._stopped:
                try:
                    self._proc = subprocess.Popen(
                        ["pactl", "subscribe"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    for line in self._proc.stdout:
                        if self._stopped:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        if any(kw in line for kw in ("sink", "source", "server")):
                            self._event_bus.publish("audio-changed")
                except Exception:
                    pass
                if not self._stopped:
                    time.sleep(2)

        threading.Thread(target=_reader, daemon=True).start()

    def stop(self) -> None:
        self._stopped = True
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.stdout.close()
            except Exception:
                pass
            self._proc = None
