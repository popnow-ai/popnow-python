from __future__ import annotations

import json
import pathlib
from typing import List

import pytest
import respx

import popnow
from popnow import AsyncPopNow

from .conftest import API_KEY, BASE, envelope, task_record

pytestmark = pytest.mark.anyio


async def test_async_balance_and_errors(mock: respx.MockRouter, sleeps: List[float]) -> None:
    mock.get(f"{BASE}/api/v1/chat/credit").respond(
        200,
        json=envelope(
            {"available": "1", "held": "0", "total": "1", "availableCredits": 100, "heldCredits": 0, "totalCredits": 100}
        ),
    )
    mock.get(f"{BASE}/api/v1/jobs/recordInfo").respond(404, json=envelope(code=404, msg="Not found"))
    async with AsyncPopNow(api_key=API_KEY) as client:
        balance = await client.account.balance()
        assert balance.available_credits == 100
        with pytest.raises(popnow.NotFoundError):
            await client.jobs.get("job_missing")


async def test_async_retry_and_wait(mock: respx.MockRouter, sleeps: List[float]) -> None:
    create = mock.post(f"{BASE}/api/v1/jobs/createTask").mock(
        side_effect=[
            respx.MockResponse(429, json=envelope(code=429, msg="Slow down"), headers={"Retry-After": "2"}),
            respx.MockResponse(
                202,
                json=envelope(
                    {"taskId": "job_1", "state": "queued", "estimatedCredits": 1, "estimatedCost": "0.01", "deadlineAt": "x"}
                ),
            ),
        ]
    )
    mock.get(f"{BASE}/api/v1/jobs/recordInfo").mock(
        side_effect=[
            respx.MockResponse(200, json=envelope(task_record("running"))),
            respx.MockResponse(200, json=envelope(task_record("succeeded"))),
        ]
    )
    async with AsyncPopNow(api_key=API_KEY) as client:
        task = await client.images.generate(model="alibaba/z-image-turbo/text-to-image", prompt="A paper boat")
    assert task.is_succeeded
    assert create.call_count == 2
    keys = {c.request.headers["idempotency-key"] for c in create.calls}
    assert len(keys) == 1
    assert sleeps[0] == 2.0


async def test_async_iter_and_upload(mock: respx.MockRouter, sleeps: List[float], tmp_path: pathlib.Path) -> None:
    mock.get(f"{BASE}/api/v1/assets").mock(
        side_effect=[
            respx.MockResponse(200, json=envelope({"items": [{"id": "ast_1", "uri": "popnow://a/ast_1"}], "nextCursor": "n"})),
            respx.MockResponse(200, json=envelope({"items": [{"id": "ast_2", "uri": "popnow://a/ast_2"}]})),
        ]
    )
    mock.post(f"{BASE}/api/v1/common/upload-url").respond(
        200,
        json=envelope(
            {
                "fileId": "fil_1",
                "key": "popnow://f/fil_1",
                "uploadUrl": "https://uploads.example.com/fil_1",
                "method": "PUT",
                "headers": {"Content-Type": "audio/mpeg"},
                "expiresAt": "x",
                "maxBytes": 5,
            }
        ),
    )
    put = mock.put("https://uploads.example.com/fil_1").respond(200)
    mock.post(f"{BASE}/api/v1/files/fil_1/commit").respond(
        200, json=envelope({"fileId": "fil_1", "status": "ready", "uri": "popnow://f/fil_1", "bytes": 5})
    )
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"ID3xx")
    async with AsyncPopNow(api_key=API_KEY) as client:
        ids = [a.id async for a in client.assets.iter(kind="image")]
        uploaded = await client.files.upload(audio)
    assert ids == ["ast_1", "ast_2"]
    assert uploaded.uri == "popnow://f/fil_1"
    assert put.calls.last.request.content == b"ID3xx"
    assert put.calls.last.request.headers["content-length"] == "5"


async def test_async_quote_body(mock: respx.MockRouter, sleeps: List[float]) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/quote").respond(
        200, json=envelope({"quoteId": "q", "model": "m", "maxCredits": 5, "expectedCredits": 5})
    )
    async with AsyncPopNow(api_key=API_KEY) as client:
        quote = await client.jobs.quote(model="m", input={"prompt": "x"})
    assert json.loads(route.calls.last.request.content) == {"model": "m", "input": {"prompt": "x"}}
    assert quote.max_credits == 5
