import io
import time
import wave
import tempfile
import numpy as np
import sounddevice as sd
from groq import Groq
from src.config import GROQ_API_KEY, GROQ_WHISPER_MODEL, SAMPLE_RATE, CHANNELS

import re

def parse_wake_phrase(text: str):
    """
    Checks if text contains a Jarvis wake command.
    Returns (is_wake: bool, remaining_query: str).
    """
    t = text.strip()
    if not t:
        return False, ""
    
    # 1. Matches "hey jarvis", "hello jarvis", "listen jarvis", "ok jarvis", "hi jarvis", or "jarvis"
    m = re.match(r'^(?:hey|hello|hi|listen|ok|okay)?\s*\bjarvis[\s,:\.!?]*(.*)$', t, re.IGNORECASE)
    if m:
        return True, m.group(1).strip()
    
    # 2. Check if jarvis is mentioned anywhere in the utterance
    if re.search(r'\bjarvis\b', t, re.IGNORECASE):
        cleaned = re.sub(r'\b(?:hey|hello|hi|listen|ok|okay)?\s*\bjarvis\b[\s,:\.!?]*', '', t, flags=re.IGNORECASE).strip()
        return True, cleaned
        
    return False, ""

class SpeechRecognizer:
    def __init__(self):
        self.client = None
        if GROQ_API_KEY:
            self.client = Groq(api_key=GROQ_API_KEY)

    def listen_for_wake_phrase(self, is_busy_fn, silence_threshold=0.018):
        """
        Passive background ear for Standby mode.
        Monitors microphone without blocking. When volume exceeds silence_threshold,
        captures the speech segment, transcribes, and checks for a Jarvis wake phrase.
        Returns (is_wake: bool, remaining_query: str).
        """
        chunk_duration = 0.1
        chunk_samples = int(SAMPLE_RATE * chunk_duration)
        audio_chunks = []
        started_talking = False
        silence_start_time = None
        start_time = time.time()

        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32') as stream:
                while True:
                    if is_busy_fn():
                        return False, ""
                    
                    data, _ = stream.read(chunk_samples)
                    volume = np.linalg.norm(data) / np.sqrt(len(data))

                    if volume > silence_threshold:
                        if not started_talking:
                            started_talking = True
                            start_time = time.time()
                        silence_start_time = None
                        audio_chunks.append(data)
                    elif started_talking:
                        audio_chunks.append(data)
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > 1.0:
                            # 1.0s of silence after speech -> user finished speaking
                            break
                    else:
                        time.sleep(0.02)
                        # After 2.0s of pure silence, cycle so caller can check busy flag
                        if time.time() - start_time > 2.0:
                            return False, ""

                    if started_talking and (time.time() - start_time > 4.5):
                        break

            if not audio_chunks or is_busy_fn():
                return False, ""

            audio_data = np.concatenate(audio_chunks, axis=0)
            transcription = self.transcribe(audio_data).strip()
            if not transcription or is_busy_fn():
                return False, ""

            return parse_wake_phrase(transcription)

        except Exception:
            time.sleep(0.3)
            return False, ""

    def record_until_silence(self, silence_threshold=0.015, silence_duration=2.2, max_duration=30.0, initial_timeout=5.0):
        """
        Record audio from microphone with automatic silence detection.
        Starts recording when user speaks, and stops after silence_duration seconds of quiet.
        If user does not begin speaking within initial_timeout seconds, returns None.
        """
        chunk_duration = 0.1  # 100ms chunks
        chunk_samples = int(SAMPLE_RATE * chunk_duration)
        
        audio_chunks = []
        started_talking = False
        silence_start_time = None
        start_time = time.time()

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32') as stream:
            while True:
                data, _ = stream.read(chunk_samples)
                volume = np.linalg.norm(data) / np.sqrt(len(data))
                
                if volume > silence_threshold:
                    if not started_talking:
                        started_talking = True
                    silence_start_time = None
                    audio_chunks.append(data)
                elif started_talking:
                    audio_chunks.append(data)
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif time.time() - silence_start_time > silence_duration:
                        # User stopped speaking for silence_duration
                        break
                else:
                    # User hasn't started talking yet; check initial timeout
                    if time.time() - start_time > initial_timeout:
                        break

                # Safety max duration cutoff
                if time.time() - start_time > max_duration:
                    break

        if not audio_chunks:
            return None

        audio_data = np.concatenate(audio_chunks, axis=0)
        return audio_data

    def record_fixed_duration(self, duration=5.0):
        """Record audio for a fixed number of seconds."""
        recording = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32')
        sd.wait()
        return recording

    def transcribe(self, audio_data) -> str:
        """Transcribe numpy audio data using Groq Cloud Whisper."""
        if audio_data is None or len(audio_data) == 0:
            return ""

        if not self.client:
            if not GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY is missing in your .env file.")
            self.client = Groq(api_key=GROQ_API_KEY)

        # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767] for WAV format
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Write to temporary WAV file using built-in wave module
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            temp_wav_path = temp_wav.name

        with wave.open(temp_wav_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

        try:
            with open(temp_wav_path, "rb") as file:
                transcription = self.client.audio.transcriptions.create(
                    file=(temp_wav_path, file.read()),
                    model=GROQ_WHISPER_MODEL,
                    response_format="text",
                    language="en"
                )
            return transcription.strip()
        finally:
            import os
            try:
                if os.path.exists(temp_wav_path):
                    os.remove(temp_wav_path)
            except Exception:
                pass
