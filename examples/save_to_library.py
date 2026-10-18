"""Keep a generated file in the asset library and reuse it by URI.

    python examples/save_to_library.py
"""

from popnow import PopNow

client = PopNow()

task = client.images.generate(
    model="alibaba/z-image-turbo/text-to-image",
    prompt="A ceramic mug with a hand-painted lemon, studio light",
)

# Saving the same output again returns the existing asset.
asset = client.assets.save_task_output(task.task_id, index=0, name="Lemon mug", idempotency_key=f"save-{task.task_id}-0")
print("saved", asset.uri)

edited = client.images.edit(
    model="google/nano-banana-2.1/edit",
    prompt="Put this mug on a wooden cafe table, morning light",
    image_urls=[asset.uri],
)
print(edited.urls[0])
