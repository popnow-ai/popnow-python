"""PopNow Python SDK: AI video, image and audio generation on popnow.ai.

Quick use::

    from popnow import PopNow

    client = PopNow()  # reads POPNOW_API_KEY
    task = client.images.generate(
        model="alibaba/z-image-turbo/text-to-image",
        prompt="A paper boat on a calm lake",
    )
    print(task.urls[0])
"""

from . import types, webhooks
from ._client import AsyncPopNow, PopNow
from ._exceptions import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InsufficientCreditsError,
    InternalServerError,
    ModelUnavailableError,
    NotFoundError,
    PayloadTooLargeError,
    PaymentRequiredError,
    PermissionDeniedError,
    PopNowError,
    QuoteMismatchError,
    RateLimitError,
    ServiceUnavailableError,
    SpendCapExceededError,
    TaskFailedError,
    WaitTimeoutError,
    WebhookVerificationError,
)
from ._version import __version__
from .resources.jobs import new_idempotency_key
from .types import (
    Asset,
    Balance,
    Model,
    ModelList,
    OutputAsset,
    Task,
    TaskCreated,
    TaskQuote,
    UploadedFile,
    Usage,
)

__all__ = [
    "__version__",
    "PopNow",
    "AsyncPopNow",
    "new_idempotency_key",
    "types",
    "webhooks",
    # types
    "Asset",
    "Balance",
    "Model",
    "ModelList",
    "OutputAsset",
    "Task",
    "TaskCreated",
    "TaskQuote",
    "UploadedFile",
    "Usage",
    # errors
    "PopNowError",
    "APIError",
    "APIConnectionError",
    "APITimeoutError",
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
