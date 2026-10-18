from __future__ import annotations

import json
from typing import List

import pytest
import respx

import popnow
from popnow import PopNow

from .conftest import BASE, envelope, task_record

MODEL = "alibaba/wan-3.0/image-to-video"
INPUT = {"image_url": "https://media.popnow.ai/movie/lighthouse.webp", "resolution": "480p", "duration_seconds": 5}

CREATED = {
    "taskId": "job_1",
    "state": "queued",
    "estimatedCredits": 34,
    "estimatedCost": "0.34",
    "deadlineAt": "2026-10-16T09:40:00Z",
}


def test_quote(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/quote").respond(
        200,
        json=envelope(
            {
                "quoteId": "q_1",
                "model": MODEL,
                "maxCredits": 68,
                "expectedCredits": 68,
                "estimatedCost": "0.68",
                "maxCharge": "0.68",
                "currency": "USD",
                "quantity": "5",
                "unit": "per_second",
                "expiresAt": "2026-10-16T09:25:00Z",
            }
        ),
    )
    quote = client.jobs.quote(model=MODEL, input=INPUT)
    assert json.loads(route.calls.last.request.content) == {"model": MODEL, "input": INPUT}
    assert quote.quote_id == "q_1"
    assert quote.max_credits == 68
    assert quote.unit == "per_second"


def test_create_sends_body_headers_and_generates_idempotency_key(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/createTask").respond(202, json=envelope(CREATED))
    created = client.jobs.create(
        model=MODEL,
        input=INPUT,
        callback_url="https://your-app.example.com/hooks/popnow",
        quote_id="q_1",
        expected_credits=68,
        retention_seconds=3600,
    )
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body == {
        "model": MODEL,
        "input": INPUT,
        "callBackUrl": "https://your-app.example.com/hooks/popnow",
        "quoteId": "q_1",
        "expectedCredits": 68,
    }
    assert request.headers["idempotency-key"]
    assert request.headers["x-popnow-retention"] == "3600"
    assert "wait" not in request.url.params
    assert created.task_id == "job_1"
    assert created.state == "queued"
    assert created.estimated_credits == 34
    assert created.task is None


def test_create_retries_with_the_same_idempotency_key(
    mock: respx.MockRouter, client: PopNow, sleeps: List[float]
) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/createTask").mock(
        side_effect=[
            respx.MockResponse(500, json=envelope(code=500, msg="Internal error")),
            respx.MockResponse(202, json=envelope(CREATED)),
        ]
    )
    client.jobs.create(model=MODEL, input=INPUT, idempotency_key="order-8814-render-1")
    keys = {call.request.headers["idempotency-key"] for call in route.calls}
    assert keys == {"order-8814-render-1"}
    assert route.call_count == 2

    route.reset()
    route.side_effect = [
        respx.MockResponse(503, json=envelope(code=503, msg="Busy")),
        respx.MockResponse(202, json=envelope(CREATED)),
    ]
    client.jobs.create(model=MODEL, input=INPUT)
    generated = {call.request.headers["idempotency-key"] for call in route.calls}
    assert len(generated) == 1 and route.call_count == 2


def test_create_with_wait_returns_terminal_record(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/createTask").respond(200, json=envelope(task_record("succeeded")))
    created = client.jobs.create(model=MODEL, input=INPUT, wait=120)
    assert route.calls.last.request.url.params["wait"] == "60"  # clamped to the server maximum
    assert created.task is not None
    assert created.task.is_succeeded
    assert created.task.urls == ["https://media.example.com/signed/out_0.png"]
    # wait() short-circuits on an already terminal record.
    assert client.jobs.wait(created) is created.task


def test_get_parses_record(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.get(f"{BASE}/api/v1/jobs/recordInfo").respond(200, json=envelope(task_record("succeeded")))
    task = client.jobs.get("job_1")
    assert route.calls.last.request.url.params["taskId"] == "job_1"
    assert task.task_id == "job_1"
    assert task.credits == 2
    asset = task.assets[0]
    assert asset.mime == "image/png" and asset.width == 1024
    assert asset.expires_at == "2026-10-16T09:20:00Z"


def test_wait_polls_with_backoff_until_terminal(mock: respx.MockRouter, client: PopNow, sleeps: List[float]) -> None:
    route = mock.get(f"{BASE}/api/v1/jobs/recordInfo").mock(
        side_effect=[
            respx.MockResponse(200, json=envelope(task_record("queued"))),
            respx.MockResponse(200, json=envelope(task_record("running"))),
            respx.MockResponse(200, json=envelope(task_record("running"))),
            respx.MockResponse(200, json=envelope(task_record("failed", errorCode="content_rejected", errorMessage="Declined"))),
        ]
    )
    task = client.jobs.wait("job_1", poll_interval=2, max_poll_interval=4)
    assert route.call_count == 4
    assert task.state == "failed"
    assert task.error_code == "content_rejected"
    assert sleeps == [2, 3.0, 4]


def test_wait_times_out(mock: respx.MockRouter, client: PopNow, monkeypatch: pytest.MonkeyPatch) -> None:
    from popnow.resources import jobs as jobs_module

    clock = [1000.0]

    def fake_monotonic() -> float:
        return clock[0]

    def fake_sleep(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr(jobs_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(jobs_module._base_client, "_sleep", fake_sleep)
    mock.get(f"{BASE}/api/v1/jobs/recordInfo").respond(200, json=envelope(task_record("running")))
    with pytest.raises(popnow.WaitTimeoutError) as info:
        client.jobs.wait("job_1", timeout=10, poll_interval=3)
    assert info.value.task_id == "job_1"
    assert info.value.last is not None and info.value.last.state == "running"


def test_create_and_wait(mock: respx.MockRouter, client: PopNow, sleeps: List[float]) -> None:
    create = mock.post(f"{BASE}/api/v1/jobs/createTask").respond(202, json=envelope(CREATED))
    mock.get(f"{BASE}/api/v1/jobs/recordInfo").mock(
        side_effect=[
            respx.MockResponse(200, json=envelope(task_record("running"))),
            respx.MockResponse(200, json=envelope(task_record("succeeded"))),
        ]
    )
    task = client.jobs.create_and_wait(model=MODEL, input=INPUT, timeout=600)
    assert create.calls.last.request.url.params["wait"] == "60"
    assert task.is_succeeded


def test_list_and_iter_follow_cursor(mock: respx.MockRouter, client: PopNow) -> None:
    item = {
        "taskId": "job_1",
        "model": MODEL,
        "state": "failed",
        "cost": "0",
        "credits": 0,
        "settled": True,
        "createdAt": "2026-10-02T00:00:00Z",
        "deadlineAt": "2026-10-02T00:30:00Z",
    }
    route = mock.get(f"{BASE}/api/v1/jobs").mock(
        side_effect=[
            respx.MockResponse(200, json=envelope({"items": [item], "hasMore": True, "nextCursor": "c2"})),
            respx.MockResponse(200, json=envelope({"items": [dict(item, taskId="job_2")], "hasMore": False})),
        ]
    )
    ids = [t.task_id for t in client.jobs.iter(state="failed", from_date="2026-10-01", limit=1)]
    assert ids == ["job_1", "job_2"]
    first, second = (call.request.url.params for call in route.calls)
    assert first["state"] == "failed" and first["from"] == "2026-10-01" and first["limit"] == "1"
    assert "cursor" not in first
    assert second["cursor"] == "c2" and second["state"] == "failed"


def test_retry_purge_and_download_url(mock: respx.MockRouter, client: PopNow) -> None:
    retry = mock.post(f"{BASE}/api/v1/jobs/retry").respond(
        200, json=envelope(dict(CREATED, taskId="job_2", sourceTaskId="job_1"))
    )
    purge = mock.post(f"{BASE}/api/v1/jobs/purge").respond(
        200,
        json=envelope(
            {
                "taskId": "job_1",
                "contentState": "purged",
                "billingRetained": True,
                "mediaDeletionPending": True,
                "purgedAt": "2026-10-16T10:00:00Z",
                "contentRemovedBy": "user",
            }
        ),
    )
    download = mock.post(f"{BASE}/api/v1/common/download-url").respond(
        200, json=envelope({"key": "out_0", "url": "https://media.example.com/x", "expiresAt": "2026-10-16T10:20:00Z"})
    )

    retried = client.jobs.retry("job_1", idempotency_key="retry-1")
    assert json.loads(retry.calls.last.request.content) == {"taskId": "job_1"}
    assert retry.calls.last.request.headers["idempotency-key"] == "retry-1"
    assert retried.task_id == "job_2" and retried.source_task_id == "job_1"

    purged = client.jobs.purge("job_1")
    assert json.loads(purge.calls.last.request.content) == {"taskId": "job_1"}
    assert purged.content_state == "purged" and purged.billing_retained is True

    link = client.jobs.download_url("job_1")
    assert json.loads(download.calls.last.request.content) == {"taskId": "job_1"}
    assert link.url == "https://media.example.com/x"
    client.jobs.download_url("job_1", key="out_0")
    assert json.loads(download.calls.last.request.content) == {"taskId": "job_1", "key": "out_0"}
