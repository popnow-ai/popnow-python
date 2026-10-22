from __future__ import annotations

import json
import pathlib

import pytest
import respx

import popnow
from popnow import PopNow

from .conftest import BASE, envelope, task_record


def _terminal(state: str = "succeeded", **extra: object) -> respx.MockResponse:
    return respx.MockResponse(200, json=envelope(task_record(state, **extra)))


def test_images_generate_builds_input_and_passes_options(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/createTask").mock(return_value=_terminal())
    task = client.images.generate(
        model="alibaba/z-image-turbo/text-to-image",
        prompt="A small red fox curled up in a teacup",
        aspect_ratio="1:1",
        seed=None,
        idempotency_key="fox-1",
        callback_url="https://your-app.example.com/hooks/popnow",
    )
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body == {
        "model": "alibaba/z-image-turbo/text-to-image",
        "input": {"prompt": "A small red fox curled up in a teacup", "aspect_ratio": "1:1"},
        "callBackUrl": "https://your-app.example.com/hooks/popnow",
    }
    assert request.headers["idempotency-key"] == "fox-1"
    assert request.url.params["wait"] == "60"
    assert task.urls == ["https://media.example.com/signed/out_0.png"]


def test_generate_raises_task_failed(mock: respx.MockRouter, client: PopNow) -> None:
    mock.post(f"{BASE}/api/v1/jobs/createTask").mock(
        return_value=_terminal("failed", errorCode="content_rejected", errorMessage="The model declined this content")
    )
    with pytest.raises(popnow.TaskFailedError) as info:
        client.images.generate(model="alibaba/z-image-turbo/text-to-image", prompt="p")
    assert info.value.error_code == "content_rejected"
    assert info.value.task.state == "failed"


def test_videos_generate_polls_after_server_wait(mock: respx.MockRouter, client: PopNow) -> None:
    create = mock.post(f"{BASE}/api/v1/jobs/createTask").respond(
        202,
        json=envelope(
            {"taskId": "job_1", "state": "queued", "estimatedCredits": 34, "estimatedCost": "0.034", "deadlineAt": "x"}
        ),
    )
    mock.get(f"{BASE}/api/v1/jobs/recordInfo").mock(side_effect=[_terminal("running"), _terminal("succeeded")])
    task = client.videos.generate(
        model="alibaba/wan-3.0/image-to-video",
        image_url="https://media.popnow.ai/movie/lighthouse.webp",
        prompt="Waves roll in slowly",
        resolution="480p",
        duration_seconds=5,
    )
    assert json.loads(create.calls.last.request.content)["input"] == {
        "prompt": "Waves roll in slowly",
        "image_url": "https://media.popnow.ai/movie/lighthouse.webp",
        "duration_seconds": 5,
        "resolution": "480p",
    }
    assert task.is_succeeded


def test_local_path_media_is_uploaded_first(mock: respx.MockRouter, client: PopNow, tmp_path: pathlib.Path) -> None:
    photo = tmp_path / "photo.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\n")
    mock.post(f"{BASE}/api/v1/common/upload-url").respond(
        200,
        json=envelope(
            {
                "fileId": "fil_9",
                "key": "popnow://f/fil_9",
                "uploadUrl": "https://uploads.example.com/fil_9",
                "method": "PUT",
                "headers": {},
                "expiresAt": "x",
                "maxBytes": 8,
            }
        ),
    )
    mock.put("https://uploads.example.com/fil_9").respond(200)
    mock.post(f"{BASE}/api/v1/files/fil_9/commit").respond(
        200, json=envelope({"fileId": "fil_9", "status": "ready", "uri": "popnow://f/fil_9", "bytes": 8})
    )
    create = mock.post(f"{BASE}/api/v1/jobs/createTask").mock(return_value=_terminal())
    client.images.edit(model="google/nano-banana-2.1/edit", prompt="Make it night", image_urls=[photo])
    assert json.loads(create.calls.last.request.content)["input"] == {
        "prompt": "Make it night",
        "image_urls": ["popnow://f/fil_9"],
    }


def test_audio_helpers_map_fields(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/createTask").mock(return_value=_terminal(output={"text": "hi", "assets": []}))

    client.audio.speech(model="google/gemini-3.8-flash-tts/text-to-speech", text="Hello", voice_id="Kore")
    assert json.loads(route.calls.last.request.content)["input"] == {"text": "Hello", "voice_id": "Kore"}

    client.audio.music(model="suno/v6/text-to-audio", prompt="Lo-fi beat", instrumental=True)
    assert json.loads(route.calls.last.request.content)["input"] == {"prompt": "Lo-fi beat", "instrumental": True}

    task = client.audio.transcribe(model="xai/grok-stt/speech-to-text", audio_url="https://example.com/a.mp3")
    assert json.loads(route.calls.last.request.content)["input"] == {"audio_url": "https://example.com/a.mp3"}
    assert task.text == "hi"
