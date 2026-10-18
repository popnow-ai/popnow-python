from __future__ import annotations

import json
import re
from typing import List

import httpx
import pytest
import respx

import popnow
from popnow import PopNow

from .conftest import API_KEY, BASE, envelope


def test_reads_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POPNOW_API_KEY", "sk-popnow-from-env")
    client = PopNow()
    assert client.api_key == "sk-popnow-from-env"
    assert client.base_url == "https://api.popnow.ai"


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POPNOW_API_KEY", raising=False)
    with pytest.raises(popnow.PopNowError, match="POPNOW_API_KEY"):
        PopNow()


def test_base_url_from_environment_and_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POPNOW_BASE_URL", "https://staging.example.com/")
    assert PopNow(api_key=API_KEY).base_url == "https://staging.example.com"
    assert PopNow(api_key=API_KEY, base_url="https://x.example.com/").base_url == "https://x.example.com"


def test_sends_auth_user_agent_and_language(mock: respx.MockRouter, sleeps: List[float]) -> None:
    route = mock.get(f"{BASE}/api/v1/chat/credit").respond(
        200,
        json=envelope(
            {
                "available": "12.34",
                "held": "0.66",
                "total": "13.00",
                "availableCredits": 1234,
                "heldCredits": 66,
                "totalCredits": 1300,
            }
        ),
    )
    client = PopNow(api_key=API_KEY, language="de", default_headers={"X-Trace": "abc"})
    balance = client.account.balance()
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    user_agent = request.headers["user-agent"]
    assert re.fullmatch(r"popnow-python/\S+ httpx/\S+ python/\d+\.\d+\.\d+\S*", user_agent), user_agent
    assert request.headers["accept-language"] == "de"
    assert request.headers["x-trace"] == "abc"
    assert balance.available_credits == 1234
    assert balance.total == "13.00"
    assert balance["heldCredits"] == 66


def test_usage_query_parameters(mock: respx.MockRouter, client: PopNow) -> None:
    import datetime

    route = mock.get(f"{BASE}/api/v1/usage").respond(
        200,
        json=envelope(
            {
                "from": "2026-10-01",
                "to": "2026-10-16",
                "currency": "USD",
                "totalCalls": 3,
                "totalSpend": "0.40",
                "totalCredits": 40,
                "days": [{"day": "2026-10-02", "calls": 3, "succeeded": 2, "failed": 1, "spend": "0.40", "credits": 40}],
                "models": [
                    {
                        "model": "alibaba/wan-3.0/image-to-video",
                        "calls": 3,
                        "succeeded": 2,
                        "failed": 1,
                        "spend": "0.40",
                        "credits": 40,
                    }
                ],
            }
        ),
    )
    usage = client.account.usage(from_date=datetime.date(2026, 10, 1), to_date="2026-10-16")
    params = route.calls.last.request.url.params
    assert params["from"] == "2026-10-01"
    assert params["to"] == "2026-10-16"
    assert usage.from_ == "2026-10-01"
    assert usage.total_credits == 40
    assert usage.days[0].failed == 1
    assert usage.models[0].model == "alibaba/wan-3.0/image-to-video"


def test_models_list_and_get(mock: respx.MockRouter, client: PopNow) -> None:
    model = {
        "model": "alibaba/wan-3.0/image-to-video",
        "family": "wan-3.0",
        "displayName": "Wan 3.0",
        "provider": "alibaba",
        "modality": "video",
        "tasks": ["image-to-video"],
        "async": True,
        "taskTimeoutSeconds": 1800,
        "enabled": True,
        "available": True,
        "quantityField": "duration_seconds",
        "version": "v1",
        "availability": "available",
        "badges": ["no_watermark"],
        "relatedModels": [],
        "updatedAt": "2026-10-01T00:00:00Z",
        "credits": {"unit": "per_second", "perUnit": 6.75},
        "inputSchema": {"type": "object", "properties": {"image_url": {"type": "string"}}},
    }
    list_route = mock.get(f"{BASE}/api/v1/models").respond(200, json=envelope({"total": 1, "items": [model]}))
    get_route = mock.get(f"{BASE}/api/v1/models/alibaba/wan-3.0/image-to-video").respond(200, json=envelope(model))

    models = client.models.list(modality="video", include_schema=True)
    params = list_route.calls.last.request.url.params
    assert params["modality"] == "video"
    assert params["includeSchema"] == "1"
    assert "includeExamples" not in params
    assert len(models) == 1 and models.total == 1
    first = next(iter(models))
    assert first.display_name == "Wan 3.0"
    assert first.async_ is True
    assert first.credits == {"unit": "per_second", "perUnit": 6.75}

    one = client.models.get("alibaba/wan-3.0/image-to-video")
    assert get_route.called
    assert one.input_schema is not None and "image_url" in one.input_schema["properties"]


def test_non_json_error_is_mapped_by_status(mock: respx.MockRouter, client: PopNow) -> None:
    mock.get(f"{BASE}/api/v1/models").respond(502, text="<html>Bad gateway</html>")
    client.max_retries = 0
    with pytest.raises(popnow.APIError) as info:
        client.models.list()
    assert info.value.status_code == 502
    assert info.value.code is None
    assert "Bad gateway" in info.value.message


def test_custom_http_client_is_not_closed(mock: respx.MockRouter) -> None:
    http = httpx.Client()
    client = PopNow(api_key=API_KEY, http_client=http)
    client.close()
    assert not http.is_closed
    http.close()


def test_task_object_helpers() -> None:
    from popnow.types import Task

    task = Task.from_dict(
        {
            "taskId": "job_9",
            "model": "xai/grok-stt/speech-to-text",
            "state": "succeeded",
            "output": {"text": "hello world", "assets": []},
            "retention": {"outputsExpireAt": "2026-10-20T00:00:00Z", "promptsExpireAt": "x", "source": "account"},
            "futureField": 1,
        }
    )
    assert task.is_terminal and task.is_succeeded
    assert task.text == "hello world"
    assert task.urls == []
    assert task.retention is not None and task.retention.source == "account"
    assert task.get("futureField") == 1
    assert json.loads(json.dumps(task.to_dict()))["taskId"] == "job_9"

    assert not Task.from_dict({"taskId": "x", "state": "some_new_state"}).is_terminal
