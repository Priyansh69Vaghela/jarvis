"""
overlay.py — iOS-style status dot overlay for Jarvis.

Renders a small colored pill/dot in the top-right corner of the screen,
always on top, transparent background, zero taskbar presence, click-through.

States:
  - hidden    : dot invisible (Jarvis in silent standby)
  - listening : orange pulsing dot  (mic is active)
  - thinking  : cyan pulsing dot    (Groq + Gemini processing)
  - speaking  : green steady dot    (Edge-TTS audio playing)
"""

import threading
import tkinter as tk
import math
import time


# ──────────────────────────────────────────────────────────────
# Colour palette for each Jarvis state
# ──────────────────────────────────────────────────────────────
STATE_COLORS = {
    "hidden":    None,           # dot invisible
    "listening": "#FF9500",      # iOS orange  (mic active)
    "thinking":  "#00D4FF",      # cyan        (processing)
    "speaking":  "#34C759",      # iOS green   (TTS playing)
}

DOT_SIZE      = 18          # diameter of the dot in pixels
PADDING       = 10          # gap from screen edge
PULSE_SPEED   = 0.04        # seconds per animation frame
PULSE_RANGE   = (0.55, 1.0) # min/max opacity during pulse


class JarvisOverlay:
    """
    Runs an always-on-top transparent Tk window with an animated status dot.
    Must be used from the main thread (Tk requirement) via `.start()`.
    State changes from any thread via `.set_state(state)`.
    """

    def __init__(self):
        self._state      = "hidden"
        self._lock       = threading.Lock()
        self._pulse_tick = 0.0
        self._root       = None
        self._canvas     = None
        self._dot_id     = None
        self._running    = False

    # ── Public API (thread-safe) ───────────────────────────────
    def set_state(self, state: str):
        """Change the overlay state from any thread."""
        assert state in STATE_COLORS, f"Unknown state: {state}"
        with self._lock:
            self._state = state
            self._pulse_tick = 0.0      # reset pulse phase on state change

    def start(self):
        """Start the Tk mainloop in a daemon thread (called once at startup)."""
        t = threading.Thread(target=self._run, daemon=True, name="JarvisOverlay")
        t.start()

    def stop(self):
        """Gracefully destroy the Tk window."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    # ── Internal Tk loop ──────────────────────────────────────
    def _run(self):
        self._root = tk.Tk()
        root = self._root

        # ── Window chrome removal & always-on-top ─────────────
        root.overrideredirect(True)             # no title bar / borders
        root.attributes("-topmost", True)       # always above other windows
        root.attributes("-alpha", 1.0)          # we control per-pixel alpha via canvas
        root.configure(bg="black")
        root.attributes("-transparentcolor", "black")   # make background invisible (Windows)
        root.wm_attributes("-toolwindow", True)          # no taskbar entry

        # ── Size & position: top-right corner ─────────────────
        sw = root.winfo_screenwidth()
        size = DOT_SIZE + PADDING * 2

        root.geometry(f"{size}x{size}+{sw - size - 4}+{6}")
        root.resizable(False, False)

        # ── Canvas ────────────────────────────────────────────
        self._canvas = tk.Canvas(
            root,
            width=size, height=size,
            bg="black", highlightthickness=0
        )
        self._canvas.pack()

        # Draw the dot (initially invisible)
        margin = PADDING
        self._dot_id = self._canvas.create_oval(
            margin, margin,
            margin + DOT_SIZE, margin + DOT_SIZE,
            fill="", outline=""
        )

        self._running = True
        self._animate()
        root.mainloop()

    def _animate(self):
        """Called every PULSE_SPEED seconds to update the dot appearance."""
        if not self._running:
            return

        with self._lock:
            state = self._state
            tick  = self._pulse_tick
            self._pulse_tick += PULSE_SPEED

        color = STATE_COLORS[state]

        if color is None or state == "hidden":
            # Invisible
            self._canvas.itemconfig(self._dot_id, fill="", outline="")
        elif state == "speaking":
            # Steady glow — no pulse
            self._canvas.itemconfig(self._dot_id, fill=color, outline=color)
        else:
            # Smooth sine pulse between PULSE_RANGE opacities
            lo, hi = PULSE_RANGE
            alpha = lo + (hi - lo) * (0.5 + 0.5 * math.sin(tick * math.pi * 2))
            blended = self._blend(color, alpha)
            self._canvas.itemconfig(self._dot_id, fill=blended, outline=blended)

        # Schedule next frame (~25 fps)
        if self._root:
            self._root.after(int(PULSE_SPEED * 1000), self._animate)

    @staticmethod
    def _blend(hex_color: str, alpha: float) -> str:
        """
        Simulate alpha blending against black (#000000 background, which is
        transparent anyway — used to compute the perceived brightness).
        """
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = int(r * alpha)
        g = int(g * alpha)
        b = int(b * alpha)
        return f"#{r:02x}{g:02x}{b:02x}"
