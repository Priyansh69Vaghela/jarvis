import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load .env file
load_dotenv(dotenv_path=ENV_PATH)

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Voice configuration (Edge-TTS)
JARVIS_VOICE = os.getenv("JARVIS_VOICE", "en-US-ChristopherNeural")
JARVIS_VOICE_RATE = os.getenv("JARVIS_VOICE_RATE", "+5%")
JARVIS_VOICE_PITCH = os.getenv("JARVIS_VOICE_PITCH", "+0Hz")

# Background hotkey activation settings
# Options: 'home', 'ctrl+home', 'alt+home', 'alt+j'
# Strip inline comments (e.g. JARVIS_HOTKEY=home  # comment) and whitespace
_raw_hotkey = os.getenv("JARVIS_HOTKEY", "home")
JARVIS_HOTKEY = _raw_hotkey.split("#")[0].strip().lower()
# Whether to say "Listening, sir" aloud when hotkey fires
JARVIS_WAKE_SOUND = os.getenv("JARVIS_WAKE_SOUND", "true").lower() == "true"
# Seconds of silence after your voice before Jarvis processes the command
JARVIS_SILENCE_TIMEOUT = float(os.getenv("JARVIS_SILENCE_TIMEOUT", "2.0"))

# AI Brain settings
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# Audio recording settings
SAMPLE_RATE = 16000  # 16kHz for Whisper
CHANNELS = 1

# System persona
JARVIS_SYSTEM_PROMPT = """You are Jarvis, an advanced personal desktop AI assistant inspired by Iron Man's J.A.R.V.I.S.
Key guidelines for your behavior:
1. Tone: Professional, intelligent, articulate, polite, and subtly witty.
2. Response Style: Keep spoken responses concise, natural, and direct (1-3 sentences max for normal chat), as your responses will be read aloud through speech synthesis.
3. Conversational Memory: Maintain continuity and remember previous context in the conversation.
4. When asked what you can do: Explain that you are currently in Phase 1 (Voice understanding, conversational reasoning, and natural speech response), and will soon gain desktop and browser control in the upcoming phases.
"""
