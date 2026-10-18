"""Render several prompts concurrently with the async client.

    python examples/async_batch.py
"""

import asyncio

from popnow import AsyncPopNow, TaskFailedError

MODEL = "alibaba/z-image-turbo/text-to-image"
PROMPTS = [
    "A paper boat on a calm lake",
    "A lighthouse at dusk, watercolor",
    "A cozy reading nook with a sleeping cat",
]


async def render(client: AsyncPopNow, i: int, prompt: str) -> None:
    try:
        task = await client.images.generate(model=MODEL, prompt=prompt, idempotency_key=f"batch-demo-{i}")
    except TaskFailedError as err:
        print(i, "failed:", err.error_code)
        return
    path = await client.files.download(task.assets[0], f"batch-{i}.png")
    print(i, "saved", path)


async def main() -> None:
    async with AsyncPopNow() as client:
        await asyncio.gather(*(render(client, i, p) for i, p in enumerate(PROMPTS, start=1)))


asyncio.run(main())
