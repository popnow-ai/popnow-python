---
name: popnow-python-sdk
description: Integrate the PopNow Python SDK (pip install popnow) into an app or script - generate AI images, videos, music, speech and transcriptions with exact USD quotes, idempotency keys, waiting, uploads, the async client and webhook verification. Use when writing or reviewing Python code that calls the PopNow API.
---

# PopNow Python SDK

## Install

```bash
pip install popnow
export POPNOW_API_KEY="sk-popnow-..."
```

Keep the key in an environment variable or secret store, never in source. The API balance is prepaid in USD (https://popnow.ai/api/console/billing) and separate from popnow.ai website credits.

## Quick generation

```python
from popnow import PopNow

client = PopNow()  # reads POPNOW_API_KEY
task = client.images.generate(
    model="alibaba/z-image-turbo/text-to-image",
    prompt="A small red fox curled up in a teacup, soft morning light",
)
print(task.state, task.cost_usd, task.urls[0])
client.files.download(task.assets[0], "fox.png")
```

High-level helpers (`client.images.generate`, `client.videos.generate`, `client.audio.music`, `client.audio.speech`, `client.audio.transcribe`) fill the shared fields (`prompt`, `text`, `image_url`, `image_urls`, `video_url`, `audio_url`, `duration_seconds`, `resolution`, `aspect_ratio`), pass other keywords into the model input, wait, and raise `TaskFailedError` unless the task succeeds. A `pathlib.Path` passed as `image_url` is uploaded for you.

## Quote, then create with a locked price

```python
from popnow import PopNow, new_idempotency_key

client = PopNow()
body = {"model": "alibaba/wan-3.0/image-to-video",
        "input": {"image_url": "https://media.popnow.ai/movie/lighthouse.webp", "resolution": "720p", "duration_seconds": 5}}
quote = client.jobs.quote(**body)                     # nothing is created or held
created = client.jobs.create(
    **body,
    idempotency_key=new_idempotency_key(),            # reuse it on every retry of this work
    quote_id=quote.quote_id,
    expected_cost_usd=quote.max_charge_usd,           # QuoteMismatchError if the price changed
)
task = client.jobs.wait(created, timeout=1800)
print(task.state, task.cost_usd, task.urls)
```

Amounts are exact decimal strings; keep them as strings or `Decimal`. `output.assets[].url` is a signed link valid for about 20 minutes, so store the `task_id`.

## Uploads and assets

```python
uploaded = client.files.upload("reference.png")                          # popnow://f/fil_...
asset = client.assets.save_upload(uploaded.file_id, name="Product shot")  # popnow://a/ast_...
```

## Async

```python
from popnow import AsyncPopNow

async with AsyncPopNow() as client:
    task = await client.images.generate(model="alibaba/z-image-turbo/text-to-image", prompt="A paper boat")
```

## Webhooks

```python
from popnow import webhooks, WebhookVerificationError

event = webhooks.verify_task_callback(raw_body, headers, os.environ["POPNOW_WEBHOOK_SECRET"])
task = webhooks.task_from_event(event)
```

Pass the raw request bytes. Deduplicate on `event["request_id"]`.

## Errors

Catch `InsufficientBalanceError`, `RateLimitError` and `APIError` from `popnow`. On a timeout, retry with the same idempotency key so the work is not created twice.

## Choosing models

Model paths look like `provider/model/task`, for example `google/nano-banana-2.1/text-to-image`, `bytedance/seedance-2.5/image-to-video` or `suno/v6/text-to-audio`. Read the current catalog and input schemas from the API or https://popnow.ai/api/pricing rather than guessing.

Docs: https://popnow.ai/docs · SDK source: https://github.com/popnow-ai/popnow-python · Support: support@popnow.ai
