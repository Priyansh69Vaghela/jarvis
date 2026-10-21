import time
import socket
import datetime

# Ensure IPv4 resolution on Windows to avoid IPv6 connection stalls
try:
    _orig_getaddrinfo = socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    socket.getaddrinfo = _ipv4_getaddrinfo
except Exception:
    pass

from src.config import GEMINI_API_KEY, GEMINI_MODEL, JARVIS_SYSTEM_PROMPT

class JarvisBrain:
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in your .env file.")
        
        # Priority list of models to try if one is busy (503) or hits quota limits (429)
        self.models_to_try = []
        for m in [GEMINI_MODEL, "gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-lite-latest", "gemini-flash-latest"]:
            if m and m not in self.models_to_try:
                self.models_to_try.append(m)

        self.current_model_idx = 0
        self._init_client()

    def _get_system_prompt(self) -> str:
        """Inject current system date, day, and time into Jarvis persona."""
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%A, %B %d, %Y, %I:%M %p")
        return f"{JARVIS_SYSTEM_PROMPT}\n[System Context: Today is {timestamp_str}]"

    def _init_client(self):
        """Initialize Google GenAI client and start a persistent chat session."""
        from google import genai
        from google.genai import types

        model = self.models_to_try[self.current_model_idx]
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat = self.client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=self._get_system_prompt(),
                temperature=0.7,
            )
        )

    def think(self, user_text: str) -> str:
        """
        Send message to conversational memory and receive assistant response.
        Automatically retries and fails over to backup models on transient 503 spikes.
        """
        if not user_text.strip():
            return ""

        # Try with current model, retry once on 503, then fallback if needed
        last_error = None
        for attempt in range(len(self.models_to_try)):
            try:
                response = self.chat.send_message(user_text)
                return response.text.strip()
            except Exception as e:
                last_error = e
                err_str = str(e)
                
                # Check for transient server overload (503) or model unavailable
                if "503" in err_str or "NOT_FOUND" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    time.sleep(1.0)
                    # Advance to next fallback model
                    if self.current_model_idx + 1 < len(self.models_to_try):
                        self.current_model_idx += 1
                        try:
                            self._init_client()
                            continue
                        except Exception:
                            pass
                else:
                    break

        return f"I apologize, sir. I encountered a reasoning error: {str(last_error)}"

    def reset_memory(self):
        """Clear the conversation memory and start fresh."""
        self._init_client()
