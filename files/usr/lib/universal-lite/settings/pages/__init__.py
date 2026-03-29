from .about import AboutPage
from .appearance import AppearancePage
from .bluetooth import BluetoothPage
from .default_apps import DefaultAppsPage
from .display import DisplayPage
from .keyboard import KeyboardPage
from .mouse_touchpad import MouseTouchpadPage
from .network import NetworkPage
from .panel import PanelPage
from .power_lock import PowerLockPage
from .sound import SoundPage

ALL_PAGES = [
    ("display-brightness-symbolic", "Appearance", AppearancePage),
    ("video-display-symbolic", "Display", DisplayPage),
    ("network-wireless-symbolic", "Network", NetworkPage),
    ("bluetooth-symbolic", "Bluetooth", BluetoothPage),
    ("view-app-grid-symbolic", "Panel", PanelPage),
    ("input-mouse-symbolic", "Mouse & Touchpad", MouseTouchpadPage),
    ("input-keyboard-symbolic", "Keyboard", KeyboardPage),
    ("audio-volume-high-symbolic", "Sound", SoundPage),
    ("system-shutdown-symbolic", "Power & Lock", PowerLockPage),
    ("application-x-executable-symbolic", "Default Apps", DefaultAppsPage),
    ("help-about-symbolic", "About", AboutPage),
]
