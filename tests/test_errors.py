from __future__ import annotations

from typing import List, Type

import pytest
import respx

import popnow
from popnow import PopNow

from .conftest import BASE, envelope

CASES = [
    (400, 400, popnow.BadRequestError),
    (400, 40004, popnow.BadRequestError),
    (401, 401, popnow.AuthenticationError),
    (402, 40201, popnow.InsufficientCreditsError),
    (402, 40202, popnow.SpendCapExceededError),
    (403, 40301, popnow.PermissionDeniedError),
    (403, 40310, popnow.PermissionDeniedError),
    (404, 404, popnow.NotFoundError),
    (409, 409, popnow.ConflictError),
    (409, 40901, popnow.QuoteMismatchError),
    (413, 413, popnow.PayloadTooLargeError),
    (503, 50302, popnow.ServiceUnavailableError),
]


@pytest.mark.parametrize("status,code,exc_type", CASES)
def test_error_envelope_maps_to_exception(
    mock: respx.MockRouter, client: PopNow, status: int, code: int, exc_type: Type[popnow.APIError]
) -> None:
    mock.get(f"{BASE}/api/v1/jobs/recordInfo").respond(
        status, json=envelope(code=code, msg="Something went wrong", request_id="req_abc")
    )
    with pytest.raises(exc_type) as info:
        client.jobs.get("job_1")
    err = info.value
    assert isinstance(err, popnow.APIError)
    assert err.code == code
    assert err.status_code == status
    assert err.request_id == "req_abc"
    assert "req_abc" in str(err)


def test_insufficient_credits_is_a_payment_error(mock: respx.MockRouter, client: PopNow) -> None:
    mock.post(f"{BASE}/api/v1/jobs/createTask").respond(402, json=envelope(code=40201, msg="Insufficient balance"))
    with pytest.raises(popnow.PaymentRequiredError) as info:
        client.jobs.create(model="m/x/text-to-image", input={"prompt": "p"})
    assert isinstance(info.value, popnow.InsufficientCreditsError)


def test_reason_is_exposed(mock: respx.MockRouter, client: PopNow) -> None:
    mock.post(f"{BASE}/api/v1/assets").respond(
        400, json={"code": 400, "msg": "Locked", "request_id": "req_1", "data": {"reason": "asset_library_locked"}}
    )
    with pytest.raises(popnow.BadRequestError) as info:
        client.assets.save_url("https://example.com/a.png")
    assert info.value.reason == "asset_library_locked"


def test_rate_limit_retries_after_retry_after(mock: respx.MockRouter, client: PopNow, sleeps: List[float]) -> None:
    route = mock.get(f"{BASE}/api/v1/models").mock(
        side_effect=[
            respx.MockResponse(429, json=envelope(code=429, msg="Too many requests"), headers={"Retry-After": "3"}),
            respx.MockResponse(200, json=envelope({"total": 0, "items": []})),
        ]
    )
    result = client.models.list()
    assert result.total == 0
    assert route.call_count == 2
    assert sleeps == [3.0]


def test_rate_limit_gives_up_after_max_retries(mock: respx.MockRouter, client: PopNow, sleeps: List[float]) -> None:
    route = mock.get(f"{BASE}/api/v1/models").respond(
        429, json=envelope(code=429, msg="Too many requests"), headers={"Retry-After": "1"}
    )
    with pytest.raises(popnow.RateLimitError) as info:
        client.models.list()
    assert route.call_count == 3  # first try + 2 retries (default)
    assert info.value.retry_after == 1.0


def test_model_unavailable_is_retried(mock: respx.MockRouter, client: PopNow, sleeps: List[float]) -> None:
    route = mock.get(f"{BASE}/api/v1/models").mock(
        side_effect=[
            respx.MockResponse(503, json=envelope(code=50301, msg="Unavailable")),
            respx.MockResponse(200, json=envelope({"total": 0, "items": []})),
        ]
    )
    client.models.list()
    assert route.call_count == 2
    assert len(sleeps) == 1 and 0 < sleeps[0] <= 0.5


def test_non_retryable_errors_are_not_retried(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/jobs/createTask").respond(
        503, json=envelope(code=50302, msg="Refunded, retry with a new key")
    )
    with pytest.raises(popnow.ServiceUnavailableError):
        client.jobs.create(model="m/x/text-to-image", input={"prompt": "p"})
    assert route.call_count == 1


def test_network_error_retries_and_then_raises(mock: respx.MockRouter, client: PopNow, sleeps: List[float]) -> None:
    import httpx

    route = mock.get(f"{BASE}/api/v1/chat/credit").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(popnow.APIConnectionError):
        client.account.balance()
    assert route.call_count == 3
    assert len(sleeps) == 2


def test_timeout_maps_to_api_timeout_error(mock: respx.MockRouter, client: PopNow) -> None:
    import httpx

    client.max_retries = 0
    mock.get(f"{BASE}/api/v1/chat/credit").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(popnow.APITimeoutError):
        client.account.balance()


def test_envelope_error_with_http_200(mock: respx.MockRouter, client: PopNow) -> None:
    mock.get(f"{BASE}/api/v1/chat/credit").respond(200, json=envelope(code=401, msg="Missing credentials"))
    with pytest.raises(popnow.AuthenticationError):
        client.account.balance()
