"""Upload a local photo and animate it with an image-to-video model.

    python examples/image_to_video.py photo.jpg
"""

import pathlib
import sys

from popnow import PopNow, TaskFailedError

MODEL = "alibaba/wan-3.0/image-to-video"

client = PopNow()
photo = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "photo.jpg")

# A pathlib.Path in a media field is uploaded first (upload-url -> PUT -> commit).
try:
    task = client.videos.generate(
        model=MODEL,
        image_url=photo,
        prompt="Gentle camera push-in, soft wind in the hair",
        resolution="480p",
        duration_seconds=5,
        timeout=1800,  # video can take several minutes
    )
except TaskFailedError as err:
    print("generation failed:", err.error_code, err.error_message)
    raise SystemExit(1)

out = client.files.download(task.assets[0], photo.with_suffix(".mp4"))
print("saved", out, "for", task.credits, "credits")
