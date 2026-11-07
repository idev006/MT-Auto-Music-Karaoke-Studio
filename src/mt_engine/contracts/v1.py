"""Schema version 1 contracts shared by engine boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

CONTRACT_SCHEMA_VERSION = 1
Primitive = None | bool | int | float | str | list["Primitive"] | dict[str, "Primitive"]


def _immutable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(dict(value))


class ToolResultStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class ContractError:
    code: str
    category: str
    message_for_user: str
    retryable: bool
    correlation_id: str
    suggested_action: str
    technical_details: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "technical_details", _immutable_mapping(self.technical_details))


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    schema_version: int
    artifact_id: str
    job_id: str
    run_id: str
    owner_epoch: int
    operation_id: str
    branch: str
    root_id: str
    relpath: str
    sha256: str
    input_hash: str
    config_hash: str
    validation: Mapping[str, Any]
    tool_versions: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "validation", _immutable_mapping(self.validation))
        object.__setattr__(self, "tool_versions", _immutable_mapping(self.tool_versions))


@dataclass(frozen=True, slots=True)
class ToolRequest:
    schema_version: int
    job_id: str
    run_id: str
    owner_epoch: int
    operation_id: str
    input_hash: str
    config_hash: str
    deadline_utc: datetime
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.deadline_utc.tzinfo is None:
            raise ValueError("deadline_utc must be timezone-aware")
        object.__setattr__(self, "payload", _immutable_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class ToolResult:
    schema_version: int
    job_id: str
    run_id: str
    owner_epoch: int
    operation_id: str
    status: ToolResultStatus
    artifacts: tuple[ArtifactManifest, ...]
    metrics: Mapping[str, int | float | str]
    error: ContractError | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "metrics", _immutable_mapping(self.metrics))


@dataclass(frozen=True, slots=True)
class DomainEvent:
    schema_version: int
    event_id: str
    sequence: int
    event_type: str
    occurred_at_utc: datetime
    correlation_id: str
    batch_id: str | None
    job_id: str | None
    run_id: str | None
    owner_epoch: int | None
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.occurred_at_utc.tzinfo is None:
            raise ValueError("occurred_at_utc must be timezone-aware")
        object.__setattr__(self, "payload", _immutable_mapping(self.payload))


def to_primitive(value: Any) -> Primitive:
    """Convert a contract value into a deterministic JSON-compatible shape."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        utc_value = value.astimezone(UTC)
        return utc_value.isoformat().replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [to_primitive(item) for item in value]
    raise TypeError(f"Unsupported contract value: {type(value).__name__}")
