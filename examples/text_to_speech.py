"""Turn each line of a text file into its own voiceover file.

    python examples/text_to_speech.py lines.txt
"""

import hashlib
import pathlib
import sys

from popnow import PopNow

MODEL = "google/gemini-3.8-flash-tts/text-to-speech"
EXTENSIONS = {"audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg"}

client = PopNow()
out = pathlib.Path("voice")
out.mkdir(exist_ok=True)

source = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "lines.txt")
lines = [line.strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]

for i, line in enumerate(lines, start=1):
    # A key derived from the content makes a rerun skip lines that already went through.
    key = "voice-" + hashlib.sha256(f"{i}:{line}".encode()).hexdigest()[:32]
    task = client.audio.speech(model=MODEL, text=line, voice_id="Kore", style="empathetic", idempotency_key=key)
    asset = task.assets[0]
    path = client.files.download(asset, out / f"{i:03d}{EXTENSIONS.get(asset.mime or '', '.audio')}")
    print("saved", path)
