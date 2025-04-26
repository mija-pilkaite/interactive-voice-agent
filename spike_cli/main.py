#!/usr/bin/env python3

import signal
import yaml
from dotenv import load_dotenv
from pathlib import Path
import sounddevice as sd
from spike_cli.recorder import Recorder

def load_config():
    cfg_path = Path(__file__).parent.parent / "config.yml"
    return yaml.safe_load(cfg_path.read_text())

def main():
    # 1. Load env vars (for later STT/LLM/TTS steps)
    load_dotenv(Path(__file__).parent.parent / ".env")

    # 2. Load any config (e.g. sample rate, block duration)
    config = load_config()
    sr = config.get("recorder", {}).get("samplerate", 16_000)
    bd = config.get("recorder", {}).get("block_duration", 1.0)

    sd.default.device = config.get("recorder", {}).get("device", None)
    # 3. Instantiate the Recorder
    recorder = Recorder(samplerate=sr, block_duration=bd,  device=config["recorder"].get("device"))

    # 4. Define a simple callback to verify we’re getting audio
    def audio_callback(chunk: bytes):
        # each 'chunk' is raw PCM data
        print(f"[{len(chunk)} bytes] audio chunk captured")

    # 5. Start the recorder
    recorder.start(audio_callback)
    print("🟢 Recorder started. Speak into your mic! (Ctrl-C to stop)")

    # 6. Keep the process alive until Ctrl-C
    try:
        signal.pause()
    except KeyboardInterrupt:
        print("\n🛑 Stopping recorder...")
        recorder.stop()

if __name__ == "__main__":
    main()
