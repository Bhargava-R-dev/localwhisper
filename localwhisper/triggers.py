"""Global hotkeys -> events on a shared queue. Runs on the keyboard lib's thread."""
import queue
from enum import Enum, auto
import keyboard


class Event(Enum):
    HOLD_START = auto()   # Ctrl+B pressed: begin walkie-talkie recording
    TOGGLE = auto()       # Alt+N tapped: start or stop toggle recording


class HotkeyListener:
    def __init__(self, config, event_queue: "queue.Queue[Event]"):
        self.hold_hotkey = config.hold_hotkey
        self.toggle_hotkey = config.toggle_hotkey
        self.events = event_queue
        self._handles = []

    def start(self):
        # Fire HOLD_START on key-down (not release) so we can record while held.
        self._handles.append(
            keyboard.add_hotkey(
                self.hold_hotkey,
                lambda: self.events.put(Event.HOLD_START),
                trigger_on_release=False,
            )
        )
        self._handles.append(
            keyboard.add_hotkey(
                self.toggle_hotkey,
                lambda: self.events.put(Event.TOGGLE),
            )
        )

    def hold_key_is_down(self) -> bool:
        """True while the hold combo is physically pressed (drives walkie-talkie stop)."""
        return keyboard.is_pressed(self.hold_hotkey)

    def stop(self):
        for h in self._handles:
            keyboard.remove_hotkey(h)
        self._handles.clear()
