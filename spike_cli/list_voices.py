import os
from elevenlabs import ElevenLabs
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
if not API_KEY:
    raise ValueError("Set ELEVENLABS_API_KEY in your environment")

client = ElevenLabs(api_key=API_KEY)

# the get_all() call returns a .voices list of voice objects
voices = client.voices.get_all().voices

print(f"{'VOICE_ID':20} {'NAME':15} {'LANG':7} {'CATEGORY'}")
print("-" * 60)
for v in voices:
    print(f"{v.voice_id:20} {v.name:15} {v.category}")