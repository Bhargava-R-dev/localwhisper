"""Global hotkeys -> events on a shared queue. Runs on the keyboard lib's thread."""
import queue
from enum import Enum, auto
import keyboard


class Event(Enum):
    HOLD_START = auto()   # Ctrl+B pressed: begin walkie-talkie recording
    TOGGLE = auto()       # Alt+N tapped: start or stop toggle recording


class HotkeyListener:
    """Global hotkeys with two Windows-specific behaviours the naive version got wrong:

    1. **Event-driven release.** Polling ``is_pressed('ctrl+b')`` falsely reported the combo
       as released mid-hold (~21 s), cutting recordings off. We instead flip a flag on the
       hotkey press and clear it on the trigger key's actual key-up (auto-repeat never fakes
       a key-up), so a hold lasts exactly until the finger lifts.

    2. **Trigger-key suppression.** Because the trigger is a printable letter, its auto-repeat
       would type ``bbbb...`` into the focused app during a hold. While a hold is active we
       ``block_key`` the trigger so it never reaches other programs — our own hooks still see
       it, so release detection keeps working. The block is always lifted: on release, via the
       app after each recording, and on shutdown.
    """

    def __init__(self, config, event_queue: "queue.Queue[Event]"):
        self.hold_hotkey = config.hold_hotkey
        self.toggle_hotkey = config.toggle_hotkey
        self.events = event_queue
        self._handles = []
        self._release_hook = None
        self._block_handle = None
        self._hold_down = False
        self._trigger_key = self.hold_hotkey.split("+")[-1].strip()   # "b" in "ctrl+b"

    def start(self):
        self._handles.append(
            keyboard.add_hotkey(self.hold_hotkey, self._on_hold_start, trigger_on_release=False)
        )
        self._handles.append(
            keyboard.add_hotkey(self.toggle_hotkey, lambda: self.events.put(Event.TOGGLE))
        )
        self._release_hook = keyboard.on_release_key(self._trigger_key, self._on_hold_release)

    def _on_hold_start(self):
        if self._hold_down:
            return
        self._hold_down = True
        # Suppress the trigger key so its auto-repeat can't type into the focused app.
        try:
            self._block_handle = keyboard.block_key(self._trigger_key)
        except Exception:
            self._block_handle = None
        self.events.put(Event.HOLD_START)

    def _on_hold_release(self, _event):
        self.release_hold()

    def hold_key_is_down(self) -> bool:
        """True from the hold-hotkey press until the trigger key is physically released."""
        return self._hold_down

    def release_hold(self):
        """Clear the hold flag and unblock the trigger key. Idempotent; safe from any thread.

        Called on the real key-up AND by the app after each hold recording, so the trigger key
        can never stay blocked even if a key-up event is ever missed.
        """
        self._hold_down = False
        if self._block_handle is not None:
            try:
                keyboard.unhook(self._block_handle)
            except (KeyError, ValueError):
                pass
            self._block_handle = None

    def stop(self):
        self.release_hold()
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
