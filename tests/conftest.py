from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

import pytest
import respx

import popnow
from popnow import _base_client

BASE = "https://api.popnow.ai"
API_KEY = "sk-popnow-" + "0" * 48


def envelope(data: Any = None, code: int = 200, msg: str = "success", request_id: str = "req_test") -> Dict[str, Any]:
    body: Dict[str, Any] = {"code": code, "msg": msg, "request_id": request_id}
    if data is not None:
        body["data"] = data
    return body


def task_record(state: str = "succeeded", task_id: str = "job_1", **extra: Any) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "taskId": task_id,
        "model": "alibaba/z-image-turbo/text-to-image",
        "state": state,
        "cost": "0.002",
        "credits": 2,
        "settled": state != "queued" and state != "running",
        "createdAt": "2026-10-16T09:00:00Z",
        "deadlineAt": "2026-10-16T09:40:00Z",
    }
    if state == "succeeded":
        record["output"] = {
            "assets": [
                {
                    "key": "out_0",
                    "url": "https://media.example.com/signed/out_0.png",
                    "mime": "image/png",
                    "width": 1024,
                    "height": 1024,
                    "expiresAt": "2026-10-16T09:20:00Z",
                }
            ]
        }
    record.update(extra)
    return record


@pytest.fixture(autouse=True)
def _no_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's proxy settings out of the mocked transport."""
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> List[float]:
    """Record every back-off sleep instead of actually sleeping."""
    calls: List[float] = []

    def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    async def fake_async_sleep(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(_base_client, "_sleep", fake_sleep)
    monkeypatch.setattr(_base_client, "_async_sleep", fake_async_sleep)
    return calls


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def client(sleeps: List[float], monkeypatch: pytest.MonkeyPatch) -> Iterator[popnow.PopNow]:
    monkeypatch.delenv("POPNOW_BASE_URL", raising=False)
    with popnow.PopNow(api_key=API_KEY) as c:
        yield c


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def header(request: Any, name: str) -> Optional[str]:
    return request.headers.get(name)
