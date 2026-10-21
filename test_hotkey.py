"""
Quick standalone test — confirms pynput global hotkey works across all apps.
Run this, switch to your browser, then press the HOME key (Fn+Home on ASUS).
You should see a message printed in this terminal instantly.
Press Ctrl+C here in the terminal to quit.
"""
from pynput import keyboard
import time

print("=== Jarvis Hotkey Test ===")
print("Press HOME / Fn+Home from ANY app (browser, explorer, etc.)")
print("You should see 'HOTKEY FIRED!' appear here.")
print("Press Ctrl+C in this terminal to stop.\n")

count = [0]

def on_activate():
    count[0] += 1
    print(f"✅ HOTKEY FIRED! (count={count[0]}) — Jarvis would wake up now.")

with keyboard.GlobalHotKeys({"<home>": on_activate}) as h:
    try:
        h.join()
    except KeyboardInterrupt:
        print("\nTest stopped.")
