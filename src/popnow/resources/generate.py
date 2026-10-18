"""Convenience helpers that create a task and wait for its result.

Each helper is a thin layer over ``jobs.create`` + ``jobs.wait``: it fills the
shared input field names (``prompt``, ``text``, ``image_url``, ``image_urls``,
``video_url``, ``audio_url`` ...) and passes every other keyword argument
through unchanged as a model input field. Fields a model does not declare are
rejected by the API with a 400, so check ``client.models.get(model).input_schema``.

Media fields accept a URL string, a ``popnow://`` URI, or a :class:`pathlib.Path`
to a local file, which is uploaded first.
"""

from __future__ import annotations

import os
import pathlib
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

from .._exceptions import TaskFailedError
from ..types import Task
from .jobs import DEFAULT_WAIT_TIMEOUT

if TYPE_CHECKING:  # pragma: no cover
    from .._client import AsyncPopNow, PopNow

__all__ = ["Images", "Videos", "Audio", "AsyncImages", "AsyncVideos", "AsyncAudio"]

_CREATE_OPTIONS = ("callback_url", "idempotency_key", "quote_id", "expected_credits", "expected_cost", "retention_seconds")


def _split(fields: Mapping[str, Any], params: Dict[str, Any]) -> "tuple[Dict[str, Any], Dict[str, Any]]":
    options = {k: params.pop(k) for k in _CREATE_OPTIONS if k in params}
    model_input = {k: v for k, v in {**fields, **params}.items() if v is not None}
    return model_input, options


def _is_local(value: Any) -> bool:
    return isinstance(value, pathlib.PurePath) or (isinstance(value, os.PathLike) and not isinstance(value, str))


def _ensure_success(task: Task) -> Task:
    if not task.is_succeeded:
        raise TaskFailedError(task)
    return task


class _SyncGenerator:
    def __init__(self, client: "PopNow") -> None:
        self._client = client

    def _resolve_media(self, model_input: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, value in model_input.items():
            if _is_local(value):
                out[key] = self._client.files.upload(value).uri
            elif isinstance(value, (list, tuple)) and any(_is_local(v) for v in value):
                out[key] = [self._client.files.upload(v).uri if _is_local(v) else v for v in value]
            else:
                out[key] = value
        return out

    def _run(self, model: str, fields: Mapping[str, Any], params: Dict[str, Any], timeout: Optional[float]) -> Task:
        model_input, options = _split(fields, params)
        task = self._client.jobs.create_and_wait(
            model=model, input=self._resolve_media(model_input), timeout=timeout, **options
        )
        return _ensure_success(task)


class _AsyncGenerator:
    def __init__(self, client: "AsyncPopNow") -> None:
        self._client = client

    async def _resolve_media(self, model_input: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, value in model_input.items():
            if _is_local(value):
                out[key] = (await self._client.files.upload(value)).uri
            elif isinstance(value, (list, tuple)) and any(_is_local(v) for v in value):
                out[key] = [(await self._client.files.upload(v)).uri if _is_local(v) else v for v in value]
            else:
                out[key] = value
        return out

    async def _run(
        self, model: str, fields: Mapping[str, Any], params: Dict[str, Any], timeout: Optional[float]
    ) -> Task:
        model_input, options = _split(fields, params)
        task = await self._client.jobs.create_and_wait(
            model=model, input=await self._resolve_media(model_input), timeout=timeout, **options
        )
        return _ensure_success(task)


class Images(_SyncGenerator):
    """``client.images``."""

    def generate(
        self, *, model: str, prompt: str, timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT, **params: Any
    ) -> Task:
        """Text-to-image. Example: ``model="alibaba/z-image-turbo/text-to-image"``.

        Extra keyword arguments (``aspect_ratio``, ``seed`` ...) become model input
        fields; ``callback_url``, ``idempotency_key``, ``retention_seconds``,
        ``quote_id`` and ``expected_credits`` are passed to ``jobs.create``.
        Raises :class:`~popnow.TaskFailedError` unless the task succeeds.
        """
        return self._run(model, {"prompt": prompt}, params, timeout)

    def edit(
        self,
        *,
        model: str,
        prompt: Optional[str] = None,
        image_url: Any = None,
        image_urls: Any = None,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **params: Any,
    ) -> Task:
        """Image editing (``.../edit`` models). Pass ``image_urls`` or ``image_url``, as the model declares."""
        fields = {"prompt": prompt, "image_url": image_url, "image_urls": image_urls}
        return self._run(model, fields, params, timeout)


class Videos(_SyncGenerator):
    """``client.videos``."""

    def generate(
        self,
        *,
        model: str,
        prompt: Optional[str] = None,
        image_url: Any = None,
        video_url: Any = None,
        duration_seconds: Optional[int] = None,
        resolution: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **params: Any,
    ) -> Task:
        """Text-to-video, image-to-video, video-extend ... depending on ``model``.

        Example: ``model="alibaba/wan-3.0/image-to-video", image_url=..., prompt=...``.
        Video usually takes minutes; raise ``timeout`` for long or high-resolution clips.
        """
        fields = {
            "prompt": prompt,
            "image_url": image_url,
            "video_url": video_url,
            "duration_seconds": duration_seconds,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
        return self._run(model, fields, params, timeout)


class Audio(_SyncGenerator):
    """``client.audio``."""

    def speech(
        self,
        *,
        model: str,
        text: str,
        voice_id: Optional[str] = None,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **params: Any,
    ) -> Task:
        """Text-to-speech. Example: ``model="google/gemini-3.8-flash-tts/text-to-speech", voice_id="Kore"``."""
        return self._run(model, {"text": text, "voice_id": voice_id}, params, timeout)

    def music(
        self, *, model: str, prompt: str, timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT, **params: Any
    ) -> Task:
        """Music and sound (``text-to-audio`` models), for example ``"suno/v6/text-to-audio"``."""
        return self._run(model, {"prompt": prompt}, params, timeout)

    def transcribe(
        self, *, model: str, audio_url: Any, timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT, **params: Any
    ) -> Task:
        """Speech-to-text. The transcript is in ``task.text`` (``output.text``)."""
        return self._run(model, {"audio_url": audio_url}, params, timeout)


class AsyncImages(_AsyncGenerator):
    async def generate(
        self, *, model: str, prompt: str, timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT, **params: Any
    ) -> Task:
        return await self._run(model, {"prompt": prompt}, params, timeout)

    async def edit(
        self,
        *,
        model: str,
        prompt: Optional[str] = None,
        image_url: Any = None,
        image_urls: Any = None,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **params: Any,
    ) -> Task:
        fields = {"prompt": prompt, "image_url": image_url, "image_urls": image_urls}
        return await self._run(model, fields, params, timeout)


class AsyncVideos(_AsyncGenerator):
    async def generate(
        self,
        *,
        model: str,
        prompt: Optional[str] = None,
        image_url: Any = None,
        video_url: Any = None,
        duration_seconds: Optional[int] = None,
        resolution: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **params: Any,
    ) -> Task:
        fields = {
            "prompt": prompt,
            "image_url": image_url,
            "video_url": video_url,
            "duration_seconds": duration_seconds,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
        return await self._run(model, fields, params, timeout)


class AsyncAudio(_AsyncGenerator):
    async def speech(
        self,
        *,
        model: str,
        text: str,
        voice_id: Optional[str] = None,
        timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT,
        **params: Any,
    ) -> Task:
        return await self._run(model, {"text": text, "voice_id": voice_id}, params, timeout)

    async def music(
        self, *, model: str, prompt: str, timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT, **params: Any
    ) -> Task:
        return await self._run(model, {"prompt": prompt}, params, timeout)

    async def transcribe(
        self, *, model: str, audio_url: Any, timeout: Optional[float] = DEFAULT_WAIT_TIMEOUT, **params: Any
    ) -> Task:
        return await self._run(model, {"audio_url": audio_url}, params, timeout)
