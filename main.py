import os
import re
import sys
import time
import socket
import concurrent.futures
import threading

# Set UTF-8 encoding for Windows terminal to support multilingual scripts (Gujarati, Hindi, etc.)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Prevent Windows IPv6 TCP timeout stalls
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.config import (
    GEMINI_API_KEY, GROQ_API_KEY, JARVIS_VOICE, ENV_PATH,
    JARVIS_HOTKEY, JARVIS_WAKE_SOUND, JARVIS_SILENCE_TIMEOUT,
)
from src.tts import speak
from src.stt import SpeechRecognizer
from src.brain import JarvisBrain
from src.hotkey import GlobalHotkeyManager
from src.overlay import JarvisOverlay

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_banner():
    console.print(
        Panel.fit(
            "[bold cyan]J.A.R.V.I.S. — Personal AI Assistant[/bold cyan]\n"
            "[dim]Phase 1: Stack-Pipelined Reasoning & Real-Time Voice Synthesis[/dim]\n"
            "[green]Status: Cloud-Powered (0% GPU Load) | Stack Concurrency: Active[/green]",
            border_style="cyan"
        )
    )


def check_environment():
    """Verify that required API keys are configured."""
    missing = []
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        missing.append("GEMINI_API_KEY (Get free at https://aistudio.google.com/)")
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        missing.append("GROQ_API_KEY (Get free at https://console.groq.com/)")

    if missing:
        console.print(Panel(
            "[bold yellow]⚠️ Configuration Required[/bold yellow]\n\n"
            "Please add your free API keys to your [bold green].env[/bold green] file:\n" +
            "\n".join([f"• {m}" for m in missing]),
            title="Setup Missing Keys",
            border_style="yellow"
        ))
        return False
    return True


def is_termination_command(text: str) -> bool:
    """Check if the user is asking Jarvis to turn off or terminate."""
    if not text:
        return False
    clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
    termination_keywords = [
        "terminate yourself",
        "terminate jarvis",
        "terminate",
        "shut down",
        "shutdown",
        "turn off",
        "power off",
        "power down",
        "goodbye jarvis",
        "goodbye",
        "exit",
        "quit",
        "stop listening",
    ]
    for kw in termination_keywords:
        if kw in clean:
            return True
    return False


def is_proceed_command(text: str) -> bool:
    """Check if the user confirmed they are done talking and want output."""
    if not text:
        return False
    clean = re.sub(r"[^\w\s]", "", text.lower()).strip()
    proceed_phrases = [
        "proceed",
        "go ahead",
        "give output",
        "give the output",
        "give answer",
        "give the answer",
        "answer",
        "execute",
        "thats all",
        "that is all",
        "thats it",
        "that is it",
        "nothing more",
        "no more",
        "no",
        "nope",
        "nah",
        "all done",
        "done",
        "carry on",
        "yes proceed",
        "ready",
    ]
    for phrase in proceed_phrases:
        if clean == phrase or clean.startswith(phrase) or phrase in clean.split():
            return True
    return False


def render_stack_table(answer_stack):
    """Display real-time visual table showing queries and background execution state."""
    table = Table(title="⚡ Jarvis Stack Execution Pipeline", border_style="cyan", header_style="bold cyan")
    table.add_column("Index", style="bold yellow", width=8, justify="center")
    table.add_column("Query", style="white", min_width=30)
    table.add_column("Reasoning Status", width=26)

    for item in answer_stack:
        idx = str(item["index"])
        q = item["query"]
        fut = item["future"]
        if fut.done():
            status = "[bold green]✅ Ready (Computed)[/bold green]"
        else:
            status = "[yellow]⏳ Reasoning in background...[/yellow]"
        table.add_row(idx, q, status)

    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# Hotkey-triggered voice session (runs in background thread)
# ─────────────────────────────────────────────────────────────────────────────

def run_hotkey_session(stt: SpeechRecognizer, brain: JarvisBrain,
                       executor_pool: concurrent.futures.ThreadPoolExecutor,
                       overlay: JarvisOverlay):
    """
    A complete single-turn voice session triggered by the global hotkey.
    Runs in a background thread so the console loop is not blocked.
    """
    # ── Wake cue ─────────────────────────────────────────────
    overlay.set_state("listening")
    if JARVIS_WAKE_SOUND:
        speak("Listening, sir.")

    # ── Capture first query ───────────────────────────────────
    console.print("[bold red]🔴 [Hotkey] Listening... (speak now)[/bold red]")
    audio_data = stt.record_until_silence(
        silence_duration=JARVIS_SILENCE_TIMEOUT,
        initial_timeout=6.0
    )

    if audio_data is None:
        console.print("[dim]No speech detected via hotkey.[/dim]")
        overlay.set_state("hidden")
        return

    overlay.set_state("thinking")
    console.print("[dim]⚡ Transcribing via Groq Whisper...[/dim]")
    first_query = stt.transcribe(audio_data).strip()

    if not first_query:
        console.print("[dim]Could not recognise speech. Try again.[/dim]")
        overlay.set_state("hidden")
        return

    if is_termination_command(first_query):
        console.print(f"[bold green]You (Hotkey):[/bold green] {first_query}")
        msg = "Terminating systems. Have a productive day, sir."
        console.print(f"[bold cyan]Jarvis:[/bold cyan] {msg}")
        overlay.set_state("speaking")
        speak(msg)
        overlay.set_state("hidden")
        # Signal main loop to exit
        os._exit(0)
        return

    console.print(f"\n[bold green]▶ Hotkey Query:[/bold green] \"{first_query}\"")

    # ── Dispatch background reasoning immediately ─────────────
    fut = executor_pool.submit(brain.think, first_query)
    answer_stack = [{"index": 0, "query": first_query, "future": fut, "start_time": time.time()}]
    render_stack_table(answer_stack)

    # ── Wait for reasoning ────────────────────────────────────
    console.print("[dim]Finalizing answer...[/dim]")
    ans = fut.result()

    # ── Deliver answer aloud ──────────────────────────────────
    overlay.set_state("speaking")
    console.print(f"[bold cyan]Jarvis:[/bold cyan] {ans}\n")
    speak(ans)

    # ── Return to standby ────────────────────────────────────
    overlay.set_state("hidden")


# ─────────────────────────────────────────────────────────────────────────────
# Main Phase 1 loop
# ─────────────────────────────────────────────────────────────────────────────

def run_phase1():
    print_banner()

    if not os.path.exists(ENV_PATH):
        # Create .env from template if missing
        example_path = ENV_PATH.parent / ".env.example"
        if os.path.exists(example_path):
            with open(example_path, "r") as f_in, open(ENV_PATH, "w") as f_out:
                f_out.write(f_in.read())

    if not check_environment():
        console.print(f"\n[cyan]Edit your settings here:[/cyan] [bold underline]{ENV_PATH}[/bold underline]\n")
        return

    console.print("[dim]Initializing Jarvis modules & thread pool...[/dim]")
    try:
        brain = JarvisBrain()
        stt = SpeechRecognizer()
        executor_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        return

    # ── Start iOS-style overlay dot ───────────────────────────
    overlay = JarvisOverlay()
    overlay.start()

    # ── Register global hotkey ────────────────────────────────
    def _hotkey_callback():
        """Runs in a daemon thread when Fn+Home (or configured key) is pressed."""
        t = threading.Thread(
            target=run_hotkey_session,
            args=(stt, brain, executor_pool, overlay),
            daemon=True,
            name="JarvisHotkeySession"
        )
        t.start()

    hotkey_mgr = GlobalHotkeyManager(
        hotkey_str=JARVIS_HOTKEY,
        callback=_hotkey_callback
    )
    hotkey_mgr.start()

    # ── Greeting ─────────────────────────────────────────────
    greeting = "Jarvis online and ready, sir. Stack execution pipeline active. How may I assist you?"
    console.print(f"[bold cyan]Jarvis:[/bold cyan] {greeting}")
    speak(greeting)

    console.print(
        "\n[bold green]Commands:[/bold green] [dim]Type '/text' for text-only, '/voice' for mic mode, "
        "'/reset' to clear memory, 'exit' to quit.[/dim]"
    )
    console.print(
        f"[bold yellow]🟠 Hotkey:[/bold yellow] [dim]Press [bold]{JARVIS_HOTKEY.upper()}[/bold] "
        "anytime (from any app) to speak to Jarvis.[/dim]\n"
    )

    mode = "voice"  # 'voice' or 'text'

    while True:
        try:
            if mode == "voice":
                user_input = Prompt.ask(
                    "[bold yellow]Press [Enter] to start speaking[/bold yellow] (or type text/command)"
                ).strip()

                if is_termination_command(user_input):
                    shutdown_msg = "Terminating systems. Have a productive day, sir."
                    console.print(f"[bold cyan]Jarvis:[/bold cyan] {shutdown_msg}")
                    overlay.set_state("speaking")
                    speak(shutdown_msg)
                    break
                elif user_input.lower() == "/text":
                    mode = "text"
                    console.print("[cyan]Switched to Text Mode.[/cyan]")
                    continue
                elif user_input.lower() == "/reset":
                    brain.reset_memory()
                    console.print("[green]Conversational memory reset.[/green]")
                    speak("Memory cleared, sir. Starting a fresh session.")
                    continue
                elif user_input:
                    # User typed directly
                    future = executor_pool.submit(brain.think, user_input)
                    answer_stack = [{"index": 0, "query": user_input, "future": future, "start_time": time.time()}]
                else:
                    # Voice capture: Stack Pipelined Execution
                    overlay.set_state("listening")
                    console.print("[bold red]🔴 Listening for Command [Index 0]... (Speak now)[/bold red]")
                    audio_data = stt.record_until_silence(silence_duration=2.2, initial_timeout=5.0)

                    if audio_data is None:
                        console.print("[dim]No speech detected. Try again.[/dim]")
                        overlay.set_state("hidden")
                        continue

                    overlay.set_state("thinking")
                    console.print("[dim]⚡ Transcribing via Groq Whisper...[/dim]")
                    first_query = stt.transcribe(audio_data).strip()

                    if not first_query:
                        console.print("[dim]No speech recognized. Try again.[/dim]")
                        overlay.set_state("hidden")
                        continue

                    # Check for voice termination command immediately
                    if is_termination_command(first_query):
                        console.print(f"[bold green]You (Spoken):[/bold green] {first_query}")
                        shutdown_msg = "Terminating systems. Have a good day, sir."
                        console.print(f"[bold cyan]Jarvis:[/bold cyan] {shutdown_msg}")
                        overlay.set_state("speaking")
                        speak(shutdown_msg)
                        break

                    # Initialize Stacks
                    fut0 = executor_pool.submit(brain.think, first_query)
                    answer_stack = [{"index": 0, "query": first_query, "future": fut0, "start_time": time.time()}]

                    console.print(f"\n[bold green]▶ Stack [Index 0]:[/bold green] \"{first_query}\"")
                    render_stack_table(answer_stack)

                    # Pipelined Stack Continuation Loop
                    while True:
                        followup_prompt = "Shall I proceed, sir, or would you like to add more?"
                        console.print(f"[bold cyan]Jarvis:[/bold cyan] {followup_prompt}")
                        speak(followup_prompt)

                        next_idx = len(answer_stack)
                        console.print(f"[dim]🎤 Listening... (Speak for Index {next_idx}, say 'proceed' / 'give output', or stay quiet)[/dim]")

                        overlay.set_state("listening")
                        followup_audio = stt.record_until_silence(silence_duration=1.8, initial_timeout=3.5)

                        if followup_audio is None:
                            console.print("[dim]No additional input detected. Delivering answers...[/dim]")
                            overlay.set_state("thinking")
                            break

                        followup_text = stt.transcribe(followup_audio).strip()
                        if not followup_text:
                            overlay.set_state("thinking")
                            break

                        if is_termination_command(followup_text):
                            console.print(f"[bold green]You (Spoken):[/bold green] {followup_text}")
                            shutdown_msg = "Terminating systems. Have a good day, sir."
                            console.print(f"[bold cyan]Jarvis:[/bold cyan] {shutdown_msg}")
                            overlay.set_state("speaking")
                            speak(shutdown_msg)
                            overlay.set_state("hidden")
                            return

                        if is_proceed_command(followup_text):
                            console.print(f"[dim]Confirmed: '{followup_text}'. Preparing final answers...[/dim]")
                            overlay.set_state("thinking")
                            break
                        else:
                            fut = executor_pool.submit(brain.think, followup_text)
                            answer_stack.append({"index": next_idx, "query": followup_text, "future": fut, "start_time": time.time()})
                            console.print(f"\n[bold green]▶ Stack [Index {next_idx}]:[/bold green] \"{followup_text}\"")
                            render_stack_table(answer_stack)

            else:  # Text mode
                query = Prompt.ask("[bold green]You[/bold green]").strip()
                if is_termination_command(query):
                    shutdown_msg = "Goodbye, sir. Systems powering down."
                    console.print(f"[bold cyan]Jarvis:[/bold cyan] {shutdown_msg}")
                    overlay.set_state("speaking")
                    speak(shutdown_msg)
                    break
                elif query.lower() == "/voice":
                    mode = "voice"
                    console.print("[cyan]Switched to Voice Mode.[/cyan]")
                    continue
                elif query.lower() == "/reset":
                    brain.reset_memory()
                    console.print("[green]Conversational memory reset.[/green]")
                    speak("Memory cleared, sir.")
                    continue

                if not query:
                    continue

                fut = executor_pool.submit(brain.think, query)
                answer_stack = [{"index": 0, "query": query, "future": fut, "start_time": time.time()}]

            # ── Delivery Phase ────────────────────────────────────────────────
            if not answer_stack:
                overlay.set_state("hidden")
                continue

            console.print("\n[bold cyan]══════════════════ ⚡ Stack Answers ══════════════════[/bold cyan]")
            overlay.set_state("thinking")
            render_stack_table(answer_stack)

            for item in answer_stack:
                idx = item["index"]
                q = item["query"]
                fut = item["future"]

                if not fut.done():
                    console.print(f"[dim]Finalizing answer for Index {idx}...[/dim]")

                ans = fut.result()
                overlay.set_state("speaking")

                if len(answer_stack) == 1:
                    console.print(f"[bold cyan]Jarvis:[/bold cyan] {ans}\n")
                    speak(ans)
                else:
                    label = f"Command {idx + 1}"
                    console.print(f"[bold cyan]Jarvis [{label} — \"{q}\"]:[/bold cyan] {ans}\n")
                    speak(f"For {label}: {ans}")

            overlay.set_state("hidden")

        except KeyboardInterrupt:
            console.print("\n[yellow]Session interrupted.[/yellow]")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            overlay.set_state("hidden")

    # Cleanup
    hotkey_mgr.stop()
    overlay.stop()


if __name__ == "__main__":
    run_phase1()
