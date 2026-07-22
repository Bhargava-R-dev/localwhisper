"""Siri-style on-screen 'listening' indicator.

A small, borderless, always-on-top pill near the bottom of the screen with animated
bars. It runs its own Tk event loop on a daemon thread; call listening()/busy()/hide()
from any thread. It is click-through and never activates, so the app you're dictating
into keeps focus (otherwise the pasted text would land in the wrong place).

If Tk or the Windows styling calls are unavailable, the overlay silently disables
itself — it is a nice-to-have and must never break the core app.
"""
import math
import threading


class Overlay:
    W, H = 240, 68
    _COLORS = {"listening": "#38bdf8", "busy": "#f59e0b"}   # cyan / amber
    _KEY = "#010203"     # near-black transparent color key (rounds the corners)
    _PILL = "#15181f"    # pill background

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._state = "hidden"        # "hidden" | "listening" | "busy"
        self._lock = threading.Lock()
        self._thread = None

    # ---- public, thread-safe ----
    def start(self):
        if not self.enabled:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def set_state(self, state: str):
        with self._lock:
            self._state = state

    def listening(self):
        self.set_state("listening")

    def busy(self):
        self.set_state("busy")

    def hide(self):
        self.set_state("hidden")

    # ---- Tk thread ----
    def _run(self):
        try:
            import tkinter as tk
        except Exception:
            return
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            try:
                root.attributes("-transparentcolor", self._KEY)   # rounded corners via color key
            except Exception:
                pass
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            x = (sw - self.W) // 2
            y = sh - self.H - 90
            root.geometry(f"{self.W}x{self.H}+{x}+{y}")
            root.configure(bg=self._KEY)
            canvas = tk.Canvas(root, width=self.W, height=self.H, bg=self._KEY,
                               highlightthickness=0)
            canvas.pack()
            self._make_click_through(root)
        except Exception:
            return

        phase = {"t": 0.0}

        def draw_pill():
            r = self.H // 2
            # rounded rectangle = two circles + a center rectangle
            canvas.create_oval(0, 0, 2 * r, self.H, fill=self._PILL, outline=self._PILL)
            canvas.create_oval(self.W - 2 * r, 0, self.W, self.H, fill=self._PILL, outline=self._PILL)
            canvas.create_rectangle(r, 0, self.W - r, self.H, fill=self._PILL, outline=self._PILL)

        def tick():
            with self._lock:
                st = self._state
            if st == "hidden":
                root.withdraw()
            else:
                root.deiconify()
                canvas.delete("all")
                draw_pill()
                color = self._COLORS.get(st, "#38bdf8")
                # five animated bars, sine-driven with phase offsets
                n = 5
                cx0 = 34
                gap = 15
                base_y = self.H / 2
                for i in range(n):
                    amp = 10 + 12 * (0.5 + 0.5 * math.sin(phase["t"] + i * 0.7))
                    bx = cx0 + i * gap
                    canvas.create_rectangle(bx - 3, base_y - amp, bx + 3, base_y + amp,
                                            fill=color, outline=color)
                label = "Listening" if st == "listening" else "Working"
                canvas.create_text(self.W - 74, base_y, text=label, fill="#e8eaed",
                                   font=("Segoe UI", 11, "bold"), anchor="center")
                phase["t"] += 0.35
            root.after(45, tick)

        root.after(45, tick)
        try:
            root.mainloop()
        except Exception:
            pass

    @staticmethod
    def _make_click_through(root):
        """Apply layered + transparent + no-activate + tool-window extended styles."""
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020    # mouse clicks pass through
        WS_EX_NOACTIVATE = 0x08000000     # never take focus
        WS_EX_TOOLWINDOW = 0x00000080     # hide from taskbar / Alt-Tab
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
