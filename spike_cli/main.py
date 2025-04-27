#!/usr/bin/env python3
import asyncio
import argparse
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv

from spike_cli.recorder           import Recorder
from spike_cli.stt                import DeepgramSTT
from spike_cli.tts                import ElevenLabsTTS
from spike_cli.player             import Player
from spike_cli.verification_agent import VerificationAgent

def load_config():
    cfg_path = Path(__file__).parent.parent / "config.yml"
    return yaml.safe_load(cfg_path.read_text())

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--voice-name", "-v", metavar="NAME",
        help="User-friendly name of the ElevenLabs voice (e.g. Aria, Roger, Sarah, etc.)"
    )
    return p.parse_args()

async def main():
    # 1) Load environment & config
    load_dotenv(Path(__file__).parent.parent / ".env")
    config = load_config()
    args = parse_args()
    if args.voice_name:
        config.setdefault("tts", {})["voice_name"] = args.voice_name

    # 2) Initialize components
    rec_cfg  = config.get("recorder", {})
    recorder = Recorder(
        samplerate=rec_cfg.get("samplerate", 16000),
        frame_duration=rec_cfg.get("frame_duration", 30),
        aggressiveness=rec_cfg.get("aggressiveness", 2)
    )
    stt    = DeepgramSTT(sample_rate=rec_cfg.get("samplerate", 16000))
    tts    = ElevenLabsTTS(config)
    player = Player(sample_rate=rec_cfg.get("samplerate", 16000), channels=1)
    agent  = VerificationAgent(config)

    state = agent.initial_state.copy()
    print("📋 Starting with state:", state)

    # shared error handler
    def handle_fatal_error():
        apology = (
            "I’m sorry, it seems something went wrong on our side. "
            "I will make sure to call you back as soon as we have everything fixed. Goodbye."
        )
        recorder.pause()
        player.play(tts.synthesize(apology))
        recorder.stop()

    # 3) Queues and callbacks
    audio_q      = asyncio.Queue()
    transcript_q = asyncio.Queue()

    loop = asyncio.get_running_loop()
    def on_frame(frame: bytes):
        loop.call_soon_threadsafe(audio_q.put_nowait, frame)

    recorder.start(on_frame)
    print("🟢 Recording and verifying coverage... (Ctrl-C to exit)")

    # 4) STT worker
    async def stt_worker():
        while True:
            utt = await audio_q.get()
            try:
                text = await stt.transcribe(utt)
            except Exception as e:
                print("⚠️ STT error:", e, file=sys.stderr)
                handle_fatal_error()
                return
            if text:
                transcript_q.put_nowait(text)

    # 5) Agent worker
    async def agent_worker():
        while True:
            rep = await transcript_q.get()
            print(f"🎙️ Rep: {rep}")
            buffer = ""
            seen_fence = False

            def nl_cb(token: str):
                nonlocal buffer, seen_fence
                buffer += token
                print(token, end="", flush=True)

                # once we hit the JSON fence, speak the natural language part
                if not seen_fence and "```json" in buffer:
                    seen_fence = True
                    nl_text, _ = buffer.split("```json", 1)
                    nl_text = nl_text.strip()
                    recorder.pause()
                    try:
                        player.play(tts.synthesize(nl_text))
                    except Exception as e:
                        print("⚠️ TTS error:", e, file=sys.stderr)
                        handle_fatal_error()
                        return
                    recorder.resume()

                    low = nl_text.lower()
                    if any(f in low for f in ["goodbye", "have a great day", "thank you for your time"]):
                        recorder.stop()

            def state_cb(new_state: dict):
                state.update(new_state)
                print("\n📋 Info:", state)

            try:
                await agent.stream(rep, nl_cb, state_cb)
            except Exception as e:
                print("⚠️ Agent error:", e, file=sys.stderr)
                handle_fatal_error()
                return

            if not seen_fence and buffer.strip():
                nl_text = buffer.strip()
                recorder.pause()
                try:
                    player.play(tts.synthesize(nl_text))
                except Exception as e:
                    print("⚠️ TTS error:", e, file=sys.stderr)
                    handle_fatal_error()
                    return
                recorder.resume()
                if any(f in nl_text.lower() for f in ["goodbye", "have a great day", "thank you for your time"]):
                    recorder.stop()

    # 6) Play initial opener
    opener, _ = agent.process("")
    nl = opener.split("```json")[0].strip()
    print(f"🤖 Spike Clinical: {nl}")
    recorder.pause()
    player.play(tts.synthesize(nl))
    recorder.resume()

    # 7) Run workers
    tasks = [
        asyncio.create_task(stt_worker()),
        asyncio.create_task(agent_worker())
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        recorder.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Call ended.")
        sys.exit(0)