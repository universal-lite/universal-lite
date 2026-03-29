from gi.repository import GLib


class EventBus:
    """Thread-safe publish/subscribe for system events. Callbacks run on the main GTK thread."""

    def __init__(self):
        self._subscribers: dict[str, list] = {}

    def subscribe(self, event: str, callback) -> None:
        self._subscribers.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback) -> None:
        if event in self._subscribers:
            self._subscribers[event] = [
                cb for cb in self._subscribers[event] if cb is not callback
            ]

    def publish(self, event: str, data=None) -> None:
        for cb in list(self._subscribers.get(event, [])):
            GLib.idle_add(cb, data)
