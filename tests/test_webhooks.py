from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from popnow import WebhookVerificationError, webhooks

SECRET = "test-webhook-secret"
NOW = 1787045531


def _callback_body() -> bytes:
    event = {
        "code": 200,
        "msg": "success",
        "data": {
            "taskId": "job_01JH8Z4Q5W2N7R3K9M6P1C0VXD",
            "model": "alibaba/wan-3.0/image-to-video",
            "state": "succeeded",
            "output": {"assets": [{"url": "https://media.example.com/v.mp4", "mime": "video/mp4"}]},
            "credits": 34,
            "cost": "0.034",
            "settled": True,
        },
        "request_id": "whd_01",
    }
    # Deliberately unusual spacing: verification must use the raw bytes.
    return json.dumps(event, indent=1).encode()


def _sign(body: bytes, task_id: str, ts: int, secret: str = SECRET) -> str:
    digest = hashlib.sha256(body).hexdigest()
    mac = hmac.new(secret.encode(), f"{task_id}.{ts}.{digest}".encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


def test_task_callback_valid_signature() -> None:
    body = _callback_body()
    headers = {
        "X-Webhook-Timestamp": str(NOW),
        "X-Webhook-Signature": _sign(body, "job_01JH8Z4Q5W2N7R3K9M6P1C0VXD", NOW),
        "X-Webhook-Payload-Version": "2",
    }
    event = webhooks.verify_task_callback(body, headers, SECRET, now=NOW + 10)
    assert event["request_id"] == "whd_01"
    task = webhooks.task_from_event(event)
    assert task.state == "succeeded" and task.credits == 34


def test_task_callback_headers_are_case_insensitive() -> None:
    body = _callback_body()
    headers = {
        "x-webhook-timestamp": str(NOW),
        "x-webhook-signature": _sign(body, "job_01JH8Z4Q5W2N7R3K9M6P1C0VXD", NOW),
    }
    webhooks.verify_task_callback(body.decode(), headers, SECRET.encode(), now=NOW)


def test_compute_task_signature_matches_reference() -> None:
    body = _callback_body()
    assert webhooks.compute_task_signature(
        secret=SECRET, task_id="job_01JH8Z4Q5W2N7R3K9M6P1C0VXD", timestamp=NOW, payload=body
    ) == _sign(body, "job_01JH8Z4Q5W2N7R3K9M6P1C0VXD", NOW)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body, headers: (body + b" ", headers),  # body changed
        lambda body, headers: (body, {**headers, "X-Webhook-Signature": "AAAA"}),  # wrong signature
        lambda body, headers: (body, {**headers, "X-Webhook-Timestamp": str(NOW - 3600)}),  # stale
        lambda body, headers: (body, {k: v for k, v in headers.items() if k != "X-Webhook-Signature"}),
        lambda body, headers: (b"not json", headers),
    ],
)
def test_task_callback_rejects_tampering(mutate) -> None:  # type: ignore[no-untyped-def]
    body = _callback_body()
    headers = {
        "X-Webhook-Timestamp": str(NOW),
        "X-Webhook-Signature": _sign(body, "job_01JH8Z4Q5W2N7R3K9M6P1C0VXD", NOW),
    }
    body, headers = mutate(body, headers)
    with pytest.raises(WebhookVerificationError):
        webhooks.verify_task_callback(body, headers, SECRET, now=NOW)


def test_task_callback_wrong_secret() -> None:
    body = _callback_body()
    headers = {
        "X-Webhook-Timestamp": str(NOW),
        "X-Webhook-Signature": _sign(body, "job_01JH8Z4Q5W2N7R3K9M6P1C0VXD", NOW, secret="other"),
    }
    with pytest.raises(WebhookVerificationError):
        webhooks.verify_task_callback(body, headers, SECRET, now=NOW)


def test_task_callback_payload_version_1_top_level_task_id() -> None:
    body = json.dumps({"task_id": "job_legacy", "state": "succeeded"}).encode()
    headers = {"X-Webhook-Timestamp": str(NOW), "X-Webhook-Signature": _sign(body, "job_legacy", NOW)}
    assert webhooks.verify_task_callback(body, headers, SECRET, now=NOW)["task_id"] == "job_legacy"


KEY = b"0123456789abcdef0123456789abcdef"
ENDPOINT_SECRET = "whsec_" + base64.b64encode(KEY).decode()


def _endpoint_sig(msg_id: str, ts: int, body: bytes, key: bytes = KEY) -> str:
    mac = hmac.new(key, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode()


def test_endpoint_event_valid_and_rotation() -> None:
    body = json.dumps(
        {"type": "task.succeeded", "data": {"object": {"taskId": "job_1", "state": "succeeded"}}}
    ).encode()
    old = _endpoint_sig("msg_1", NOW, body, key=b"old-key-old-key-old-key-old-key!")
    headers = {
        "webhook-id": "msg_1",
        "webhook-timestamp": str(NOW),
        "webhook-signature": f"{old} {_endpoint_sig('msg_1', NOW, body)}",
    }
    event = webhooks.verify_endpoint_event(body, headers, ENDPOINT_SECRET, now=NOW)
    assert event["type"] == "task.succeeded"
    assert webhooks.task_from_event(event).task_id == "job_1"


def test_endpoint_event_rejects_bad_signature_and_stale_timestamp() -> None:
    body = b'{"type":"task.failed","data":{"object":{}}}'
    good = {"webhook-id": "msg_1", "webhook-timestamp": str(NOW), "webhook-signature": _endpoint_sig("msg_1", NOW, body)}
    with pytest.raises(WebhookVerificationError):
        webhooks.verify_endpoint_event(body, {**good, "webhook-signature": "v1,AAAA"}, ENDPOINT_SECRET, now=NOW)
    with pytest.raises(WebhookVerificationError):
        webhooks.verify_endpoint_event(body, good, ENDPOINT_SECRET, now=NOW + 3600)
    with pytest.raises(WebhookVerificationError):
        webhooks.verify_endpoint_event(body, {**good, "webhook-id": "msg_2"}, ENDPOINT_SECRET, now=NOW)
