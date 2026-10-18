"""Balance and per-key usage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .._base_client import DateLike, format_date
from ..types import Balance, Usage

if TYPE_CHECKING:  # pragma: no cover
    from .._client import AsyncPopNow, PopNow

__all__ = ["Account", "AsyncAccount"]


class Account:
    """``client.account``."""

    def __init__(self, client: "PopNow") -> None:
        self._client = client

    def balance(self) -> Balance:
        """Available, held and total credits of the account wallet."""
        result = self._client._request("GET", "/api/v1/chat/credit")
        return Balance.from_dict(result.data)

    def usage(self, *, from_date: Optional[DateLike] = None, to_date: Optional[DateLike] = None) -> Usage:
        """Calls and settled spend of the calling key over the UTC interval ``[from_date, to_date)``.

        Defaults to the last seven days; the range may span at most 92 days.
        """
        result = self._client._request(
            "GET", "/api/v1/usage", params={"from": format_date(from_date), "to": format_date(to_date)}
        )
        return Usage.from_dict(result.data)


class AsyncAccount:
    """``client.account`` on :class:`~popnow.AsyncPopNow`."""

    def __init__(self, client: "AsyncPopNow") -> None:
        self._client = client

    async def balance(self) -> Balance:
        result = await self._client._request("GET", "/api/v1/chat/credit")
        return Balance.from_dict(result.data)

    async def usage(
        self, *, from_date: Optional[DateLike] = None, to_date: Optional[DateLike] = None
    ) -> Usage:
        result = await self._client._request(
            "GET", "/api/v1/usage", params={"from": format_date(from_date), "to": format_date(to_date)}
        )
        return Usage.from_dict(result.data)
