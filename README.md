# 🤖 J.A.R.V.I.S. — Personal AI Assistant

A private, fast, and intelligent voice assistant built for Windows with **0% local GPU load**.

---

## 🚀 Phase 1: Voice Understanding & Stack Execution Architecture
In this phase, Jarvis features:
- **Concurrent Stack Pipeline**: Stores speech in `query_stack` (`Index 0, 1, 2...`) while reasoning in parallel in `answer_stack`.
- **Zero-Wait Pipelining**: Calculates the answer for sentence 0 in the background *while* you speak sentence 1.
- **Listen & Silence Detection**: Auto-detects speech pauses with comfortable breathing room.
- **Real-Time Transcription (~250ms)**: Ultra-fast STT via Groq Cloud Whisper.
- **Resilient AI Reasoning**: Multi-turn memory and auto-failover across Gemini Flash models.
- **Natural Neural TTS**: Microsoft Edge-TTS voice playback with Pygame audio streaming.

---

## 🔑 Quick Setup

### 1. Configure Free API Keys
Copy `.env.example` to `.env` (or edit `.env` directly in the project root):

1. **Google Gemini API Key:** [Google AI Studio (Free)](https://aistudio.google.com/)
2. **Groq Cloud API Key:** [Groq Cloud Console (Free)](https://console.groq.com/)

Edit `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
JARVIS_VOICE=en-US-ChristopherNeural
```

---

## 🎙️ Running Jarvis (Phase 1)

Activate the virtual environment and launch:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

### Controls & Speech Flow:
- **Press `[Enter]`**: Start speaking into your microphone.
- **Smart Pause & Continuation Check**: When you finish speaking a sentence, Jarvis asks aloud: *"Shall I proceed, sir, or would you like to add more?"*
  - Speak additional thoughts to append to your query.
  - Say *"proceed"*, *"give output"*, *"that's all"*, or stay quiet for 3 seconds to generate the response.
- **Voice Termination**: Say *"terminate yourself jarvis"*, *"shut down"*, or *"turn off"* at any point to power down the assistant.
- **Type directly**: Enter text commands or queries.
- **`/text`**: Switch to text-only mode.
- **`/voice`**: Switch back to voice mode.
- **`/reset`**: Clear conversation memory.
- **`exit`**: Quit the assistant.
