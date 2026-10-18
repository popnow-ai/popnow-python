"""Transport layer shared by the sync and async clients."""

from __future__ import annotations

import asyncio
import datetime as _dt
import os
import platform
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Union

import httpx

from ._exceptions import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    PopNowError,
    make_api_error,
)
from ._version import __version__

DEFAULT_BASE_URL = "https://api.popnow.ai"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_RETRIES = 2

#: Business codes worth retrying, as listed in the PopNow error reference.
RETRYABLE_CODES = frozenset({429, 500, 503, 50301})
#: HTTP statuses retried when the body is not a PopNow envelope (proxies, gateways).
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

INITIAL_RETRY_DELAY = 0.5
MAX_RETRY_DELAY = 8.0
MAX_RETRY_AFTER = 60.0

TimeoutTypes = Union[float, httpx.Timeout, None]
DateLike = Union[str, _dt.date]


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


async def _async_sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


@dataclass
class Result:
    """A successful envelope."""

    status_code: int
    data: Any
    request_id: Optional[str]
    headers: httpx.Headers


def format_date(value: Optional[DateLike]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return str(value)


def clean_params(params: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """Drop ``None`` values and encode booleans the way the API expects."""
    if not params:
        return None
    out: Dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        out[key] = value
    return out or None


def parse_response(response: httpx.Response) -> Result:
    """Unwrap the ``{code,msg,data,request_id}`` envelope or raise an :class:`APIError`."""
    header_request_id = response.headers.get("x-request-id")
    try:
        body = response.json()
    except ValueError:
        body = None

    if not isinstance(body, dict) or "code" not in body:
        if response.is_success and body is not None:
            return Result(response.status_code, body, header_request_id, response.headers)
        snippet = response.text[:200] if body is None else str(body)[:200]
        raise make_api_error(
            status_code=response.status_code,
            code=None,
            message=f"HTTP {response.status_code}: {snippet}".rstrip(": "),
            request_id=header_request_id,
            body=body,
            headers=response.headers,
        )

    code = body.get("code")
    request_id = body.get("request_id") or header_request_id
    if code == 200 and response.is_success:
        return Result(response.status_code, body.get("data"), request_id, response.headers)

    raise make_api_error(
        status_code=response.status_code,
        code=code if isinstance(code, int) else None,
        message=str(body.get("msg") or f"HTTP {response.status_code}"),
        request_id=request_id,
        body=body,
        headers=response.headers,
    )


def is_retryable(error: APIError) -> bool:
    if error.code is not None:
        return error.code in RETRYABLE_CODES
    return error.status_code in RETRYABLE_STATUSES


class BaseClient:
    """Configuration and request helpers shared by :class:`PopNow` and :class:`AsyncPopNow`."""

    def __init__(
        self,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout: TimeoutTypes,
        max_retries: int,
        default_headers: Optional[Mapping[str, str]],
        language: Optional[str],
    ) -> None:
        api_key = api_key or os.environ.get("POPNOW_API_KEY")
        if not api_key:
            raise PopNowError(
                "No API key provided. Pass api_key=... or set the POPNOW_API_KEY environment variable. "
                "Create a key at https://popnow.ai/api/console/keys"
            )
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.api_key = api_key
        self.base_url = (base_url or os.environ.get("POPNOW_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.language = language
        self._default_headers = dict(default_headers or {})

    @property
    def user_agent(self) -> str:
        return f"popnow-python/{__version__} httpx/{httpx.__version__} python/{platform.python_version()}"

    def _auth_headers(self, extra: Optional[Mapping[str, Optional[str]]] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.language:
            headers["Accept-Language"] = self.language
        headers.update(self._default_headers)
        headers["Authorization"] = f"Bearer {self.api_key}"
        for key, value in (extra or {}).items():
            if value is not None:
                headers[key] = value
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    @staticmethod
    def _retry_delay(attempt: int, error: Optional[APIError]) -> float:
        if error is not None and error.retry_after is not None:
            return min(error.retry_after, MAX_RETRY_AFTER)
        base: float = min(MAX_RETRY_DELAY, INITIAL_RETRY_DELAY * float(2**attempt))
        return base * (0.75 + random.random() * 0.25)

    def _effective_timeout(self, timeout: TimeoutTypes, extra: float = 0.0) -> TimeoutTypes:
        value = self.timeout if timeout is None else timeout
        if extra and isinstance(value, (int, float)):
            return float(value) + extra
        if extra and isinstance(value, httpx.Timeout) and value.read is not None:
            return httpx.Timeout(
                connect=value.connect, read=value.read + extra, write=value.write, pool=value.pool
            )
        return value


class SyncAPIClient(BaseClient):
    def __init__(self, *, http_client: Optional[httpx.Client] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(follow_redirects=True)

    def close(self) -> None:
        """Close the underlying HTTP connection pool (only if this client created it)."""
        if self._owns_http:
            self._http.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        headers: Optional[Mapping[str, Optional[str]]] = None,
        timeout: TimeoutTypes = None,
        max_retries: Optional[int] = None,
    ) -> Result:
        retries = self.max_retries if max_retries is None else max_retries
        for attempt in range(retries + 1):
            last = attempt >= retries
            try:
                response = self._http.request(
                    method,
                    self._url(path),
                    params=clean_params(params),
                    json=json,
                    headers=self._auth_headers(headers),
                    timeout=self._effective_timeout(timeout),
                )
            except httpx.TimeoutException as exc:
                if last:
                    raise APITimeoutError(f"Request timed out: {method} {path}") from exc
                _sleep(self._retry_delay(attempt, None))
                continue
            except httpx.TransportError as exc:
                if last:
                    raise APIConnectionError(f"Connection error: {method} {path}: {exc}") from exc
                _sleep(self._retry_delay(attempt, None))
                continue
            try:
                return parse_response(response)
            except APIError as err:
                if last or not is_retryable(err):
                    raise
                _sleep(self._retry_delay(attempt, err))
        raise AssertionError("unreachable")  # pragma: no cover


class AsyncAPIClient(BaseClient):
    def __init__(self, *, http_client: Optional[httpx.AsyncClient] = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(follow_redirects=True)

    async def close(self) -> None:
        """Close the underlying HTTP connection pool (only if this client created it)."""
        if self._owns_http:
            await self._http.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
        headers: Optional[Mapping[str, Optional[str]]] = None,
        timeout: TimeoutTypes = None,
        max_retries: Optional[int] = None,
    ) -> Result:
        retries = self.max_retries if max_retries is None else max_retries
        for attempt in range(retries + 1):
            last = attempt >= retries
            try:
                response = await self._http.request(
                    method,
                    self._url(path),
                    params=clean_params(params),
                    json=json,
                    headers=self._auth_headers(headers),
                    timeout=self._effective_timeout(timeout),
                )
            except httpx.TimeoutException as exc:
                if last:
                    raise APITimeoutError(f"Request timed out: {method} {path}") from exc
                await _async_sleep(self._retry_delay(attempt, None))
                continue
            except httpx.TransportError as exc:
                if last:
                    raise APIConnectionError(f"Connection error: {method} {path}: {exc}") from exc
                await _async_sleep(self._retry_delay(attempt, None))
                continue
            try:
                return parse_response(response)
            except APIError as err:
                if last or not is_retryable(err):
                    raise
                await _async_sleep(self._retry_delay(attempt, err))
        raise AssertionError("unreachable")  # pragma: no cover
