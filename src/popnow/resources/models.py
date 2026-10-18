"""The live model catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import quote

from ..types import Model, ModelList

if TYPE_CHECKING:  # pragma: no cover
    from .._client import AsyncPopNow, PopNow

__all__ = ["Models", "AsyncModels"]


def _list_params(
    modality: Optional[str],
    provider: Optional[str],
    task: Optional[str],
    search: Optional[str],
    include_schema: bool,
    include_examples: bool,
) -> Dict[str, Any]:
    return {
        "modality": modality,
        "provider": provider,
        "task": task,
        "search": search,
        "includeSchema": 1 if include_schema else None,
        "includeExamples": 1 if include_examples else None,
    }


def _model_path(model: str) -> str:
    # Model ids contain slashes (publisher/model/task); the API accepts them as-is.
    return "/api/v1/models/" + quote(model.strip("/"), safe="/")


class Models:
    """``client.models``."""

    def __init__(self, client: "PopNow") -> None:
        self._client = client

    def list(
        self,
        *,
        modality: Optional[str] = None,
        provider: Optional[str] = None,
        task: Optional[str] = None,
        search: Optional[str] = None,
        include_schema: bool = False,
        include_examples: bool = False,
    ) -> ModelList:
        """Every image, video and audio model this key can call, with its credit price.

        Args:
            modality: ``"image"``, ``"video"`` or ``"audio"``.
            provider: Exact model creator id.
            task: Exact task, for example ``"text-to-image"`` or ``"edit"``.
            search: Free-text search (max 128 characters).
            include_schema: Include each model's input JSON Schema.
            include_examples: Include validated example inputs.
        """
        result = self._client._request(
            "GET",
            "/api/v1/models",
            params=_list_params(modality, provider, task, search, include_schema, include_examples),
        )
        return ModelList.from_dict(result.data)

    def get(self, model: str) -> Model:
        """One model including its ``input_schema``. ``model`` may contain slashes."""
        result = self._client._request("GET", _model_path(model))
        return Model.from_dict(result.data)


class AsyncModels:
    """``client.models`` on :class:`~popnow.AsyncPopNow`."""

    def __init__(self, client: "AsyncPopNow") -> None:
        self._client = client

    async def list(
        self,
        *,
        modality: Optional[str] = None,
        provider: Optional[str] = None,
        task: Optional[str] = None,
        search: Optional[str] = None,
        include_schema: bool = False,
        include_examples: bool = False,
    ) -> ModelList:
        result = await self._client._request(
            "GET",
            "/api/v1/models",
            params=_list_params(modality, provider, task, search, include_schema, include_examples),
        )
        return ModelList.from_dict(result.data)

    async def get(self, model: str) -> Model:
        result = await self._client._request("GET", _model_path(model))
        return Model.from_dict(result.data)
