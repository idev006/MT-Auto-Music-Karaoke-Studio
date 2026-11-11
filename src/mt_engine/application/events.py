"""Immutable events and UI-neutral read models emitted by the engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .orchestrator import BatchJobSnapshot


class EngineEventKind(StrEnum):
    QUEUE_CHANGED = "QUEUE_CHANGED"
    BATCH_STARTED = "BATCH_STARTED"
    JOB_PROGRESS = "JOB_PROGRESS"
    JOB_FINISHED = "JOB_FINISHED"
    BATCH_FINISHED = "BATCH_FINISHED"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    sequence: int
    kind: EngineEventKind
    job_id: str | None
    progress: int | None
    detail: str
    data: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class OrchestratorView:
    revision: int
    jobs: tuple[BatchJobSnapshot, ...]
    total_jobs: int
    active_jobs: int
    terminal_jobs: int
    batch_running: bool
    can_start: bool
    queue_mutable: bool
