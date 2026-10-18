"""The long-term private asset library (``popnow://a/...``) and its characters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, Iterator, Optional, Sequence, Union
from urllib.parse import quote

from ..types import Asset, AssetCharacter, AssetCharacterPage, AssetDeleted, AssetPage, AssetUsage
from .jobs import new_idempotency_key

if TYPE_CHECKING:  # pragma: no cover
    from .._client import AsyncPopNow, PopNow

__all__ = ["Assets", "AsyncAssets"]

SourceFilter = Union[str, Sequence[str], None]


def _list_params(
    kind: Optional[str],
    source: SourceFilter,
    q: Optional[str],
    favorite: Optional[bool],
    collection_id: Optional[str],
    entity_id: Optional[str],
    sort: Optional[str],
    cursor: Optional[str],
    limit: Optional[int],
) -> Dict[str, Any]:
    if source is not None and not isinstance(source, str):
        source = ",".join(source)
    return {
        "kind": kind,
        "source": source,
        "q": q,
        "favorite": favorite,
        "collectionId": collection_id,
        "entityId": entity_id,
        "sort": sort,
        "cursor": cursor,
        "limit": limit,
    }


def _create_body(
    source: str,
    task_id: Optional[str],
    key: Optional[str],
    index: Optional[int],
    file_id: Optional[str],
    url: Optional[str],
    name: Optional[str],
) -> Dict[str, Any]:
    if source not in ("task_output", "upload", "url"):
        raise ValueError("source must be 'task_output', 'upload' or 'url'")
    body: Dict[str, Any] = {"source": source}
    for field_name, value in (
        ("taskId", task_id),
        ("key", key),
        ("index", index),
        ("fileId", file_id),
        ("url", url),
        ("name", name),
    ):
        if value is not None:
            body[field_name] = value
    return body


def _update_body(name: Optional[str], favorite: Optional[bool]) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if favorite is not None:
        body["favorite"] = favorite
    if not body:
        raise ValueError("Pass name and/or favorite")
    return body


def _asset_path(asset_id: str) -> str:
    return f"/api/v1/assets/{quote(asset_id, safe='')}"


def _entity_path(entity_id: str) -> str:
    return f"/api/v1/assets/entities/{quote(entity_id, safe='')}"


class Assets:
    """``client.assets``."""

    def __init__(self, client: "PopNow") -> None:
        self._client = client

    def list(
        self,
        *,
        kind: Optional[str] = None,
        source: SourceFilter = None,
        q: Optional[str] = None,
        favorite: Optional[bool] = None,
        collection_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        sort: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AssetPage:
        """One page of saved assets. ``sort`` is ``recent`` (default), ``oldest``, ``name`` or ``size``."""
        result = self._client._request(
            "GET",
            "/api/v1/assets",
            params=_list_params(kind, source, q, favorite, collection_id, entity_id, sort, cursor, limit),
        )
        return AssetPage.from_dict(result.data)

    def iter(self, **filters: Any) -> Iterator[Asset]:
        """Iterate every asset matching ``filters`` (same arguments as :meth:`list`)."""
        filters.pop("cursor", None)
        cursor: Optional[str] = None
        while True:
            page = self.list(cursor=cursor, **filters)
            yield from page.items
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    def get(self, asset_id: str) -> Asset:
        """One asset with a fresh private ``preview_url`` (valid ~20 minutes)."""
        result = self._client._request("GET", _asset_path(asset_id))
        return Asset.from_dict(result.data)

    def create(
        self,
        *,
        source: str,
        task_id: Optional[str] = None,
        key: Optional[str] = None,
        index: Optional[int] = None,
        file_id: Optional[str] = None,
        url: Optional[str] = None,
        name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Asset:
        """Save a file to the library. Saving the same source again returns the existing asset.

        ``Idempotency-Key`` is required by the API; one is generated when omitted.
        """
        result = self._client._request(
            "POST",
            "/api/v1/assets",
            json=_create_body(source, task_id, key, index, file_id, url, name),
            headers={"Idempotency-Key": idempotency_key or new_idempotency_key()},
        )
        return Asset.from_dict(result.data)

    def save_task_output(
        self,
        task_id: str,
        *,
        index: Optional[int] = None,
        key: Optional[str] = None,
        name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Asset:
        """Save one output of a succeeded task (``index`` defaults to 0)."""
        if index is None and key is None:
            index = 0
        return self.create(
            source="task_output", task_id=task_id, index=index, key=key, name=name, idempotency_key=idempotency_key
        )

    def save_upload(self, file_id: str, *, name: Optional[str] = None, idempotency_key: Optional[str] = None) -> Asset:
        """Save a committed upload (``fil_...`` or ``popnow://f/fil_...``)."""
        return self.create(source="upload", file_id=file_id, name=name, idempotency_key=idempotency_key)

    def save_url(self, url: str, *, name: Optional[str] = None, idempotency_key: Optional[str] = None) -> Asset:
        """Download a public ``http``/``https`` file once and save it."""
        return self.create(source="url", url=url, name=name, idempotency_key=idempotency_key)

    def update(self, asset_id: str, *, name: Optional[str] = None, favorite: Optional[bool] = None) -> Asset:
        """Rename an asset and/or change its favorite mark. The ``uri`` stays the same."""
        result = self._client._request("PATCH", _asset_path(asset_id), json=_update_body(name, favorite))
        return Asset.from_dict(result.data)

    def delete(self, asset_id: str) -> AssetDeleted:
        """Delete an asset; its ``uri`` stops working in new requests. Safe to repeat."""
        result = self._client._request("DELETE", _asset_path(asset_id))
        return AssetDeleted.from_dict(result.data)

    def usage(self) -> AssetUsage:
        """Storage plan, usage, limits and what the next plan unlocks."""
        result = self._client._request("GET", "/api/v1/assets/usage")
        return AssetUsage.from_dict(result.data)

    def list_characters(
        self, *, asset_id: Optional[str] = None, cursor: Optional[str] = None, limit: Optional[int] = None
    ) -> AssetCharacterPage:
        """Characters (named, ordered image sets) in the library, newest first."""
        result = self._client._request(
            "GET",
            "/api/v1/assets/entities",
            params={"assetId": asset_id, "cursor": cursor, "limit": limit},
        )
        return AssetCharacterPage.from_dict(result.data)

    def get_character(self, entity_id: str) -> AssetCharacter:
        """One character with its images in order."""
        result = self._client._request("GET", _entity_path(entity_id))
        return AssetCharacter.from_dict(result.data)


class AsyncAssets:
    """``client.assets`` on :class:`~popnow.AsyncPopNow`."""

    def __init__(self, client: "AsyncPopNow") -> None:
        self._client = client

    async def list(
        self,
        *,
        kind: Optional[str] = None,
        source: SourceFilter = None,
        q: Optional[str] = None,
        favorite: Optional[bool] = None,
        collection_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        sort: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AssetPage:
        result = await self._client._request(
            "GET",
            "/api/v1/assets",
            params=_list_params(kind, source, q, favorite, collection_id, entity_id, sort, cursor, limit),
        )
        return AssetPage.from_dict(result.data)

    async def iter(self, **filters: Any) -> AsyncIterator[Asset]:
        filters.pop("cursor", None)
        cursor: Optional[str] = None
        while True:
            page = await self.list(cursor=cursor, **filters)
            for item in page.items:
                yield item
            if not page.next_cursor:
                return
            cursor = page.next_cursor

    async def get(self, asset_id: str) -> Asset:
        result = await self._client._request("GET", _asset_path(asset_id))
        return Asset.from_dict(result.data)

    async def create(
        self,
        *,
        source: str,
        task_id: Optional[str] = None,
        key: Optional[str] = None,
        index: Optional[int] = None,
        file_id: Optional[str] = None,
        url: Optional[str] = None,
        name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Asset:
        result = await self._client._request(
            "POST",
            "/api/v1/assets",
            json=_create_body(source, task_id, key, index, file_id, url, name),
            headers={"Idempotency-Key": idempotency_key or new_idempotency_key()},
        )
        return Asset.from_dict(result.data)

    async def save_task_output(
        self,
        task_id: str,
        *,
        index: Optional[int] = None,
        key: Optional[str] = None,
        name: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Asset:
        if index is None and key is None:
            index = 0
        return await self.create(
            source="task_output", task_id=task_id, index=index, key=key, name=name, idempotency_key=idempotency_key
        )

    async def save_upload(
        self, file_id: str, *, name: Optional[str] = None, idempotency_key: Optional[str] = None
    ) -> Asset:
        return await self.create(source="upload", file_id=file_id, name=name, idempotency_key=idempotency_key)

    async def save_url(self, url: str, *, name: Optional[str] = None, idempotency_key: Optional[str] = None) -> Asset:
        return await self.create(source="url", url=url, name=name, idempotency_key=idempotency_key)

    async def update(
        self, asset_id: str, *, name: Optional[str] = None, favorite: Optional[bool] = None
    ) -> Asset:
        result = await self._client._request("PATCH", _asset_path(asset_id), json=_update_body(name, favorite))
        return Asset.from_dict(result.data)

    async def delete(self, asset_id: str) -> AssetDeleted:
        result = await self._client._request("DELETE", _asset_path(asset_id))
        return AssetDeleted.from_dict(result.data)

    async def usage(self) -> AssetUsage:
        result = await self._client._request("GET", "/api/v1/assets/usage")
        return AssetUsage.from_dict(result.data)

    async def list_characters(
        self, *, asset_id: Optional[str] = None, cursor: Optional[str] = None, limit: Optional[int] = None
    ) -> AssetCharacterPage:
        result = await self._client._request(
            "GET",
            "/api/v1/assets/entities",
            params={"assetId": asset_id, "cursor": cursor, "limit": limit},
        )
        return AssetCharacterPage.from_dict(result.data)

    async def get_character(self, entity_id: str) -> AssetCharacter:
        result = await self._client._request("GET", _entity_path(entity_id))
        return AssetCharacter.from_dict(result.data)
