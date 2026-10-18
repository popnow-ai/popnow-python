"""Generate one image and save it to disk.

    export POPNOW_API_KEY="sk-popnow-..."
    python examples/generate_image.py
"""

from popnow import PopNow

client = PopNow()

task = client.images.generate(
    model="alibaba/z-image-turbo/text-to-image",
    prompt="A small red fox curled up in a teacup, soft morning light",
    aspect_ratio="1:1",
)

print("state:", task.state, "credits charged:", task.credits)
path = client.files.download(task.assets[0], "fox.png")
print("saved", path)
