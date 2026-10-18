"""Public client classes."""

from __future__ import annotations

from types import TracebackType
from typing import Any, Mapping, Optional, Type

import httpx

from ._base_client import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    AsyncAPIClient,
    Result,
    SyncAPIClient,
    TimeoutTypes,
)
from .resources.account import Account, AsyncAccount
from .resources.assets import Assets, AsyncAssets
from .resources.files import AsyncFiles, Files
from .resources.generate import AsyncAudio, AsyncImages, AsyncVideos, Audio, Images, Videos
from .resources.jobs import AsyncJobs, Jobs
from .resources.models import AsyncModels, Models

__all__ = ["PopNow", "AsyncPopNow"]


class PopNow(SyncAPIClient):
    """Synchronous PopNow API client.

    Args:
        api_key: ``sk-popnow-...``. Defaults to the ``POPNOW_API_KEY`` environment variable.
        base_url: Defaults to ``POPNOW_BASE_URL`` or ``https://api.popnow.ai``.
        timeout: Per-request timeout in seconds (or an ``httpx.Timeout``).
        max_retries: Automatic retries for network errors and retryable codes
            (``429``, ``500``, ``503``, ``50301``), honouring ``Retry-After``.
        language: ``Accept-Language`` for error messages (for example ``"de"``).
        default_headers: Extra headers sent with every API request.
        http_client: Bring your own ``httpx.Client`` (proxies, transports ...).

    Example::

        from popnow import PopNow

        client = PopNow()
        task = client.images.generate(
            model="alibaba/z-image-turbo/text-to-image",
            prompt="A small red fox curled up in a teacup, soft morning light",
        )
        print(task.urls[0])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        language: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            language=language,
            http_client=http_client,
        )
        self.models = Models(self)
        self.jobs = Jobs(self)
        self.files = Files(self)
        self.assets = Assets(self)
        self.account = Account(self)
        self.images = Images(self)
        self.videos = Videos(self)
        self.audio = Audio(self)

    def _request(self, method: str, path: str, **kwargs: Any) -> Result:
        return self.request(method, path, **kwargs)

    def __enter__(self) -> "PopNow":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"PopNow(base_url={self.base_url!r})"


class AsyncPopNow(AsyncAPIClient):
    """Asynchronous PopNow API client. Same arguments and resources as :class:`PopNow`.

    Example::

        import asyncio
        from popnow import AsyncPopNow

        async def main() -> None:
            async with AsyncPopNow() as client:
                balance = await client.account.balance()
                print(balance.available_credits)

        asyncio.run(main())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        language: Optional[str] = None,
        default_headers: Optional[Mapping[str, str]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            language=language,
            http_client=http_client,
        )
        self.models = AsyncModels(self)
        self.jobs = AsyncJobs(self)
        self.files = AsyncFiles(self)
        self.assets = AsyncAssets(self)
        self.account = AsyncAccount(self)
        self.images = AsyncImages(self)
        self.videos = AsyncVideos(self)
        self.audio = AsyncAudio(self)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Result:
        return await self.request(method, path, **kwargs)

    async def __aenter__(self) -> "AsyncPopNow":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncPopNow(base_url={self.base_url!r})"
