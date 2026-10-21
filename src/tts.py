import asyncio
import os
import tempfile
import pygame
import edge_tts
from src.config import JARVIS_VOICE, JARVIS_VOICE_RATE, JARVIS_VOICE_PITCH

# Initialize pygame mixer for audio playback
if not pygame.mixer.get_init():
    pygame.mixer.init()

def select_voice_for_text(text: str) -> str:
    """Select the most natural voice based on detected language characters."""
    for ch in text:
        # Gujarati script: \u0A80 to \u0AFF
        if "\u0A80" <= ch <= "\u0AFF":
            return "gu-IN-NiranjanNeural"
        # Hindi/Devanagari script: \u0900 to \u097F
        elif "\u0900" <= ch <= "\u097F":
            return "hi-IN-MadhurNeural"
    return JARVIS_VOICE

async def generate_speech_audio(text: str, output_path: str):
    """Generate audio file from text using Microsoft Edge-TTS."""
    chosen_voice = select_voice_for_text(text)
    communicate = edge_tts.Communicate(
        text=text,
        voice=chosen_voice,
        rate=JARVIS_VOICE_RATE,
        pitch=JARVIS_VOICE_PITCH
    )
    await communicate.save(output_path)

def speak(text: str):
    """Convert text to speech and play it through speakers (blocking until done)."""
    if not text or not text.strip():
        return

    # Clean text of markdown formatting symbols that sound weird when spoken aloud
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").strip()

    # Create temporary file for mp3
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        temp_filename = fp.name

    try:
        # Run async edge-tts generation
        asyncio.run(generate_speech_audio(clean_text, temp_filename))

        # Play audio with pygame mixer
        pygame.mixer.music.load(temp_filename)
        pygame.mixer.music.play()

        # Wait for playback to finish
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)

    except Exception as e:
        print(f"[TTS Error]: {e}")
    finally:
        # Unload and clean up temporary file
        try:
            pygame.mixer.music.unload()
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except Exception:
            pass

if __name__ == "__main__":
    print("Testing Jarvis Voice...")
    speak("Good evening, sir. Jarvis audio systems are fully operational.")
