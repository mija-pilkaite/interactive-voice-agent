#!/usr/bin/env python3

import asyncio
from pathlib import Path
import yaml
from dotenv import load_dotenv

from spike_cli.recorder           import Recorder
from spike_cli.stt                import DeepgramSTT
from spike_cli.tts                import ElevenLabsTTS
from spike_cli.player             import Player
from spike_cli.verification_agent import VerificationAgent
import argparse

def load_config():
    cfg_path = Path(__file__).parent.parent / "config.yml"
    return yaml.safe_load(cfg_path.read_text())

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--voice-name",
        "-v", metavar="NAME",
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
    rec_cfg = config.get("recorder", {})
    recorder = Recorder(
        samplerate=rec_cfg.get("samplerate", 16000),
        frame_duration=rec_cfg.get("frame_duration", 30),
        aggressiveness=rec_cfg.get("aggressiveness", 2)
    )
    stt    = DeepgramSTT(sample_rate=rec_cfg.get("samplerate", 16000))
    tts    = ElevenLabsTTS(config)
    player = Player(sample_rate=rec_cfg.get("samplerate", 16000), channels=1)
    
    agent = VerificationAgent(config)
    state = agent.initial_state.copy()
    print("📋 Starting with state:", state)

    # 3) Setup asyncio queues for pipelining
    audio_q      = asyncio.Queue()
    transcript_q = asyncio.Queue()
    pcm_q        = asyncio.Queue()

    # 4) Recorder: feed frames into audio_q
    loop = asyncio.get_running_loop()
    def on_frame(frame: bytes):
        # schedule the put into the asyncio loop
        loop.call_soon_threadsafe(audio_q.put_nowait, frame)

    recorder.start(on_frame)
    print("🟢 Recording and verifying coverage... (Ctrl-C to exit)")

    # 5) STT worker: live stream audio -> transcripts
    async def stt_worker():
        while True:
            utt = await audio_q.get()
            text = await stt.transcribe(utt)
            if text:
                transcript_q.put_nowait(text)

    # 6) Agent worker: transcripts -> LLM stream -> TTS queue
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

                if not seen_fence and "```json" in buffer:
                    seen_fence = True
                    nl_text, _ = buffer.split("```json", 1)
                    nl_text = nl_text.strip()

                    # pause the mic, speak, then resume
                    recorder.pause()
                    player.play(tts.synthesize(nl_text))
                    recorder.resume()

                    # if AI said goodbye (or any farewell), end the call
                    low = nl_text.lower()
                    if any(f in low for f in ["goodbye", "have a great day", "thank you for your time"]):
                        recorder.stop()

            def state_cb(new_state: dict):
                state.update(new_state)
                print("\n📋 Info:", state)

            # stream GPT-4; nl_cb speaks as soon as it sees the JSON boundary
            await agent.stream(rep, nl_cb, state_cb)

            # fallback: if for some reason no fence appears, speak entire buffer now
            if not seen_fence and buffer.strip():
                nl_text = buffer.strip()
                recorder.pause()
                player.play(tts.synthesize(nl_text))
                recorder.resume()
                if any(f in nl_text.lower() for f in ["goodbye", "have a great day", "thank you for your time"]):
                    recorder.stop()

    # 7) Player worker: pcm chunks -> speaker
    async def player_worker():
        await player.stream_play(pcm_q)

    # 8) Play initial opener
    opener, _ = agent.process("")
    nl = opener.split("```json")[0].strip()
    print(f"🤖 Spike Clinical: {nl}")
    recorder.pause()
    player.play(tts.synthesize(nl))
    recorder.resume()

    # 9) Run workers and handle exit
    tasks = [
        asyncio.create_task(stt_worker()),
        asyncio.create_task(agent_worker()),
        asyncio.create_task(player_worker())
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
