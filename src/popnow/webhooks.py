"""Webhook signature verification.

PopNow sends two kinds of webhooks:

* **Task callbacks** (``callBackUrl`` on ``createTask``), signed with the
  account's webhook signing secret::

      X-Webhook-Signature = base64(HMAC-SHA256(secret, f"{taskId}.{timestamp}.{sha256_hex(raw_body)}"))

  Use :func:`verify_task_callback`.

* **Account endpoints** (registered in the API console), in the Standard
  Webhooks format with a ``whsec_...`` secret. Use :func:`verify_endpoint_event`.

Always verify the **raw** request body bytes, never a re-serialized object.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Mapping, Optional, Union

from ._exceptions import WebhookVerificationError
from .types import Task

__all__ = [
    "DEFAULT_TOLERANCE",
    "compute_task_signature",
    "verify_task_callback",
    "verify_endpoint_event",
    "task_from_event",
    "WebhookVerificationError",
]

#: Reject deliveries whose timestamp is further than this from now (seconds).
DEFAULT_TOLERANCE = 300

Payload = Union[bytes, bytearray, str]


def _as_bytes(payload: Payload) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return bytes(payload)


def _header(headers: Mapping[str, Any], name: str) -> Optional[str]:
    wanted = name.lower()
    for key, value in headers.items():
        if str(key).lower() == wanted:
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            return None if value is None else str(value)
    return None


def _check_timestamp(timestamp: Optional[str], tolerance: Optional[float], now: Optional[float]) -> int:
    if not timestamp or not timestamp.strip().isdigit():
        raise WebhookVerificationError("Missing or malformed webhook timestamp")
    ts = int(timestamp.strip())
    if tolerance is not None:
        current = time.time() if now is None else now
        if abs(current - ts) > tolerance:
            raise WebhookVerificationError("Webhook timestamp is outside the allowed tolerance")
    return ts


def _secret_bytes(secret: Union[str, bytes]) -> bytes:
    return secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)


def compute_task_signature(*, secret: Union[str, bytes], task_id: str, timestamp: Union[str, int], payload: Payload) -> str:
    """Return the Base64 ``X-Webhook-Signature`` value for a task callback."""
    digest = hashlib.sha256(_as_bytes(payload)).hexdigest()
    message = f"{task_id}.{timestamp}.{digest}".encode("utf-8")
    return base64.b64encode(hmac.new(_secret_bytes(secret), message, hashlib.sha256).digest()).decode("ascii")


def verify_task_callback(
    payload: Payload,
    headers: Mapping[str, Any],
    secret: Union[str, bytes],
    *,
    tolerance: Optional[float] = DEFAULT_TOLERANCE,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Verify a ``callBackUrl`` delivery and return the decoded envelope.

    Args:
        payload: The raw request body, exactly as received.
        headers: The request headers (any mapping; names are case-insensitive).
        secret: The account webhook signing secret (``POPNOW_WEBHOOK_SECRET``).
        tolerance: Maximum age of ``X-Webhook-Timestamp`` in seconds (``None`` disables the check).

    Returns:
        The envelope ``{"code", "msg", "data", "request_id"}``. ``request_id`` is the
        stable delivery id: store it to ignore duplicate deliveries. Use
        :func:`task_from_event` to turn ``data`` into a :class:`~popnow.types.Task`.

    Raises:
        WebhookVerificationError: bad signature, stale timestamp or malformed body.
    """
    raw = _as_bytes(payload)
    timestamp = _header(headers, "X-Webhook-Timestamp")
    signature = _header(headers, "X-Webhook-Signature")
    if not signature:
        raise WebhookVerificationError("Missing X-Webhook-Signature header")
    _check_timestamp(timestamp, tolerance, now)
    try:
        event = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise WebhookVerificationError("Webhook body is not valid JSON") from exc
    if not isinstance(event, dict):
        raise WebhookVerificationError("Webhook body is not a JSON object")

    data = event.get("data")
    task_id = data.get("taskId") if isinstance(data, dict) else None
    if not task_id:
        # Payload version 1 (older receivers) carries the id at the top level.
        task_id = event.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise WebhookVerificationError("Webhook body has no task id")

    expected = compute_task_signature(secret=secret, task_id=task_id, timestamp=str(timestamp).strip(), payload=raw)
    if not hmac.compare_digest(expected.encode("ascii"), signature.strip().encode("utf-8", "replace")):
        raise WebhookVerificationError("Webhook signature does not match")
    return event


def task_from_event(event: Mapping[str, Any]) -> Task:
    """Build a :class:`~popnow.types.Task` from a verified task callback or endpoint event."""
    data = event.get("data")
    if isinstance(data, dict) and isinstance(data.get("object"), dict):
        data = data["object"]  # Standard Webhooks endpoint event
    return Task.from_dict(data if isinstance(data, dict) else {})


def _endpoint_key(secret: Union[str, bytes]) -> bytes:
    if isinstance(secret, bytes):
        return secret
    value = secret.strip()
    if value.startswith("whsec_"):
        value = value[len("whsec_") :]
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise WebhookVerificationError("Endpoint secret is not valid Base64 after 'whsec_'") from exc


def verify_endpoint_event(
    payload: Payload,
    headers: Mapping[str, Any],
    secret: Union[str, bytes],
    *,
    tolerance: Optional[float] = DEFAULT_TOLERANCE,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Verify an account endpoint delivery (Standard Webhooks) and return the event.

    The signature is ``v1,base64(HMAC-SHA256(key, f"{webhook-id}.{webhook-timestamp}.{raw_body}"))``
    where ``key`` is the Base64-decoded part of the ``whsec_...`` secret. During a
    secret rotation the header may hold several space-separated signatures; any
    match is accepted. ``webhook-id`` is stable across retries: use it to drop duplicates.
    """
    raw = _as_bytes(payload)
    msg_id = _header(headers, "webhook-id")
    timestamp = _header(headers, "webhook-timestamp")
    signature_header = _header(headers, "webhook-signature")
    if not msg_id or not signature_header:
        raise WebhookVerificationError("Missing webhook-id or webhook-signature header")
    _check_timestamp(timestamp, tolerance, now)

    message = msg_id.encode("utf-8") + b"." + str(timestamp).strip().encode("utf-8") + b"." + raw
    expected = base64.b64encode(hmac.new(_endpoint_key(secret), message, hashlib.sha256).digest())
    matched = False
    for candidate in signature_header.split():
        version, _, value = candidate.partition(",")
        if version == "v1" and hmac.compare_digest(expected, value.encode("utf-8", "replace")):
            matched = True
    if not matched:
        raise WebhookVerificationError("Webhook signature does not match")
    try:
        event = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise WebhookVerificationError("Webhook body is not valid JSON") from exc
    if not isinstance(event, dict):
        raise WebhookVerificationError("Webhook body is not a JSON object")
    return event
