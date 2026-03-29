from .about import AboutPage
from .accessibility import AccessibilityPage
from .appearance import AppearancePage
from .bluetooth import BluetoothPage
from .datetime import DateTimePage
from .default_apps import DefaultAppsPage
from .display import DisplayPage
from .keyboard import KeyboardPage
from .language import LanguagePage
from .mouse_touchpad import MouseTouchpadPage
from .network import NetworkPage
from .panel import PanelPage
from .power_lock import PowerLockPage
from .sound import SoundPage
from .users import UsersPage

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
    ("preferences-desktop-accessibility-symbolic", "Accessibility", AccessibilityPage),
    ("preferences-system-time-symbolic", "Date & Time", DateTimePage),
    ("system-users-symbolic", "Users", UsersPage),
    ("preferences-desktop-locale-symbolic", "Language & Region", LanguagePage),
    ("application-x-executable-symbolic", "Default Apps", DefaultAppsPage),
    ("help-about-symbolic", "About", AboutPage),
]
