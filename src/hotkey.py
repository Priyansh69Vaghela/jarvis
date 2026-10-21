"""
hotkey.py — System-wide background hotkey listener for Jarvis.

Listens for a configurable key combination (default: Home / Fn+Home on ASUS
laptops) across ALL Windows applications without stealing focus, then fires a
callback that begins a Jarvis voice session.

Uses pynput's GlobalHotKeys so it works even when Jarvis's console window is
minimized or in the background.
"""

import threading
from typing import Callable
from pynput import keyboard


# Keys that need special pynput names rather than raw characters
_SPECIAL_KEY_MAP = {
    "home":        "<home>",
    "end":         "<end>",
    "insert":      "<insert>",
    "delete":      "<delete>",
    "page_up":     "<page_up>",
    "page_down":   "<page_down>",
    "f1":  "<f1>",  "f2":  "<f2>",  "f3":  "<f3>",  "f4":  "<f4>",
    "f5":  "<f5>",  "f6":  "<f6>",  "f7":  "<f7>",  "f8":  "<f8>",
    "f9":  "<f9>",  "f10": "<f10>", "f11": "<f11>", "f12": "<f12>",
    "ctrl":  "<ctrl>",
    "alt":   "<alt>",
    "shift": "<shift>",
}


def _parse_hotkey(hotkey_str: str) -> str:
    """
    Convert a human-readable hotkey string to pynput GlobalHotKeys format.

    Examples:
        "home"       ->  "<home>"
        "ctrl+home"  ->  "<ctrl>+<home>"
        "alt+j"      ->  "<alt>+j"
        "alt+home"   ->  "<alt>+<home>"
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    mapped = []
    for part in parts:
        if part in _SPECIAL_KEY_MAP:
            mapped.append(_SPECIAL_KEY_MAP[part])
        else:
            mapped.append(part)         # single character key, e.g. 'j'
    return "+".join(mapped)


class GlobalHotkeyManager:
    """
    Runs pynput's GlobalHotKeys listener in a daemon thread.

    Usage:
        def on_trigger():
            print("Jarvis activated!")

        mgr = GlobalHotkeyManager(hotkey_str="home", callback=on_trigger)
        mgr.start()
        # ... rest of your program ...
        mgr.stop()
    """

    def __init__(self, hotkey_str: str, callback: Callable[[], None]):
        self._hotkey_str  = hotkey_str
        self._callback    = callback
        self._listener    = None
        self._busy        = False               # state lock — no overlapping sessions
        self._busy_lock   = threading.Lock()

    def start(self):
        """Start the background hotkey listener thread."""
        pynput_hotkey = _parse_hotkey(self._hotkey_str)

        def _safe_callback():
            """Fires when the hotkey is detected; guards against overlapping calls."""
            with self._busy_lock:
                if self._busy:
                    return                      # Jarvis already active — ignore
                self._busy = True

            try:
                self._callback()
            finally:
                with self._busy_lock:
                    self._busy = False

        bindings = {pynput_hotkey: _safe_callback}

        self._listener = keyboard.GlobalHotKeys(bindings)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        """Stop the listener cleanly."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass

    @property
    def is_busy(self) -> bool:
        """True while a Jarvis session triggered by hotkey is in progress."""
        with self._busy_lock:
            return self._busy
