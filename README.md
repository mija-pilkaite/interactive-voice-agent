# Spike Clinical CLI Voice Agent

An interactive command-line tool that simulates a hospital staff member calling an insurance provider to verify patient coverage details using real-time voice: speech-to-text (Deepgram) ➔ LLM dialogue (OpenAI) ➔ text-to-speech (ElevenLabs) ➔ audio playback.

---

## 🚀 Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/mija-pilkaite/interactive-voice-agent.git
   cd interactive-voice-agent
    ```

2. **Create a Python virtual environment**:
    ```
    python3 -m venv .venv
    source .venv/bin/activate      # macOS/Linux
    .\\.venv\\Scripts\\activate    # Windows (PowerShell)
    ```

3. **Install dependencies**:
    ```
    pip install -r requirements.txt
    ```

4. **Configure API keys**:
    •	Copy the provided .env.example to .env:
    ```
    cp .env.example .env
    ```
    •	Fill in your own keys:
    ```
    DEEPGRAM_API_KEY=...
    OPENAI_API_KEY=...
    ELEVENLABS_API_KEY=...
    ```

5. **Customize config.yml (optional)**:

    •	Adjust recorder settings (samplerate, frame_duration)

	•	Set TTS voice or name

	•	Change LLM model or system prompt template

6. **Run the app**:
    ```
    python -m spike_cli.main
    ```

    You can customize the voice in the config file or override during runtime by choosing the desired name. 
    ```
    python -m spike_cli.main --voice-name Aria  
    ```

    Here's a few recommendations depending on your needs:

    1. **Aria** - Standart Female Voice
    2. **Roger** - Standart Male Voice
    3. **Sarah** 
    4. **Laura**
    5. **Charlie**

    You can also get the full list of names by running:

    ```
    python -m spike_cli.list_voices
    ```

7. **(Optional) Docker (<- right now only supported on Linux as on Mac and Windows I could not make it access the mic and the speakers)**:
    ```
    docker build -t spike-cli .
    docker run --rm -it --env-file .env spike-cli
    ```


## 🏗️ Architecture Overview
```
┌──────────┐   PCM ┌───────────┐  Text ┌────────────┐  Prompt┌───────────--┐  Text ┌───────────┐  PCM  ┌────────---┐
│ Micro-   │──────▶│ Recorder  │──────▶│ Deepgram   │──────▶ │ Verification│──────▶│ ElevenLabs│──────▶│ Player    │
│ phone    │       │ (VAD)     │       │ STT Client │        │ Agent       │       │ TTS Client│       │ (Playback)│
└──────────┘       └───────────┘       └────────────┘        └───────────--┘       └───────────┘       └────────---┘
```


	•	Recorder (recorder.py): captures live audio, segments utterances via WebRTC VAD, emits utterance buffers.

	•	STT (stt.py): wraps Deepgram pre-recorded (and optionally live) API to transcribe buffered PCM into text.

	•	Verification Agent (verification_agent.py): maintains JSON state, prompts GPT-4 to ask for missing insurance fields in natural dialogue.

	•	TTS (tts.py): uses ElevenLabs API; supports voice lookup by voice_id or friendly voice_name.

	•	Player (player.py): plays raw PCM via sounddevice.

	•	Main (spike_cli/main.py): wires together recorder, STT, agent, TTS and player; handles pause/resume to avoid feedback.


## 💡 Design Decisions & Trade-Offs

| Decision                      | Pros                                         | Cons                                               |
| ----------------------------- | -------------------------------------------- | -------------------------------------------------- |
| **Python CLI**                | Rapid prototyping, rich audio libs           | Single-threaded limits, packaging overhead         |
| **WebRTC VAD**                | Lightweight, accurate utterance segmentation | Tuning thresholds; occasional misfires             |
| **Deepgram prerecord vs live**| Simpler integration, fewer WS issues         | Latency per utterance; no human-like interjections |
| **GPT-4 via OpenAI API**      | State-of-the-art language understanding      | API cost; token-limit constraints                  |
| **ElevenLabs TTS**            | High-quality natural voices                  | API cost; voice IDs update over time               |
| **Pause/Resume stream**       | Prevents self-echo during playback           | Brief dead-zones; complexity in state management   |
| **Dockerized Linux workflow** | Reproducible builds; easy CI/CD              | No native audio on macOS/Windows; needs stubbing   |


### Detailed Explanations

#### Python CLI

We chose a command-line interface in Python because it allows rapid prototyping and leverages powerful audio libraries (PortAudio via sounddevice, WebRTC VAD) without dealing with browser complexities. The trade‑off is that Python’s single‑threaded nature and reliance on a global interpreter lock can block I/O; packaging a CLI also adds friction for end users installing dependencies.

#### WebRTC VAD

WebRTC’s VAD module runs in native code and can accurately detect speech vs. silence with minimal CPU overhead. It ships as a simple API (is_speech(frame)), making it easy to integrate. However, the frame duration and aggressiveness parameters must be tuned to avoid clipping speech or capturing too much silence.

#### Deepgram prerecord vs live

Using Deepgram’s prerecorded endpoint simplifies integration (pure HTTP) and avoids WebSocket header issues, while still delivering high transcription accuracy with punctuation. The downside is that each chunk must finish before sending, introducing tens to hundreds of milliseconds of latency. A live WebSocket stream can reduce latency and support real‑time partial transcripts, but it requires more complex error‑handling and header patching and more implementation time. 

#### GPT-4 via OpenAI API

I use GPT-4 for its stateful conversational abilities and robust language understanding, which simplifies crafting dynamic, context‑aware dialogue flows. The OpenAI SDK handles retries and streaming in future versions, but today’s v1 client is blocking. API usage costs and token limits also factor into prompt design and budgeting.

#### ElevenLabs TTS

ElevenLabs offers some of the best synthetic voices on the market, making my AI assistant sound natural. Their API is straightforward: send text, get back raw PCM chunks. Voices are managed by ID, and occasionally new voices are added or old ones deprecated, so we allow fallback and voice lookup by voice_name.

#### Pause/Resume stream

To avoid the microphone picking up the AI’s own voice during playback, we pause the sounddevice input stream before playing audio and resume afterward. This ensures clean recordings but introduces short gaps where the microphone is offline. Managing that state adds complexity to the Recorder class.

#### Dockerized Linux workflow

We provide a Dockerfile for Linux to guarantee consistent dependencies and simplify CI/CD. Audio support in containers is tricky on macOS/Windows—devices may not map directly—so for local development on non‑Linux hosts, running natively may be necessary (at least in the MVP!!!:>).


## Call Pipeline

### 1) Audio Capture (`Recorder._enqueue`)

- **Async?** No  
- **How it works:**  
  - Uses `sounddevice.InputStream` from the PortAudio C library.  
  - Invokes a Python callback on each audio buffer (frame) arrival.  
- **Why synchronous:**  
  - PortAudio’s callback interface is inherently synchronous and real-time.  
  - Audio I/O demands low latency (milliseconds), and using an `asyncio` wrapper adds complexity and potential jitter.  
  - Running in the native audio thread ensures minimal overhead and drop-free capture.

### 2) Utterance Segmentation (`Recorder._process_audio`)

- **Async?** No (runs in its own thread)  
- **How it works:**  
  - A Python thread consumes raw PCM frames from a `queue.Queue`.  
  - Applies `webrtcvad.Vad.is_speech(frame, sample_rate)` to detect speech vs. silence.  
  - Buffers frames until N milliseconds of silence, then emits a complete “utterance” (byte block).  
- **Why thread‐based sync:**  
  - VAD processing is CPU‐bound and needs to run frame-by-frame as fast as audio arrives.  
  - Offloading to a dedicated thread avoids blocking the main thread or event loop, while keeping audio segmentation deterministic.

### 3) Speech-to-Text (DeepgramSTT.transcribe)

- **Async?** Yes  
- **How it works:**  
  - Wraps raw PCM in an in-memory WAV container.  
  - Calls `await dg_client.transcription.prerecorded(source, options)` via the Deepgram SDK.  
  - Parses the JSON response to extract the best `transcript`.  
- **Why asynchronous:**  
  - Network I/O to Deepgram can vary from tens to hundreds of milliseconds.  
  - `asyncio` lets you dispatch multiple transcriptions or keep the UI/loop responsive if you extend to parallel calls.  
  - Avoids blocking the main thread during the HTTP request.

### 4) LLM Interaction (`VerificationAgent.process`)

- **Async?** No  
- **How it works:**  
  - Appends the user’s transcript to an internal history list.  
  - Calls `openai.chat.completions.create(model, messages)` synchronously (blocking).  
  - Receives a combined natural-language reply + updated JSON state block.  
- **Why synchronous:**  
  - The current OpenAI Python SDK (v1) does not natively support `asyncio` calls out of the box.  
  - Each LLM request depends on the previous state and must complete before generating the next prompt.  
  - The conversational flow naturally pauses for the AI’s response, so blocking here does not degrade user experience.

### 5) Text-to-Speech (`ElevenLabsTTS.synthesize`)

- **Async?** No  
- **How it works:**  
  - Calls `client.text_to_speech.convert(text, voice_id, ...)` which returns an iterator (or list) of raw PCM chunks.  
  - Joins chunks into a single bytes object.  
- **Why synchronous:**  
  - ElevenLabs’ Python client provides a blocking HTTP API by design.  
  - Since synthesis only happens once per assistant turn (after getting the LLM reply), a simple blocking call keeps code straightforward.  
  - You want the full audio buffer before playback begins, so streaming here adds little benefit.

### 6) Audio Playback (`Player.play`)

- **Async?** No  
- **How it works:**  
  - Converts the PCM bytes to a NumPy `int16` array.  
  - Calls `sounddevice.play(audio, samplerate)` and then `sounddevice.wait()` to block until playback finishes.  
- **Why synchronous:**  
  - Playback must complete before resuming the microphone to avoid self-echo and overlap.  
  - Blocking `sd.wait()` ensures no race conditions between playing and capturing.



## 🔮 Future Improvements

1. **WebSocket API for External UIs and Dashboards**:
Develop a bidirectional WebSocket endpoint that exposes live call events (e.g., raw audio frames, partial and final transcripts, agent prompts) to browser-based or desktop client dashboards. This enables real-time monitoring, visual transcript overlays, and remote control (e.g., pause/resume, push custom prompts).

2. **Real-time STT Streaming with Human-like Interruptions**:
Integrate Deepgram’s live streaming API to receive partial transcripts as audio arrives. By processing interim hypotheses, the agent can detect sentence boundaries or key keywords and interject follow-up questions without waiting for the entire utterance. This mimics a more conversational, human-to-human interruption style.

3. **Redis-backed Cache & Queue for Scalability**
Use Redis to cache recent STT transcripts and LLM responses, reducing redundant API calls for identical inputs. Implement a queue for orchestrating multiple concurrent calls (e.g., dozens of agent sessions), enabling horizontal scaling and reliable message delivery with retry logic on transient failures.

4. **Custom Voice Training & Personality Presets**
Allow users to upload or fine-tune ElevenLabs voices for branded or domain-specific tonality (e.g., pediatric, geriatric, corporate). Provide personality presets via system-prompt templates (e.g., “cheerful concierge,” “formal verifier”), so switching between different agent personas is as simple as selecting a dropdown.

5. **Web Front-end with Live Transcript & Call Logs**
Build a lightweight React interface that connects to the WebSocket API. Display live-updating transcripts, audio waveform visualization, and a sidebar of captured insurance data. Store call logs to a database for audit trails, transcripts archiving, and post-call review.

6. **Database implementation**
Database for the patients and having the LLM gathered information saved into the database. This would allow saving the patient's information, access it later and as well even implement an algorithm that the LLM calls for patients that are still missing their insurance information. 
