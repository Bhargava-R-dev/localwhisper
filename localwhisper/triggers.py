"""Global hotkeys -> events on a shared queue. Runs on the keyboard lib's thread."""
import queue
from enum import Enum, auto
import keyboard


class Event(Enum):
    HOLD_START = auto()   # Ctrl+B pressed: begin walkie-talkie recording
    TOGGLE = auto()       # Alt+N tapped: start or stop toggle recording


class HotkeyListener:
    """Hold-release is tracked by EVENTS, not polling.

    Polling ``keyboard.is_pressed('ctrl+b')`` proved unreliable: it falsely reported the
    combo as released mid-hold (observed at ~21 s), cutting recordings off. Instead we set
    a flag on the hotkey press and clear it on the actual key-up of the trigger key. Key
    auto-repeat sends repeated key-DOWNs but never a key-up, so the flag stays true for the
    entire hold and flips exactly once, when the finger actually lifts.
    """

    def __init__(self, config, event_queue: "queue.Queue[Event]"):
        self.hold_hotkey = config.hold_hotkey
        self.toggle_hotkey = config.toggle_hotkey
        self.events = event_queue
        self._handles = []
        self._release_hook = None
        self._hold_down = False
        # trigger (last) key of the hold combo, e.g. "b" in "ctrl+b"
        self._trigger_key = self.hold_hotkey.split("+")[-1].strip()

    def start(self):
        self._handles.append(
            keyboard.add_hotkey(
                self.hold_hotkey, self._on_hold_start, trigger_on_release=False
            )
        )
        self._handles.append(
            keyboard.add_hotkey(
                self.toggle_hotkey, lambda: self.events.put(Event.TOGGLE)
            )
        )
        # Fires on the real key-up of the trigger key (never during auto-repeat).
        self._release_hook = keyboard.on_release_key(self._trigger_key, self._on_hold_release)

    def _on_hold_start(self):
        self._hold_down = True
        self.events.put(Event.HOLD_START)

    def _on_hold_release(self, _event):
        self._hold_down = False

    def hold_key_is_down(self) -> bool:
        """True from the hold-hotkey press until the trigger key is physically released."""
        return self._hold_down

    def stop(self):
        for h in self._handles:
            try:
                keyboard.remove_hotkey(h)
            except (KeyError, ValueError):
                pass
        self._handles.clear()
        if self._release_hook is not None:
            try:
                keyboard.unhook(self._release_hook)
            except (KeyError, ValueError):
                pass
            self._release_hook = None
