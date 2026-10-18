<div align="center">
  <a href="https://popnow.ai">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/popnow-ai/popnow-python/main/assets/popnow-wordmark-light.png">
      <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/popnow-ai/popnow-python/main/assets/popnow-wordmark.png">
      <img alt="PopNow" src="https://raw.githubusercontent.com/popnow-ai/popnow-python/main/assets/popnow-wordmark.png" width="260">
    </picture>
  </a>

  <h1>PopNow Python SDK: AI Video, Image and Music Generation API</h1>

  <p><strong>popnow</strong> is a typed Python client for the PopNow API that turns text, images and audio into AI videos, images, music and speech, using the same models, prices and credits as <a href="https://popnow.ai">popnow.ai</a>.</p>

  <p>
    <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
    <img alt="Python 3.9 to 3.13" src="https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776AB.svg?logo=python&logoColor=white">
    <a href="https://github.com/popnow-ai/popnow-python/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/popnow-ai/popnow-python/actions/workflows/tests.yml/badge.svg"></a>
    <a href="https://popnow.ai"><img alt="Website: popnow.ai" src="https://img.shields.io/badge/site-popnow.ai-ff5a36.svg"></a>
    <a href="https://popnow.ai/docs"><img alt="Docs" src="https://img.shields.io/badge/docs-popnow.ai%2Fdocs-111111.svg"></a>
  </p>
</div>

PopNow is a browser-based AI studio for videos, images and music: image-to-video, text-to-video, AI images, music and speech, one-tap trending video effects and image styles. This SDK wraps its developer API (`https://api.popnow.ai/api/v1`) so you can call Kling, Seedance, Wan, Vidu, MiniMax, Nano Banana, GPT Image, Flux, Suno and more from Python. Credit packs, no subscription; failed runs are refunded. *Make it pop.*

- Sync **and** async clients (`PopNow`, `AsyncPopNow`) built on `httpx`, the only dependency.
- Typed results (`py.typed`) with snake_case attributes, plus the raw JSON on every object.
- One-line helpers: `client.images.generate()`, `client.videos.generate()`, `client.audio.speech()`.
- Safe retries: automatic `Idempotency-Key`, back-off on `429` / `500` / `503` honouring `Retry-After`.
- Local file uploads, asset library, task history, usage, balance and webhook signature verification.

## Quickstart

**1. Install** (Python 3.9+):

```bash
pip install popnow
# or straight from GitHub:
pip install "git+https://github.com/popnow-ai/popnow-python"
```

**2. Create an API key** in the [API console](https://popnow.ai/api/console/keys) and export it:

```bash
export POPNOW_API_KEY="sk-popnow-..."
```

**3. Generate:**

```python
from popnow import PopNow

client = PopNow()  # reads POPNOW_API_KEY

task = client.images.generate(
    model="alibaba/z-image-turbo/text-to-image",
    prompt="A small red fox curled up in a teacup, soft morning light",
)
print(task.state, task.credits, task.urls[0])
client.files.download(task.assets[0], "fox.png")
```

That image costs a couple of credits (1 credit = $0.01). Buy credits on the [pricing page](https://popnow.ai/pricing); API calls and the website share one wallet.

## What you can call

| Area | SDK | API endpoint |
| --- | --- | --- |
| Models and prices | `client.models.list()`, `client.models.get(id)` | `GET /api/v1/models`, `GET /api/v1/models/{model}` |
| Price a request | `client.jobs.quote()` | `POST /api/v1/jobs/quote` |
| Create a task | `client.jobs.create()` | `POST /api/v1/jobs/createTask` |
| Read / wait | `client.jobs.get()`, `client.jobs.wait()` | `GET /api/v1/jobs/recordInfo` |
| Task history | `client.jobs.list()`, `client.jobs.iter()` | `GET /api/v1/jobs` |
| Retry / purge | `client.jobs.retry()`, `client.jobs.purge()` | `POST /api/v1/jobs/retry`, `POST /api/v1/jobs/purge` |
| Download link | `client.jobs.download_url()` | `POST /api/v1/common/download-url` |
| Upload a file | `client.files.upload(path)` | `POST /api/v1/common/upload-url`, `PUT`, `POST /api/v1/files/{id}/commit` |
| Import a LoRA | `client.files.import_lora(url)` | `POST /api/v1/files/import` |
| Asset library | `client.assets.*` | `/api/v1/assets*` |
| Balance / usage | `client.account.balance()`, `client.account.usage()` | `GET /api/v1/chat/credit`, `GET /api/v1/usage` |
| Webhooks | `popnow.webhooks.verify_task_callback()` | `X-Webhook-Signature` header |

### Supported models

Model ids look like `<maker>/<model>/<task>`. Some examples; the live list with prices is `client.models.list()` or [popnow.ai/docs/models](https://popnow.ai/docs/models):

| Kind | Example model ids |
| --- | --- |
| Text-to-image | `alibaba/z-image-turbo/text-to-image`, `google/nano-banana-2.1/text-to-image`, `openai/gpt-image-2/text-to-image`, `black-forest-labs/flux-2-pro/text-to-image`, `bytedance/seedream-5.0-pro/text-to-image` |
| Image editing | `google/nano-banana-2.1/edit`, `openai/gpt-image-2/edit`, `popnow/background-remover-v1/edit` |
| Image-to-video | `alibaba/wan-3.0/image-to-video`, `kling/3.0/image-to-video`, `bytedance/seedance-2.0/image-to-video`, `vidu/q3/image-to-video`, `minimax/h3/image-to-video` |
| Text-to-video | `kling/3.0/text-to-video`, `alibaba/wan-3.0/text-to-video`, `bytedance/seedance-2.0/text-to-video` |
| Music | `suno/v6/text-to-audio`, `minimax/music-3.0/text-to-audio` |
| Speech | `google/gemini-3.8-flash-tts/text-to-speech`, `minimax/speech-2.8-hd/text-to-speech` |
| Transcription | `xai/grok-stt/speech-to-text` |
| Upscaling | `popnow/image-upscaler-v1/upscale`, `popnow/video-upscaler-v1/upscale` |

Every model has its own `input_schema` (`client.models.get(id).input_schema`). Unknown fields are rejected with a `400`, so typos fail fast.

## Usage

### Image to video

```python
import pathlib
from popnow import PopNow

client = PopNow()
task = client.videos.generate(
    model="alibaba/wan-3.0/image-to-video",
    image_url=pathlib.Path("photo.jpg"),  # a Path is uploaded for you; URLs work too
    prompt="Waves roll in slowly, the camera drifts toward the lighthouse",
    resolution="480p",
    duration_seconds=5,
    timeout=1800,
)
client.files.download(task.assets[0], "clip.mp4")
```

### Music, speech and transcription

```python
song = client.audio.music(model="suno/v6/text-to-audio", prompt="Upbeat lo-fi beat for a cooking video", instrumental=True)
voice = client.audio.speech(model="google/gemini-3.8-flash-tts/text-to-speech", text="Welcome back!", voice_id="Kore")
transcript = client.audio.transcribe(model="xai/grok-stt/speech-to-text", audio_url="https://example.com/interview.mp3").text
```

The helpers fill the shared field names (`prompt`, `text`, `image_url`, `image_urls`, `video_url`, `audio_url`, `duration_seconds`, `resolution`, `aspect_ratio`) and pass every other keyword straight into the model `input`. They wait for the result and raise `TaskFailedError` unless the task succeeds.

### Low-level task API

```python
from popnow import PopNow, new_idempotency_key

client = PopNow()
body = {
    "model": "alibaba/wan-3.0/image-to-video",
    "input": {"image_url": "https://media.popnow.ai/movie/lighthouse.webp", "resolution": "720p", "duration_seconds": 5},
}

quote = client.jobs.quote(**body)                 # nothing is created or held
created = client.jobs.create(
    **body,
    idempotency_key=new_idempotency_key(),        # reuse it on every retry of this work
    quote_id=quote.quote_id,
    expected_credits=quote.max_credits,           # QuoteMismatchError (40901) if the price changed
    callback_url="https://your-app.example.com/hooks/popnow",
)
task = client.jobs.wait(created, timeout=1800)    # polls with back-off: 2s, 3s, 4.5s ... up to 15s
if task.is_succeeded:
    print(task.urls)
else:
    print(task.state, task.error_code, task.error_message)
```

- `jobs.create(..., wait=60)` holds the connection up to 60 seconds; if the task finishes in time, `created.task` is the full record.
- `jobs.create_and_wait(model=..., input=...)` combines the server-side wait with polling.
- Task states: `queued`, `running`, then `succeeded`, `failed` or `expired`. Unknown states count as not final.
- `output.assets[].url` is a signed link valid for about 20 minutes. Store the `task_id`, not the link.

### Uploads and the asset library

```python
uploaded = client.files.upload("reference.png")                          # popnow://f/fil_...
asset = client.assets.save_upload(uploaded.file_id, name="Product shot")  # popnow://a/ast_...
for a in client.assets.iter(kind="image", sort="recent"):
    print(a.name, a.uri)
lora = client.files.import_lora("your-name/your-lora-repo", token="hf_...")  # for loras[].path
```

Uploads are temporary; saved assets stay until you delete them. Images up to 10 MiB, video and audio up to 90 MiB (600 seconds), LoRA `.safetensors` up to 2 GiB.

### Async

```python
import asyncio
from popnow import AsyncPopNow

async def main() -> None:
    async with AsyncPopNow() as client:
        balance = await client.account.balance()
        task = await client.images.generate(model="alibaba/z-image-turbo/text-to-image", prompt="A paper boat")
        print(balance.available_credits, task.urls)

asyncio.run(main())
```

### Webhooks

```python
import os
from popnow import webhooks, WebhookVerificationError

def handle(raw_body: bytes, headers: dict) -> int:
    try:
        event = webhooks.verify_task_callback(raw_body, headers, os.environ["POPNOW_WEBHOOK_SECRET"])
    except WebhookVerificationError:
        return 401
    task = webhooks.task_from_event(event)  # event["request_id"] is the stable delivery id
    print(task.task_id, task.state)
    return 200
```

Task callbacks are signed as `base64(HMAC-SHA256(secret, "<taskId>.<timestamp>.<sha256_hex(raw_body)>"))`; timestamps more than five minutes away are rejected. Account endpoints use the Standard Webhooks format: `webhooks.verify_endpoint_event(raw_body, headers, "whsec_...")`. Always verify the raw request bytes.

## Configuration

```python
client = PopNow(
    api_key="sk-popnow-...",           # default: $POPNOW_API_KEY
    base_url="https://api.popnow.ai",  # default: $POPNOW_BASE_URL or this
    timeout=60.0,                      # seconds per request, or an httpx.Timeout
    max_retries=2,                     # network errors and codes 429, 500, 503, 50301
    language="de",                     # Accept-Language for error messages
    http_client=None,                  # bring your own httpx.Client (proxies, mounts)
)
```

Keep keys on your server; never ship them in a browser or mobile app.

## Error handling

Every error response is `{"code", "msg", "request_id"}`. The SDK raises a typed exception chosen by the business `code`:

| Exception | `code` |
| --- | --- |
| `BadRequestError` | `400`, `40003`, `40004` |
| `AuthenticationError` | `401` |
| `InsufficientCreditsError` / `SpendCapExceededError` (both `PaymentRequiredError`) | `40201` / `40202` |
| `PermissionDeniedError` | `403`, `40301`, `40302`, `40303`, `40310` |
| `NotFoundError` | `404` |
| `ConflictError` / `QuoteMismatchError` | `409` / `40901` |
| `PayloadTooLargeError` | `413` |
| `RateLimitError` | `429` (see `err.retry_after`) |
| `InternalServerError` | `500` |
| `ServiceUnavailableError` / `ModelUnavailableError` | `503`, `50302` / `50301` |
| `APIConnectionError` / `APITimeoutError` | no HTTP response |
| `TaskFailedError` | task ended `failed` or `expired` (see `err.error_code`) |
| `WaitTimeoutError` | the local wait budget ran out; the task keeps running |

All API errors carry `code`, `status_code`, `message`, `request_id` and, for some asset and content errors, `reason` (`data.reason`).

```python
from popnow import APIError, InsufficientCreditsError, RateLimitError

try:
    client.jobs.create(model="kling/3.0/text-to-video", input={"prompt": "A koi pond in the rain"})
except InsufficientCreditsError:
    print("Top up at https://popnow.ai/pricing")
except RateLimitError as err:
    print("retry in", err.retry_after, "seconds")
except APIError as err:
    print(err.code, err.message, err.request_id, err.reason)
```

Branch on `code` (and `task.error_code`), never on message text. Quote `request_id` when contacting support.

## Examples

See [`examples/`](examples): `generate_image.py`, `image_to_video.py`, `text_to_speech.py`, `quote_and_create.py`, `async_batch.py`, `save_to_library.py`, `webhook_receiver.py`.

## FAQ

### How do I generate a video from an image with an API in Python?

Call `client.videos.generate(model="alibaba/wan-3.0/image-to-video", image_url=..., prompt=...)`. Pass a public HTTPS URL, a `popnow://` URI, or a `pathlib.Path` to a local photo, which the SDK uploads first. The call waits for the clip and returns the task with a signed download URL.

### How much does the PopNow API cost?

The API uses the same credits and prices as popnow.ai: 1 credit = $0.01, bought in credit packs with no subscription. Each model lists its price in `client.models.get(id).credits`, and `client.jobs.quote()` returns the exact amount for one request. Failed and expired tasks release their hold, so they cost nothing.

### How do I retry an AI generation request without being charged twice?

Send the same `Idempotency-Key` with every retry of one piece of work. The SDK generates one per call and reuses it across its own automatic retries; pass `idempotency_key=` yourself (for example `order-8814-render-1`) to stay safe across process restarts. Keys are remembered for 24 hours.

### Do I have to poll for results?

No. `jobs.wait()` polls with back-off for you, `jobs.create(wait=60)` returns quick results in the same call, and in production you can pass `callback_url` and verify the webhook with `popnow.webhooks.verify_task_callback()`.

### How do I upload a local file to use as a reference image?

`client.files.upload("photo.jpg")` asks for an upload ticket, PUTs the bytes and commits them, then returns a `uri` (`popnow://f/fil_...`) for `image_url` or `image_urls`. To keep a file for reuse, save it with `client.assets.save_upload()`.

### Which AI video and image models can I use from Python?

Kling, Seedance, Wan, Vidu, MiniMax, Nano Banana, GPT Image, Flux, Seedream, Suno and more. Call `client.models.list(modality="video")` for the live list with availability and prices.

### Is there an async Python client for AI video generation?

Yes. `AsyncPopNow` has the same resources and helpers as `PopNow`, with `await`. Combine it with `asyncio.gather` to run many tasks at once within the rate limits.

### Can I use PopNow from an AI assistant instead of code?

Yes. PopNow runs a remote MCP server at `https://api.popnow.ai/mcp` with tools for images, video, music, speech and effects. See [popnow.ai/mcp](https://popnow.ai/mcp).

## Links

- Website: [popnow.ai](https://popnow.ai)
- Docs: [popnow.ai/docs](https://popnow.ai/docs)
- API reference (OpenAPI): [popnow.ai/docs/openapi.yaml](https://popnow.ai/docs/openapi.yaml)
- Pricing: [popnow.ai/pricing](https://popnow.ai/pricing)
- MCP server: [popnow.ai/mcp](https://popnow.ai/mcp)
- llms.txt: [popnow.ai/llms.txt](https://popnow.ai/llms.txt)
- Other PopNow repos: [popnow-mcp](https://github.com/popnow-ai/popnow-mcp), [popnow-skills](https://github.com/popnow-ai/popnow-skills), [popnow-js](https://github.com/popnow-ai/popnow-js), [popnow-api](https://github.com/popnow-ai/popnow-api), [popnow-blender](https://github.com/popnow-ai/popnow-blender)

## Contributing

Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © PopNow
