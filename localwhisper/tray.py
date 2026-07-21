"""System-tray state indicator + short audible cues (winsound is stdlib on Windows)."""
import threading
import winsound
import pystray
from PIL import Image


_COLORS = {
    "idle": (90, 90, 90),        # grey
    "listening": (40, 160, 40),  # green (recording)
    "busy": (200, 140, 0),       # amber (transcribing)
}


def _icon_image(color):
    img = Image.new("RGB", (64, 64), color)
    return img


class TrayIcon:
    def __init__(self, on_quit, enable_beep=True):
        self.enable_beep = enable_beep
        self._icon = pystray.Icon(
            "LocalWhisper",
            _icon_image(_COLORS["idle"]),
            "LocalWhisper (idle)",
            menu=pystray.Menu(pystray.MenuItem("Quit", lambda: on_quit())),
        )

    def start(self):
        threading.Thread(target=self._icon.run, daemon=True).start()

    def set_state(self, state: str):
        self._icon.icon = _icon_image(_COLORS.get(state, _COLORS["idle"]))
        self._icon.title = f"LocalWhisper ({state})"

    def beep_start(self):
        if self.enable_beep:
            winsound.Beep(880, 120)

    def beep_stop(self):
        if self.enable_beep:
            winsound.Beep(440, 120)

    def stop(self):
        self._icon.stop()
