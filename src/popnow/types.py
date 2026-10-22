"""Typed response objects.

The API speaks camelCase JSON; these dataclasses expose snake_case attributes.
Every object keeps the untouched JSON in ``raw`` so fields added to the API
later are never lost, and ``obj["camelCaseKey"]`` reads from it directly.

Timestamps are kept as the ISO 8601 strings the API returns. USD amounts are
decimal strings (``"0.185"``); credit amounts are integers (1 credit = $0.001).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Callable, Dict, Iterator, List, Optional, Type, TypeVar

__all__ = [
    "APIObject",
    "TERMINAL_STATES",
    "OutputAsset",
    "TaskOutput",
    "TaskRetention",
    "Task",
    "TaskCreated",
    "TaskQuote",
    "TaskSummary",
    "TaskPage",
    "TaskPurgeResult",
    "Model",
    "ModelList",
    "Balance",
    "UsageDay",
    "UsageModel",
    "Usage",
    "UploadTicket",
    "UploadedFile",
    "DownloadURL",
    "Asset",
    "AssetPage",
    "AssetCharacter",
    "AssetCharacterPage",
    "AssetUsage",
    "AssetDeleted",
]

#: Task states after which nothing changes. Unknown states are treated as not final.
TERMINAL_STATES = frozenset({"succeeded", "failed", "expired", "canceled"})

T = TypeVar("T", bound="APIObject")


def _camel(name: str) -> str:
    head, *rest = name.rstrip("_").split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def _list_of(cls: Type[T]) -> Callable[[Any], List[T]]:
    def convert(value: Any) -> List[T]:
        return [cls.from_dict(item) for item in value or [] if isinstance(item, dict)]

    return convert


def _one(cls: Type[T]) -> Callable[[Any], Optional[T]]:
    def convert(value: Any) -> Optional[T]:
        return cls.from_dict(value) if isinstance(value, dict) else None

    return convert


@dataclass
class APIObject:
    """Base class: builds itself from the API's camelCase JSON."""

    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {}

    @classmethod
    def from_dict(cls: Type[T], data: Optional[Dict[str, Any]]) -> T:
        data = data or {}
        converters = cls._converters()
        kwargs: Dict[str, Any] = {}
        for f in fields(cls):
            if f.name == "raw":
                continue
            key = f.metadata.get("key") or _camel(f.name)
            if key not in data:
                continue
            value = data[key]
            convert = converters.get(f.name)
            kwargs[f.name] = convert(value) if convert is not None and value is not None else value
        return cls(raw=dict(data), **kwargs)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Read a raw JSON field by its API (camelCase) name."""
        return self.raw.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """The original JSON object."""
        return dict(self.raw)


# --------------------------------------------------------------------------- tasks


@dataclass
class OutputAsset(APIObject):
    """One generated file in ``task.output.assets``.

    ``url`` is a signed link valid for about 20 minutes. Do not send your API
    key when downloading it, and do not store it: read the task again for a
    fresh link.
    """

    key: Optional[str] = None
    url: Optional[str] = None
    expires_at: Optional[str] = None
    mime: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    bytes: Optional[int] = None
    role: Optional[str] = None
    pending: Optional[bool] = None
    unavailable: Optional[bool] = None
    deleted: Optional[bool] = None
    layer: Optional[Dict[str, Any]] = None


@dataclass
class TaskOutput(APIObject):
    text: Optional[str] = None
    transcript: Optional[Dict[str, Any]] = None
    assets: List[OutputAsset] = field(default_factory=list)

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"assets": _list_of(OutputAsset)}


@dataclass
class TaskRetention(APIObject):
    outputs_expire_at: Optional[str] = None
    prompts_expire_at: Optional[str] = None
    source: Optional[str] = None


@dataclass
class Task(APIObject):
    """A task record, as returned by ``jobs/recordInfo`` and webhooks."""

    task_id: str = ""
    model: str = ""
    state: str = ""
    source_task_id: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    output: Optional[TaskOutput] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    cost: Optional[str] = None
    credits: Optional[int] = None
    settled: Optional[bool] = None
    created_at: Optional[str] = None
    deadline_at: Optional[str] = None
    completed_at: Optional[str] = None
    content_state: Optional[str] = None
    content_removed_by: Optional[str] = None
    purged_at: Optional[str] = None
    retention: Optional[TaskRetention] = None

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"output": _one(TaskOutput), "retention": _one(TaskRetention)}

    @property
    def is_terminal(self) -> bool:
        """True once the state can no longer change."""
        return self.state in TERMINAL_STATES

    @property
    def is_succeeded(self) -> bool:
        return self.state == "succeeded"

    @property
    def assets(self) -> List[OutputAsset]:
        """Shortcut for ``output.assets`` (empty when there is no output)."""
        return list(self.output.assets) if self.output else []

    @property
    def urls(self) -> List[str]:
        """Signed URLs of every ready output asset."""
        return [a.url for a in self.assets if a.url]

    @property
    def text(self) -> Optional[str]:
        """Text result (speech-to-text), if any."""
        return self.output.text if self.output else None


@dataclass
class TaskCreated(APIObject):
    """Response of ``createTask`` and ``retry``.

    ``task`` is set only when ``wait`` was used and the task reached a terminal
    state within that budget (HTTP 200); it is the full task record.
    """

    task_id: str = ""
    state: str = ""
    estimated_cost: Optional[str] = None
    estimated_credits: Optional[int] = None
    deadline_at: Optional[str] = None
    source_task_id: Optional[str] = None
    task: Optional[Task] = field(default=None, metadata={"key": "__task__"})


@dataclass
class TaskQuote(APIObject):
    """Response of ``jobs/quote``. Nothing is created or held."""

    quote_id: str = ""
    model: str = ""
    estimated_cost: Optional[str] = None
    max_charge: Optional[str] = None
    max_credits: Optional[int] = None
    expected_credits: Optional[int] = None
    currency: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    expires_at: Optional[str] = None


@dataclass
class TaskSummary(APIObject):
    """One row of ``GET /api/v1/jobs`` (metadata only, no input or output)."""

    task_id: str = ""
    request_id: Optional[str] = None
    model: str = ""
    state: str = ""
    cost: Optional[str] = None
    credits: Optional[int] = None
    settled: Optional[bool] = None
    created_at: Optional[str] = None
    deadline_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class TaskPage(APIObject):
    items: List[TaskSummary] = field(default_factory=list)
    has_more: bool = False
    next_cursor: Optional[str] = None

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"items": _list_of(TaskSummary)}

    def __iter__(self) -> Iterator[TaskSummary]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


@dataclass
class TaskPurgeResult(APIObject):
    task_id: str = ""
    content_state: Optional[str] = None
    purged_at: Optional[str] = None
    content_removed_by: Optional[str] = None
    billing_retained: bool = True
    media_deletion_pending: Optional[bool] = None


@dataclass
class DownloadURL(APIObject):
    key: str = ""
    url: str = ""
    expires_at: Optional[str] = None


# -------------------------------------------------------------------------- models


@dataclass
class Model(APIObject):
    """One callable model. ``model`` is the id ``createTask`` takes."""

    model: str = ""
    family: Optional[str] = None
    display_name: Optional[str] = None
    provider: Optional[str] = None
    modality: Optional[str] = None
    tasks: List[str] = field(default_factory=list)
    async_: Optional[bool] = None
    toolkit: Optional[str] = None
    task_timeout_seconds: Optional[int] = None
    max_output_duration_seconds: Optional[int] = None
    enabled: Optional[bool] = None
    available: Optional[bool] = None
    quantity_field: Optional[str] = None
    credits: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    version: Optional[str] = None
    availability: Optional[str] = None
    badges: List[str] = field(default_factory=list)
    related_models: List[str] = field(default_factory=list)
    examples: Optional[List[Dict[str, Any]]] = None
    updated_at: Optional[str] = None


@dataclass
class ModelList(APIObject):
    total: int = 0
    items: List[Model] = field(default_factory=list)

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"items": _list_of(Model)}

    def __iter__(self) -> Iterator[Model]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


# ------------------------------------------------------------------------- account


@dataclass
class Balance(APIObject):
    """Wallet balance. Use the ``*_credits`` integers; USD strings are for accounting."""

    available: Optional[str] = None
    held: Optional[str] = None
    total: Optional[str] = None
    available_credits: Optional[int] = None
    held_credits: Optional[int] = None
    total_credits: Optional[int] = None
    funding: Optional[Dict[str, Any]] = None


@dataclass
class UsageDay(APIObject):
    day: str = ""
    calls: int = 0
    succeeded: int = 0
    failed: int = 0
    spend: Optional[str] = None
    credits: Optional[int] = None


@dataclass
class UsageModel(APIObject):
    model: str = ""
    calls: int = 0
    succeeded: int = 0
    failed: int = 0
    spend: Optional[str] = None
    credits: Optional[int] = None


@dataclass
class Usage(APIObject):
    """Usage of the calling API key over ``[from_, to)`` (UTC dates)."""

    from_: Optional[str] = None
    to: Optional[str] = None
    currency: Optional[str] = None
    total_calls: int = 0
    total_spend: Optional[str] = None
    total_credits: Optional[int] = None
    days: List[UsageDay] = field(default_factory=list)
    models: List[UsageModel] = field(default_factory=list)

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"days": _list_of(UsageDay), "models": _list_of(UsageModel)}


# --------------------------------------------------------------------------- files


@dataclass
class UploadTicket(APIObject):
    """A presigned upload ticket from ``common/upload-url``."""

    file_id: str = ""
    key: str = ""
    upload_url: str = ""
    method: str = "PUT"
    headers: Dict[str, str] = field(default_factory=dict)
    expires_at: Optional[str] = None
    max_bytes: Optional[int] = None


@dataclass
class UploadedFile(APIObject):
    """A committed file. Put ``uri`` (``popnow://f/fil_...``) in a model's media field."""

    file_id: str = ""
    status: Optional[str] = None
    bytes: Optional[int] = None
    content_type: Optional[str] = None
    sha256: Optional[str] = None
    uri: str = ""
    expires_at: Optional[str] = None
    duration_seconds: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


# -------------------------------------------------------------------------- assets


@dataclass
class Asset(APIObject):
    """A saved asset. Persist ``uri`` (``popnow://a/ast_...``), never ``preview_url``."""

    id: str = ""
    uri: str = ""
    name: Optional[str] = None
    kind: Optional[str] = None
    content_type: Optional[str] = None
    bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    source: Optional[str] = None
    source_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    preview_url: Optional[str] = None
    preview_url_expires_at: Optional[str] = None
    favorite: Optional[bool] = None
    model: Optional[str] = None
    model_name: Optional[str] = None


@dataclass
class AssetPage(APIObject):
    items: List[Asset] = field(default_factory=list)
    next_cursor: Optional[str] = None

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"items": _list_of(Asset)}

    def __iter__(self) -> Iterator[Asset]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


@dataclass
class AssetCharacter(APIObject):
    """A named, ordered set of images in the asset library (read-only via the API)."""

    id: str = ""
    kind: Optional[str] = None
    name: Optional[str] = None
    note: Optional[str] = None
    cover_asset_id: Optional[str] = None
    cover: Optional[Asset] = None
    assets: List[Asset] = field(default_factory=list)
    count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"cover": _one(Asset), "assets": _list_of(Asset)}


@dataclass
class AssetCharacterPage(APIObject):
    items: List[AssetCharacter] = field(default_factory=list)
    next_cursor: Optional[str] = None

    @classmethod
    def _converters(cls) -> Dict[str, Callable[[Any], Any]]:
        return {"items": _list_of(AssetCharacter)}

    def __iter__(self) -> Iterator[AssetCharacter]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)


@dataclass
class AssetUsage(APIObject):
    """Asset library plan, usage and limits (``GET /api/v1/assets/usage``)."""

    tier: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None
    limits: Optional[Dict[str, Any]] = None
    full: Optional[bool] = None
    next_tier: Optional[Dict[str, Any]] = None
    topup_to_next_tier_usd: Optional[str] = None
    lifetime_topup_usd: Optional[str] = None
    tiers: List[Dict[str, Any]] = field(default_factory=list)
    daily_create_limit: Optional[int] = None
    created_today: Optional[int] = None
    scope: Optional[Dict[str, Any]] = None


@dataclass
class AssetDeleted(APIObject):
    id: str = ""
    deleted: bool = True
