"""Global hotkeys -> events on a shared queue. Runs on the keyboard lib's thread."""
import queue
from enum import Enum, auto
import keyboard


class Event(Enum):
    HOLD_START = auto()   # Ctrl+B pressed: begin walkie-talkie recording
    TOGGLE = auto()       # Alt+N tapped: start or stop toggle recording


class HotkeyListener:
    """Global hotkeys with two Windows-specific behaviours the naive version got wrong.

    **Trigger-key suppression + release detection in ONE hook.** The trigger of the hold
    combo is a printable letter, so its auto-repeat would type ``bbbb...`` into the focused
    app during a hold. A previous attempt used ``block_key`` for suppression and a separate
    ``on_release_key`` for the release — but the keyboard library drops a blocked event
    *before* the non-blocking release hook ever runs, so the release was never seen and the
    hold ran to the 2-minute cap. The fix is a single ``suppress=True`` hook whose callback
    is guaranteed to run for every event of that key: it detects the key-up (release) AND
    decides whether to block the key. It blocks the key only while a hold is active, so
    normal typing of that letter is unaffected.
    """

    def __init__(self, config, event_queue: "queue.Queue[Event]"):
        self.hold_hotkey = config.hold_hotkey
        self.toggle_hotkey = config.toggle_hotkey
        self.events = event_queue
        self._handles = []
        self._trigger_hook = None
        self._hold_down = False
        self._trigger_key = self.hold_hotkey.split("+")[-1].strip()   # "b" in "ctrl+b"

    def start(self):
        self._handles.append(
            keyboard.add_hotkey(self.hold_hotkey, self._on_hold_start, trigger_on_release=False)
        )
        self._handles.append(
            keyboard.add_hotkey(self.toggle_hotkey, lambda: self.events.put(Event.TOGGLE))
        )
        # Suppressing hook: its callback runs for EVERY event of the trigger key, so it both
        # blocks auto-repeat during a hold and reliably detects the key-up (release).
        self._trigger_hook = keyboard.hook_key(
            self._trigger_key, self._on_trigger_event, suppress=True
        )

    def _on_hold_start(self):
        self._hold_down = True
        self.events.put(Event.HOLD_START)

    def _on_trigger_event(self, event):
        """Return True to let the key through, False to block it. Runs for down AND up."""
        if event.event_type == keyboard.KEY_UP:
            self._hold_down = False          # release detected -> recording will stop
        return not self._hold_down           # block the trigger key only while a hold is active

    def hold_key_is_down(self) -> bool:
        """True from the hold-hotkey press until the trigger key is physically released."""
        return self._hold_down

    def release_hold(self):
        """Force the hold flag off (idempotent). Called by the app after each recording."""
        self._hold_down = False

    def stop(self):
        self.release_hold()
        for h in self._handles:
            try:
                keyboard.remove_hotkey(h)
            except (KeyError, ValueError):
                pass
        self._handles.clear()
        if self._trigger_hook is not None:
            try:
                keyboard.unhook(self._trigger_hook)
            except (KeyError, ValueError):
                pass
            self._trigger_hook = None
