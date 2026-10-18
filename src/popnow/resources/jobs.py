"""Asynchronous generation tasks: quote, create, read, list, wait, retry, purge."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Iterator, Mapping, Optional, Union

from .. import _base_client
from .._base_client import DateLike, Result, format_date
from .._exceptions import WaitTimeoutError
from ..types import DownloadURL, Task, TaskCreated, TaskPage, TaskPurgeResult, TaskQuote, TaskSummary

if TYPE_CHECKING:  # pragma: no cover
    from .._client import AsyncPopNow, PopNow

__all__ = ["Jobs", "AsyncJobs"]

#: Server-side ``wait`` is clamped to this many seconds.
MAX_SERVER_WAIT = 60
DEFAULT_WAIT_TIMEOUT = 900.0
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_MAX_POLL_INTERVAL = 15.0
POLL_BACKOFF = 1.5


def new_idempotency_key() -> str:
    """A fresh random idempotency key. Create it once per logical piece of work."""
    return str(uuid.uuid4())


def _task_body(
    model: str,
    input: Mapping[str, Any],
    callback_url: Optional[str],
    quote_id: Optional[str] = None,
    expected_credits: Optional[int] = None,
    expected_cost: Optional[str] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"model": model, "input": dict(input)}
    if callback_url is not None:
        body["callBackUrl"] = callback_url
    if quote_id is not None:
        body["quoteId"] = quote_id
    if expected_credits is not None:
        body["expectedCredits"] = expected_credits
    if expected_cost is not None:
        body["expectedCost"] = expected_cost
    return body


def _create_headers(idempotency_key: Optional[str], retention_seconds: Optional[int]) -> Dict[str, Optional[str]]:
    return {
        # Always send a key, so the client's own retries can never create a second task.
        "Idempotency-Key": idempotency_key or new_idempotency_key(),
        "X-PopNow-Retention": None if retention_seconds is None else str(int(retention_seconds)),
    }


def _wait_param(wait: Optional[int]) -> Optional[int]:
    if wait is None:
        return None
    wait = int(wait)
    if wait <= 0:
        return None
    return min(wait, MAX_SERVER_WAIT)


def _parse_created(result: Result) -> TaskCreated:
    data = result.data or {}
    created = TaskCreated.from_dict(data)
    # HTTP 200 (only with ?wait=) carries the full terminal task record.
    if result.status_code == 200 and "model" in data:
        created.task = Task.from_dict(data)
    return created


def _list_params(
    from_date: Optional[DateLike],
    to_date: Optional[DateLike],
    state: Optional[str],
    model: Optional[str],
    limit: Optional[int],
    cursor: Optional[str],
) -> Dict[str, Any]:
    return {
        "from": format_date(from_date),
        "to": format_date(to_date),
        "state": state,
        "model": model,
        "limit": limit,
        "cursor": cursor,
    }


def _next_interval(current: float, max_interval: float) -> float:
    return min(max_interval, current * POLL_BACKOFF)


def _task_id(task: Union[str, Task, TaskCreated, TaskSummary]) -> str:
    return task if isinstance(task, str) else task.task_id


class Jobs:
    """``client.jobs``: the native task API under ``/api/v1/jobs``."""

    def __init__(self, client: "PopNow") -> None:
        self._client = client

    def quote(
        self, *, model: str, input: Mapping[str, Any], callback_url: Optional[str] = None
    ) -> TaskQuote:
        """Price a request without creating a task or holding credits.

        Pass the returned ``quote_id`` and ``max_credits`` to :meth:`create`
        (as ``expected_credits``) within five minutes to lock the price.
        """
        result = self._client._request("POST", "/api/v1/jobs/quote", json=_task_body(model, input, callback_url))
        return TaskQuote.from_dict(result.data)

    def create(
        self,
        *,
        model: str,
        input: Mapping[str, Any],
        callback_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        quote_id: Optional[str] = None,
        expected_credits: Optional[int] = None,
        expected_cost: Optional[str] = None,
        retention_seconds: Optional[int] = None,
        wait: Optional[int] = None,
    ) -> TaskCreated:
        """Create an asynchronous generation task.

        Args:
            model: Model id, for example ``"alibaba/wan-3.0/image-to-video"``.
            input: The model's own fields, validated against its input schema.
            callback_url: Public HTTPS URL that receives the finished task.
            idempotency_key: Reuse the same key when retrying the same work.
                One is generated for you when omitted.
            quote_id / expected_credits / expected_cost: Lock a quoted price.
            retention_seconds: Shorten how long outputs and prompt are kept.
            wait: Hold the connection up to this many seconds (max 60). When the
                task finishes in time, ``TaskCreated.task`` holds the full record.
        """
        wait_s = _wait_param(wait)
        result = self._client._request(
            "POST",
            "/api/v1/jobs/createTask",
            params={"wait": wait_s},
            json=_task_body(model, input, callback_url, quote_id, expected_credits, expected_cost),
            headers=_create_headers(idempotency_key, retention_seconds),
            timeout=self._client._effective_timeout(None, extra=float(wait_s or 0)),
        )
        return _parse_created(result)

    def get(self, task_id: str) -> Task:
        """Read one task created by this API key (``jobs/recordInfo``)."""
        result = self._client._request("GET", "/api/v1/jobs/recordInfo", params={"taskId": task_id})
        return Task.from_dict(result.data)

    def list(
        self,
        *,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        state: Optional[str] = None,
        model: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> TaskPage:
        """One page of this key's task history, newest first (metadata only)."""
        result = self._client._request(
            "GET", "/api/v1/jobs", params=_list_params(from_date, to_date, state, model, limit, cursor)
        )
        return TaskPage.from_dict(result.data)

    def iter(
        self,
        *,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        state: Optional[str] = None,
        model: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[TaskSummary]:
        """Iterate every matching task, following ``nextCursor`` with the same filters."""
        cursor: Optional[str] = None
        while True:
            page = self.list(
                from_date=from_date, to_date=to_date, state=state, model=model, limit=limit, cursor=cursor
            )
            yield from page.items
            if not page.has_more or not page.next_cursor:
                return
            cursor = page.next_cursor

    def retry(self, task_id: str, *, idempotency_key: Optional[str] = None) -> TaskCreated:
        """Create a new task from a ``failed`` or ``expired`` one. The source is never changed."""
        result = self._client._request(
            "POST",
            "/api/v1/jobs/retry",
            json={"taskId": task_id},
            headers={"Idempotency-Key": idempotency_key or new_idempotency_key()},
        )
        return _parse_created(result)

    def purge(self, task_id: str) -> TaskPurgeResult:
        """Destroy a finished task's outputs and stored prompt. Billing records are kept."""
        result = self._client._request("POST", "/api/v1/jobs/purge", json={"taskId": task_id})
        return TaskPurgeResult.from_dict(result.data)

    def download_url(self, task_id: str, *, key: Optional[str] = None) -> DownloadURL:
        """Mint a short-lived download URL for one output (the first when ``key`` is omitted)."""
        body: Dict[str, Any] = {"taskId": task_id}
        if key:
            body["key"] = key
        result = self._client._request("POST", "/api/v1/common/download-url", json=body)
        return DownloadURL.from_dict(result.data)

    def wait(
        self,
        task: Union[str, Task, TaskCreated, TaskSummary],
        *,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_poll_interval: float = DEFAULT_MAX_POLL_INTERVAL,
    ) -> Task:
        """Poll ``recordInfo`` until the task is terminal and return it.

        The interval starts at ``poll_interval`` and grows by 1.5x up to
        ``max_poll_interval``. A terminal state is not necessarily success:
        check ``task.state`` (or use the ``generate`` helpers, which raise
        :class:`~popnow.TaskFailedError`). Raises :class:`~popnow.WaitTimeoutError`
        when ``timeout`` seconds pass first; the task keeps running.
        """
        if isinstance(task, TaskCreated) and task.task is not None and task.task.is_terminal:
            return task.task
        if isinstance(task, Task) and task.is_terminal:
            return task
        task_id = _task_id(task)
        deadline = None if timeout is None else time.monotonic() + timeout
        interval = poll_interval
        while True:
            last = self.get(task_id)
            if last.is_terminal:
                return last
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WaitTimeoutError(task_id, timeout or 0, last)
                _base_client._sleep(min(interval, remaining))
            else:
                _base_client._sleep(interval)
            interval = _next_interval(interval, max_poll_interval)

    def create_and_wait(
        self,
        *,
        model: str,
        input: Mapping[str, Any],
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **create_kwargs: Any,
    ) -> Task:
        """:meth:`create` with a server-side wait, then :meth:`wait` until terminal."""
        server_wait = MAX_SERVER_WAIT if timeout is None else max(0, min(MAX_SERVER_WAIT, int(timeout)))
        started = time.monotonic()
        created = self.create(model=model, input=input, wait=server_wait or None, **create_kwargs)
        remaining = None if timeout is None else max(0.0, timeout - (time.monotonic() - started))
        return self.wait(created, timeout=remaining)


class AsyncJobs:
    """``client.jobs`` on :class:`~popnow.AsyncPopNow`."""

    def __init__(self, client: "AsyncPopNow") -> None:
        self._client = client

    async def quote(
        self, *, model: str, input: Mapping[str, Any], callback_url: Optional[str] = None
    ) -> TaskQuote:
        result = await self._client._request(
            "POST", "/api/v1/jobs/quote", json=_task_body(model, input, callback_url)
        )
        return TaskQuote.from_dict(result.data)

    async def create(
        self,
        *,
        model: str,
        input: Mapping[str, Any],
        callback_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        quote_id: Optional[str] = None,
        expected_credits: Optional[int] = None,
        expected_cost: Optional[str] = None,
        retention_seconds: Optional[int] = None,
        wait: Optional[int] = None,
    ) -> TaskCreated:
        wait_s = _wait_param(wait)
        result = await self._client._request(
            "POST",
            "/api/v1/jobs/createTask",
            params={"wait": wait_s},
            json=_task_body(model, input, callback_url, quote_id, expected_credits, expected_cost),
            headers=_create_headers(idempotency_key, retention_seconds),
            timeout=self._client._effective_timeout(None, extra=float(wait_s or 0)),
        )
        return _parse_created(result)

    async def get(self, task_id: str) -> Task:
        result = await self._client._request("GET", "/api/v1/jobs/recordInfo", params={"taskId": task_id})
        return Task.from_dict(result.data)

    async def list(
        self,
        *,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        state: Optional[str] = None,
        model: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> TaskPage:
        result = await self._client._request(
            "GET", "/api/v1/jobs", params=_list_params(from_date, to_date, state, model, limit, cursor)
        )
        return TaskPage.from_dict(result.data)

    async def iter(
        self,
        *,
        from_date: Optional[DateLike] = None,
        to_date: Optional[DateLike] = None,
        state: Optional[str] = None,
        model: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[TaskSummary]:
        cursor: Optional[str] = None
        while True:
            page = await self.list(
                from_date=from_date, to_date=to_date, state=state, model=model, limit=limit, cursor=cursor
            )
            for item in page.items:
                yield item
            if not page.has_more or not page.next_cursor:
                return
            cursor = page.next_cursor

    async def retry(self, task_id: str, *, idempotency_key: Optional[str] = None) -> TaskCreated:
        result = await self._client._request(
            "POST",
            "/api/v1/jobs/retry",
            json={"taskId": task_id},
            headers={"Idempotency-Key": idempotency_key or new_idempotency_key()},
        )
        return _parse_created(result)

    async def purge(self, task_id: str) -> TaskPurgeResult:
        result = await self._client._request("POST", "/api/v1/jobs/purge", json={"taskId": task_id})
        return TaskPurgeResult.from_dict(result.data)

    async def download_url(self, task_id: str, *, key: Optional[str] = None) -> DownloadURL:
        body: Dict[str, Any] = {"taskId": task_id}
        if key:
            body["key"] = key
        result = await self._client._request("POST", "/api/v1/common/download-url", json=body)
        return DownloadURL.from_dict(result.data)

    async def wait(
        self,
        task: Union[str, Task, TaskCreated, TaskSummary],
        *,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_poll_interval: float = DEFAULT_MAX_POLL_INTERVAL,
    ) -> Task:
        if isinstance(task, TaskCreated) and task.task is not None and task.task.is_terminal:
            return task.task
        if isinstance(task, Task) and task.is_terminal:
            return task
        task_id = _task_id(task)
        deadline = None if timeout is None else time.monotonic() + timeout
        interval = poll_interval
        while True:
            last = await self.get(task_id)
            if last.is_terminal:
                return last
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WaitTimeoutError(task_id, timeout or 0, last)
                await _base_client._async_sleep(min(interval, remaining))
            else:
                await _base_client._async_sleep(interval)
            interval = _next_interval(interval, max_poll_interval)

    async def create_and_wait(
        self,
        *,
        model: str,
        input: Mapping[str, Any],
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **create_kwargs: Any,
    ) -> Task:
        server_wait = MAX_SERVER_WAIT if timeout is None else max(0, min(MAX_SERVER_WAIT, int(timeout)))
        started = time.monotonic()
        created = await self.create(model=model, input=input, wait=server_wait or None, **create_kwargs)
        remaining = None if timeout is None else max(0.0, timeout - (time.monotonic() - started))
        return await self.wait(created, timeout=remaining)

