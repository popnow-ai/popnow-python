"""Exception hierarchy.

Every non-success response from the PopNow API uses the envelope
``{"code", "msg", "request_id", "data"?}``. The business ``code`` is more
specific than the HTTP status, so errors are mapped by ``code`` first and by
HTTP status as a fallback.
"""

from __future__ import annotations

import email.utils
import time
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Type

if TYPE_CHECKING:  # pragma: no cover
    from .types import Task

__all__ = [
    "PopNowError",
    "APIConnectionError",
    "APITimeoutError",
    "APIError",
    "BadRequestError",
    "AuthenticationError",
    "PaymentRequiredError",
    "InsufficientCreditsError",
    "SpendCapExceededError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "QuoteMismatchError",
    "PayloadTooLargeError",
    "RateLimitError",
    "InternalServerError",
    "ServiceUnavailableError",
    "ModelUnavailableError",
    "TaskFailedError",
    "WaitTimeoutError",
    "WebhookVerificationError",
]


class PopNowError(Exception):
    """Base class for every error raised by this library."""


class APIConnectionError(PopNowError):
    """The request never produced an HTTP response (DNS, TLS, reset, ...)."""


class APITimeoutError(APIConnectionError):
    """The request timed out on the client side."""


class APIError(PopNowError):
    """The API answered with a non-success envelope or a non-JSON error page.

    Attributes:
        message: The human-readable ``msg``. Never branch on it.
        code: The business ``code`` (for example ``40201``), or ``None`` when the
            response was not a PopNow envelope.
        status_code: The HTTP status.
        request_id: Correlation id; include it when contacting support.
        reason: Machine-readable ``data.reason`` when present
            (for example ``asset_library_locked``).
        body: The decoded JSON body, if any.
        headers: The response headers.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: Optional[int] = None,
        request_id: Optional[str] = None,
        reason: Optional[str] = None,
        body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.reason = reason
        self.body = body
        self.headers: Dict[str, str] = {k.lower(): v for k, v in (headers or {}).items()}

    @property
    def retry_after(self) -> Optional[float]:
        """Seconds from the ``Retry-After`` header, if the server sent one."""
        return parse_retry_after(self.headers.get("retry-after"))

    def __str__(self) -> str:
        parts = [f"code={self.code}" if self.code is not None else None, f"status={self.status_code}"]
        if self.reason:
            parts.append(f"reason={self.reason}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return f"{self.message} ({', '.join(p for p in parts if p)})"


class BadRequestError(APIError):
    """``400``, ``40003`` (upload does not match its ticket) or ``40004`` (unsupported combination)."""


class AuthenticationError(APIError):
    """``401``: missing, malformed, unknown, revoked or expired API key."""


class PaymentRequiredError(APIError):
    """HTTP ``402``."""


class InsufficientCreditsError(PaymentRequiredError):
    """``40201``: the balance cannot cover this task's hold."""


class SpendCapExceededError(PaymentRequiredError):
    """``40202``: a spend cap on this API key was reached."""


class PermissionDeniedError(APIError):
    """``403`` and ``40301`` / ``40302`` / ``40303`` / ``40310``."""


class NotFoundError(APIError):
    """``404``: does not exist, or belongs to another account or API key."""


class ConflictError(APIError):
    """``409``: idempotency or media-transfer state conflict."""


class QuoteMismatchError(ConflictError):
    """``40901``: the quote expired or the price changed. Quote again."""


class PayloadTooLargeError(APIError):
    """``413``: the JSON body is too large. Upload media instead of inlining it."""


class RateLimitError(APIError):
    """``429``: too many requests. Honour :attr:`retry_after`."""


class InternalServerError(APIError):
    """``500``: something broke on the server side."""


class ServiceUnavailableError(APIError):
    """``503`` / ``50302``: a dependency is temporarily unavailable."""


class ModelUnavailableError(ServiceUnavailableError):
    """``50301``: the model cannot take tasks right now."""


class TaskFailedError(PopNowError):
    """A task reached a terminal state other than ``succeeded``.

    Raised by the convenience ``generate`` helpers. ``task`` is the full record;
    branch on :attr:`error_code`, never on :attr:`error_message`.
    """

    def __init__(self, task: "Task") -> None:
        self.task = task
        self.task_id = task.task_id
        self.state = task.state
        self.error_code = task.error_code
        self.error_message = task.error_message
        detail = f": {task.error_code}" if task.error_code else ""
        msg = f"Task {task.task_id} ended in state {task.state!r}{detail}"
        if task.error_message:
            msg += f" ({task.error_message})"
        super().__init__(msg)


class WaitTimeoutError(PopNowError):
    """The local wait budget ran out before the task reached a terminal state.

    The task keeps running on the server; poll it again later with
    ``client.jobs.get(task_id)``.
    """

    def __init__(self, task_id: str, timeout: float, last: Optional["Task"] = None) -> None:
        self.task_id = task_id
        self.timeout = timeout
        self.last = last
        super().__init__(f"Task {task_id} did not finish within {timeout:g} seconds")


class WebhookVerificationError(PopNowError):
    """A webhook delivery failed signature or timestamp verification."""


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        parsed = email.utils.parsedate_tz(value)
        if parsed is None:
            return None
        seconds = email.utils.mktime_tz(parsed) - time.time()
    return max(0.0, seconds)


_CODE_MAP: Dict[int, Type[APIError]] = {
    400: BadRequestError,
    40003: BadRequestError,
    40004: BadRequestError,
    401: AuthenticationError,
    40201: InsufficientCreditsError,
    40202: SpendCapExceededError,
    403: PermissionDeniedError,
    40301: PermissionDeniedError,
    40302: PermissionDeniedError,
    40303: PermissionDeniedError,
    40310: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    40901: QuoteMismatchError,
    413: PayloadTooLargeError,
    429: RateLimitError,
    500: InternalServerError,
    503: ServiceUnavailableError,
    50301: ModelUnavailableError,
    50302: ServiceUnavailableError,
}

_STATUS_MAP: Dict[int, Type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: PaymentRequiredError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    413: PayloadTooLargeError,
    429: RateLimitError,
    500: InternalServerError,
    503: ServiceUnavailableError,
}


def make_api_error(
    *,
    status_code: int,
    code: Optional[int],
    message: str,
    request_id: Optional[str],
    body: Any,
    headers: Optional[Mapping[str, str]],
) -> APIError:
    reason = None
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        raw_reason = body["data"].get("reason")
        reason = raw_reason if isinstance(raw_reason, str) else None
    cls: Type[APIError] = APIError
    if code is not None and code in _CODE_MAP:
        cls = _CODE_MAP[code]
    elif status_code in _STATUS_MAP:
        cls = _STATUS_MAP[status_code]
    elif status_code >= 500:
        cls = InternalServerError
    return cls(
        message,
        status_code=status_code,
        code=code,
        request_id=request_id,
        reason=reason,
        body=body,
        headers=headers,
    )
