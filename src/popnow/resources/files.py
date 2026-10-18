"""File uploads (upload-url -> PUT -> commit), LoRA imports and result downloads."""

from __future__ import annotations

import io
import mimetypes
import os
import pathlib
from typing import IO, TYPE_CHECKING, Any, AsyncIterator, Dict, Optional, Tuple, Union
from urllib.parse import quote, urlparse

import httpx

from .._exceptions import APIConnectionError, APIError, APITimeoutError
from ..types import DownloadURL, OutputAsset, UploadedFile, UploadTicket

if TYPE_CHECKING:  # pragma: no cover
    from .._client import AsyncPopNow, PopNow

__all__ = ["Files", "AsyncFiles", "FileInput", "guess_content_type"]

FileInput = Union[str, "os.PathLike[str]", bytes, IO[bytes]]
Downloadable = Union[str, OutputAsset, DownloadURL]

DEFAULT_UPLOAD_TIMEOUT = 600.0
CHUNK_SIZE = 1024 * 1024

#: Extensions of the media types accepted by ``common/upload-url``.
_EXTENSION_TYPES: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".safetensors": "application/octet-stream",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def guess_content_type(name: Optional[str]) -> Optional[str]:
    """Best-effort media type for a file name, limited to types the API accepts."""
    if not name:
        return None
    ext = os.path.splitext(name)[1].lower()
    if ext in _EXTENSION_TYPES:
        return _EXTENSION_TYPES[ext]
    guessed, _ = mimetypes.guess_type(name)
    return guessed


def _prepare(file: FileInput, content_type: Optional[str]) -> Tuple[Union[bytes, IO[bytes]], int, str, bool]:
    """Return ``(payload, size, content_type, should_close)``."""
    name: Optional[str] = None
    should_close = False
    payload: Union[bytes, IO[bytes]]
    if isinstance(file, (bytes, bytearray, memoryview)):
        payload = bytes(file)
        size = len(payload)
    elif isinstance(file, (str, os.PathLike)):
        path = pathlib.Path(file)
        name = path.name
        size = path.stat().st_size
        payload = open(path, "rb")
        should_close = True
    elif hasattr(file, "read"):
        payload = file
        name = getattr(file, "name", None)
        name = name if isinstance(name, str) else None
        start = file.tell()
        file.seek(0, io.SEEK_END)
        size = file.tell() - start
        file.seek(start)
    else:
        raise TypeError("file must be a path, bytes or a binary file object")
    resolved = content_type or guess_content_type(name)
    if not resolved:
        if should_close and not isinstance(payload, bytes):
            payload.close()
        raise ValueError("Could not infer content_type; pass content_type='image/png' (for example)")
    if size <= 0:
        if should_close and not isinstance(payload, bytes):
            payload.close()
        raise ValueError("Cannot upload an empty file")
    return payload, size, resolved, should_close


def _put_headers(ticket: UploadTicket, size: int, content_type: str, user_agent: str) -> Dict[str, str]:
    # Send every header from the ticket exactly as given - they are part of the signature.
    headers = {str(k): str(v) for k, v in (ticket.headers or {}).items()}
    lower = {k.lower() for k in headers}
    if "content-type" not in lower:
        headers["Content-Type"] = content_type
    if "content-length" not in lower:
        headers["Content-Length"] = str(size)
    if "user-agent" not in lower:
        headers["User-Agent"] = user_agent
    return headers


def _check_put(response: httpx.Response) -> None:
    if not response.is_success:
        raise APIError(
            f"Upload PUT failed: HTTP {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
            headers=response.headers,
        )


def _resolve_url(target: Downloadable) -> Tuple[str, Optional[str]]:
    if isinstance(target, str):
        return target, None
    if isinstance(target, OutputAsset):
        if not target.url:
            raise ValueError("This output asset has no URL (pending, unavailable or deleted)")
        return target.url, target.mime
    return target.url, None


def _destination(dest: Union[str, "os.PathLike[str]"], url: str) -> pathlib.Path:
    path = pathlib.Path(dest)
    if path.is_dir():
        name = os.path.basename(urlparse(url).path) or "output"
        path = path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _ticket_body(content_type: str, size: int) -> Dict[str, Any]:
    return {"contentType": content_type, "bytes": size}


def _commit_path(file_id: str) -> str:
    return f"/api/v1/files/{quote(file_id, safe='')}/commit"


def _import_body(url: str, token: Optional[str]) -> Dict[str, Any]:
    body: Dict[str, Any] = {"url": url}
    if token:
        body["token"] = token
    return body


class Files:
    """``client.files``."""

    def __init__(self, client: "PopNow") -> None:
        self._client = client

    def create_upload_url(self, *, content_type: str, bytes: int) -> UploadTicket:
        """Step 1: ask for a presigned upload ticket for exactly ``bytes`` bytes."""
        result = self._client._request("POST", "/api/v1/common/upload-url", json=_ticket_body(content_type, bytes))
        return UploadTicket.from_dict(result.data)

    def commit(self, file_id: str) -> UploadedFile:
        """Step 3: verify the uploaded bytes and get the ``popnow://f/...`` URI. Idempotent."""
        result = self._client._request("POST", _commit_path(file_id))
        return UploadedFile.from_dict(result.data)

    def upload(
        self,
        file: FileInput,
        *,
        content_type: Optional[str] = None,
        timeout: float = DEFAULT_UPLOAD_TIMEOUT,
    ) -> UploadedFile:
        """Upload a local file (path, bytes or binary file object) and commit it.

        Returns the committed file; put ``.uri`` in a model's media field, for
        example ``{"image_url": uploaded.uri}``. Uploads are temporary: see
        ``expires_at``, or save the file to the asset library to keep it.
        """
        payload, size, resolved, should_close = _prepare(file, content_type)
        try:
            ticket = self.create_upload_url(content_type=resolved, bytes=size)
            try:
                response = self._client._http.request(
                    ticket.method or "PUT",
                    ticket.upload_url,
                    content=payload,
                    headers=_put_headers(ticket, size, resolved, self._client.user_agent),
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise APITimeoutError("Upload timed out") from exc
            except httpx.TransportError as exc:
                raise APIConnectionError(f"Upload failed: {exc}") from exc
            _check_put(response)
        finally:
            if should_close and not isinstance(payload, bytes):
                payload.close()
        return self.commit(ticket.file_id)

    def import_lora(self, url: str, *, token: Optional[str] = None) -> UploadedFile:
        """Import a ``.safetensors`` LoRA file from a Hugging Face repo id, page or direct HTTPS link.

        ``token`` (a Hugging Face token or Civitai key) is used once and never stored.
        Put the returned ``uri`` in ``loras[].path``.
        """
        result = self._client._request("POST", "/api/v1/files/import", json=_import_body(url, token))
        return UploadedFile.from_dict(result.data)

    def download(
        self,
        target: Downloadable,
        dest: Union[str, "os.PathLike[str]"],
        *,
        timeout: float = DEFAULT_UPLOAD_TIMEOUT,
    ) -> pathlib.Path:
        """Stream a signed output URL to ``dest`` (a file path or an existing directory).

        The API key is never sent: the signed link itself is the permission.
        """
        url, _ = _resolve_url(target)
        path = _destination(dest, url)
        try:
            ua = {"User-Agent": self._client.user_agent}
            with self._client._http.stream("GET", url, headers=ua, timeout=timeout) as response:
                if not response.is_success:
                    response.read()
                    raise APIError(
                        f"Download failed: HTTP {response.status_code}",
                        status_code=response.status_code,
                        headers=response.headers,
                    )
                with open(path, "wb") as fh:
                    for chunk in response.iter_bytes(CHUNK_SIZE):
                        fh.write(chunk)
        except httpx.TimeoutException as exc:
            raise APITimeoutError("Download timed out") from exc
        except httpx.TransportError as exc:
            raise APIConnectionError(f"Download failed: {exc}") from exc
        return path


async def _aiter_file(fh: IO[bytes]) -> AsyncIterator[bytes]:
    while True:
        chunk = fh.read(CHUNK_SIZE)
        if not chunk:
            return
        yield chunk


class AsyncFiles:
    """``client.files`` on :class:`~popnow.AsyncPopNow`."""

    def __init__(self, client: "AsyncPopNow") -> None:
        self._client = client

    async def create_upload_url(self, *, content_type: str, bytes: int) -> UploadTicket:
        result = await self._client._request(
            "POST", "/api/v1/common/upload-url", json=_ticket_body(content_type, bytes)
        )
        return UploadTicket.from_dict(result.data)

    async def commit(self, file_id: str) -> UploadedFile:
        result = await self._client._request("POST", _commit_path(file_id))
        return UploadedFile.from_dict(result.data)

    async def upload(
        self,
        file: FileInput,
        *,
        content_type: Optional[str] = None,
        timeout: float = DEFAULT_UPLOAD_TIMEOUT,
    ) -> UploadedFile:
        payload, size, resolved, should_close = _prepare(file, content_type)
        try:
            ticket = await self.create_upload_url(content_type=resolved, bytes=size)
            content: Any = payload if isinstance(payload, bytes) else _aiter_file(payload)
            try:
                response = await self._client._http.request(
                    ticket.method or "PUT",
                    ticket.upload_url,
                    content=content,
                    headers=_put_headers(ticket, size, resolved, self._client.user_agent),
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                raise APITimeoutError("Upload timed out") from exc
            except httpx.TransportError as exc:
                raise APIConnectionError(f"Upload failed: {exc}") from exc
            _check_put(response)
        finally:
            if should_close and not isinstance(payload, bytes):
                payload.close()
        return await self.commit(ticket.file_id)

    async def import_lora(self, url: str, *, token: Optional[str] = None) -> UploadedFile:
        result = await self._client._request("POST", "/api/v1/files/import", json=_import_body(url, token))
        return UploadedFile.from_dict(result.data)

    async def download(
        self,
        target: Downloadable,
        dest: Union[str, "os.PathLike[str]"],
        *,
        timeout: float = DEFAULT_UPLOAD_TIMEOUT,
    ) -> pathlib.Path:
        url, _ = _resolve_url(target)
        path = _destination(dest, url)
        try:
            ua = {"User-Agent": self._client.user_agent}
            async with self._client._http.stream("GET", url, headers=ua, timeout=timeout) as response:
                if not response.is_success:
                    await response.aread()
                    raise APIError(
                        f"Download failed: HTTP {response.status_code}",
                        status_code=response.status_code,
                        headers=response.headers,
                    )
                with open(path, "wb") as fh:
                    async for chunk in response.aiter_bytes(CHUNK_SIZE):
                        fh.write(chunk)
        except httpx.TimeoutException as exc:
            raise APITimeoutError("Download timed out") from exc
        except httpx.TransportError as exc:
            raise APIConnectionError(f"Download failed: {exc}") from exc
        return path
