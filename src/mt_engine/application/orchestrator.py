"""Process-wide orchestration for bounded, isolated folder production jobs."""

from __future__ import annotations

import json
import os
import threading
import traceback
from collections import deque
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from mt_engine.paths import PathManager
from mt_engine.production import ProductionResult, produce_song

from .events import EngineEvent, EngineEventKind, OrchestratorView


class BatchJobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLED = "CANCELLED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


TERMINAL_STATES = {
    BatchJobState.CANCELLED,
    BatchJobState.SUCCEEDED,
    BatchJobState.FAILED,
    BatchJobState.REVIEW_REQUIRED,
}


class BatchCancelled(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BatchSettings:
    dest_root: Path
    ffmpeg_root: Path
    font_assets_dir: Path
    model_cache_dir: Path = Path("models/faster-whisper")
    model_name: str = "base"
    cpu_threads_per_worker: int = 2
    ffmpeg_preset: str = "veryfast"
    karaoke_preset: str = "classic-gold"
    openrouter_config: Path = Path("config/openrouter.env")
    openrouter_mode: str = "off"
    accept_unreviewed_timing: bool = False
    timing_lock: Path | None = None


@dataclass(frozen=True, slots=True)
class BatchJobSnapshot:
    job_id: str
    source: Path
    state: BatchJobState
    progress: int
    detail: str
    target: Path | None = None
    error: str | None = None
    error_detail: str | None = None
    metrics: tuple[tuple[str, str], ...] = ()


class Producer(Protocol):
    def __call__(
        self,
        source: Path,
        settings: BatchSettings,
        progress: Callable[[int, str, Mapping[str, str] | None], None],
    ) -> object: ...


def _production_adapter(
    source: Path,
    settings: BatchSettings,
    progress: Callable[[int, str, Mapping[str, str] | None], None],
) -> ProductionResult:
    return produce_song(
        source,
        settings.dest_root,
        ffmpeg_root=settings.ffmpeg_root,
        model_name=settings.model_name,
        model_cache=settings.model_cache_dir,
        cpu_threads=settings.cpu_threads_per_worker,
        ffmpeg_preset=settings.ffmpeg_preset,
        karaoke_preset=settings.karaoke_preset,
        font_assets_dir=settings.font_assets_dir,
        openrouter_config=settings.openrouter_config,
        openrouter_mode=settings.openrouter_mode,
        accept_unreviewed_timing=settings.accept_unreviewed_timing,
        timing_lock=settings.timing_lock,
        progress_callback=progress,
    )


class ApplicationOrchestrator:
    """Own admission, lifecycle, resource policy and immutable job snapshots."""

    def __init__(self, producer: Producer = _production_adapter) -> None:
        self._producer = producer
        self._lock = threading.RLock()
        self._jobs: dict[str, BatchJobSnapshot] = {}
        self._cancel: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[object]] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._sequence = 0
        self._event_sequence = 0
        self._events: deque[EngineEvent] = deque(maxlen=4096)

    def add(self, folders: tuple[Path, ...]) -> tuple[str, ...]:
        added = []
        with self._lock:
            if self._executor is not None:
                raise RuntimeError("Cannot add folders while a batch is running")
            known = {job.source for job in self._jobs.values() if job.state not in TERMINAL_STATES}
            for folder in folders:
                source = PathManager.source_folder(folder)
                if source in known:
                    continue
                self._sequence += 1
                job_id = f"J{self._sequence:04d}"
                self._jobs[job_id] = BatchJobSnapshot(
                    job_id, source, BatchJobState.QUEUED, 0, "Queued"
                )
                self._cancel[job_id] = threading.Event()
                known.add(source)
                added.append(job_id)
                self._publish_locked(EngineEventKind.QUEUE_CHANGED, job_id, 0, "Queued")
        return tuple(added)

    def remove_queued(self, job_ids: tuple[str, ...]) -> None:
        with self._lock:
            if self._executor is not None:
                raise RuntimeError("Cannot remove queued jobs while a batch is running")
            for job_id in job_ids:
                job = self._jobs.get(job_id)
                if job is not None and (
                    job.state == BatchJobState.QUEUED or job.state in TERMINAL_STATES
                ):
                    self._jobs.pop(job_id)
                    self._cancel.pop(job_id, None)
                    self._publish_locked(EngineEventKind.QUEUE_CHANGED, job_id, None, "Removed")

    def start(self, settings: BatchSettings, *, max_workers: int) -> None:
        if max_workers < 1:
            raise ValueError("Worker count must be at least 1")
        if settings.cpu_threads_per_worker < 1:
            raise ValueError("CPU threads per worker must be at least 1")
        available_cpus = max(1, os.cpu_count() or 1)
        if max_workers * settings.cpu_threads_per_worker > available_cpus:
            raise ValueError(
                "Worker count multiplied by CPU threads per worker "
                f"must not exceed {available_cpus}"
            )
        if not settings.font_assets_dir.is_dir():
            raise ValueError(f"Font assets directory does not exist: {settings.font_assets_dir}")
        if settings.timing_lock is None and not settings.accept_unreviewed_timing:
            raise ValueError(
                "Select a reviewed timing lock, or enable diagnostic timing "
                "to create a non-release test video"
            )
        validated = replace(
            settings,
            dest_root=PathManager.output_root(settings.dest_root),
            ffmpeg_root=PathManager.ffmpeg_root(settings.ffmpeg_root),
            font_assets_dir=settings.font_assets_dir.resolve(),
            model_cache_dir=PathManager.output_root(settings.model_cache_dir),
            openrouter_config=settings.openrouter_config.resolve(),
        )
        with self._lock:
            if self._executor is not None:
                raise RuntimeError("A batch is already running")
            queued = [job for job in self._jobs.values() if job.state == BatchJobState.QUEUED]
            if not queued:
                return
            self._executor = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="karaoke-worker"
            )
            self._publish_locked(
                EngineEventKind.BATCH_STARTED,
                None,
                0,
                "Batch started",
                {"workers": str(max_workers)},
            )
            for job in queued:
                future = self._executor.submit(self._run_job, job.job_id, validated)
                self._futures[job.job_id] = future

    def cancel(self, job_ids: tuple[str, ...]) -> None:
        with self._lock:
            for job_id in job_ids:
                job = self._jobs.get(job_id)
                if job is None or job.state in TERMINAL_STATES:
                    continue
                self._cancel[job_id].set()
                future = self._futures.get(job_id)
                if future is not None and future.cancel():
                    self._jobs[job_id] = replace(
                        job, state=BatchJobState.CANCELLED, detail="Cancelled"
                    )
                else:
                    self._jobs[job_id] = replace(
                        job,
                        state=BatchJobState.CANCELLATION_REQUESTED,
                        detail="Cancellation requested",
                    )
                self._publish_locked(
                    EngineEventKind.JOB_PROGRESS,
                    job_id,
                    self._jobs[job_id].progress,
                    self._jobs[job_id].detail,
                )
        # Cancelled futures never enter _run_job(), so they cannot release the
        # executor from that worker's finally block. Reconcile here as well.
        self._release_executor_if_terminal()

    def snapshots(self) -> tuple[BatchJobSnapshot, ...]:
        with self._lock:
            return tuple(self._jobs.values())

    def view(self) -> OrchestratorView:
        with self._lock:
            jobs = tuple(self._jobs.values())
            terminal = sum(job.state in TERMINAL_STATES for job in jobs)
            return OrchestratorView(
                revision=self._event_sequence,
                jobs=jobs,
                total_jobs=len(jobs),
                active_jobs=len(jobs) - terminal,
                terminal_jobs=terminal,
                batch_running=self._executor is not None,
                can_start=(
                    self._executor is None
                    and any(job.state == BatchJobState.QUEUED for job in jobs)
                ),
                queue_mutable=self._executor is None,
            )

    def events_since(self, sequence: int) -> tuple[tuple[EngineEvent, ...], int]:
        with self._lock:
            events = tuple(event for event in self._events if event.sequence > sequence)
            return events, self._event_sequence

    def is_running(self) -> bool:
        with self._lock:
            return self._executor is not None

    def cancel_all(self) -> None:
        with self._lock:
            job_ids = tuple(
                job.job_id for job in self._jobs.values() if job.state not in TERMINAL_STATES
            )
        self.cancel(job_ids)

    def shutdown(self, *, wait: bool) -> None:
        with self._lock:
            executor, self._executor = self._executor, None
            for event in self._cancel.values():
                event.set()
        if executor is not None:
            executor.shutdown(wait=wait, cancel_futures=True)

    def _run_job(self, job_id: str, settings: BatchSettings) -> None:
        event = self._cancel[job_id]

        def progress(
            value: int,
            detail: str,
            data: Mapping[str, str] | None = None,
        ) -> None:
            if event.is_set():
                raise BatchCancelled("Cancellation requested")
            with self._lock:
                current = self._jobs[job_id]
                self._jobs[job_id] = replace(
                    current,
                    state=BatchJobState.RUNNING,
                    progress=max(current.progress, min(100, int(value))),
                    detail=detail,
                    metrics=tuple(sorted((data or {}).items())),
                )
                self._publish_locked(
                    EngineEventKind.JOB_PROGRESS,
                    job_id,
                    self._jobs[job_id].progress,
                    detail,
                    data,
                )

        with self._lock:
            current = self._jobs[job_id]
            if event.is_set():
                self._jobs[job_id] = replace(
                    current, state=BatchJobState.CANCELLED, detail="Cancelled"
                )
                return
            self._jobs[job_id] = replace(
                current, state=BatchJobState.RUNNING, progress=1, detail="Starting"
            )
            self._publish_locked(EngineEventKind.JOB_PROGRESS, job_id, 1, "Starting")
        try:
            result = self._producer(current.source, settings, progress)
            target = getattr(result, "target_dir", settings.dest_root / current.source.name)
            production_state = getattr(result, "state", "COMPLETED")
            succeeded = production_state in {"COMPLETED", "SUCCEEDED"}
            with self._lock:
                self._jobs[job_id] = replace(
                    self._jobs[job_id],
                    state=(BatchJobState.SUCCEEDED if succeeded else BatchJobState.REVIEW_REQUIRED),
                    progress=100,
                    detail=("Completed" if succeeded else production_state),
                    target=Path(target),
                )
                self._publish_locked(
                    EngineEventKind.JOB_FINISHED,
                    job_id,
                    100,
                    self._jobs[job_id].detail,
                )
        except BatchCancelled:
            with self._lock:
                self._jobs[job_id] = replace(
                    self._jobs[job_id], state=BatchJobState.CANCELLED, detail="Cancelled"
                )
                self._publish_locked(EngineEventKind.JOB_FINISHED, job_id, None, "Cancelled")
        except Exception as error:  # noqa: BLE001 - worker boundary records typed failure
            error_detail = traceback.format_exc()
            target = settings.dest_root / current.source.name
            stage = "UNKNOWN"
            state_path = target / "production_data" / "run_state.json"
            try:
                if state_path.is_file():
                    state_payload = json.loads(state_path.read_text(encoding="utf-8"))
                    stage = str(state_payload.get("stage") or stage)
                target.mkdir(parents=True, exist_ok=True)
                failure_path = target / "production_data" / "failure.log"
                failure_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = failure_path.with_suffix(".log.partial")
                temporary.write_text(
                    f"stage={stage}\n{error_detail}", encoding="utf-8"
                )
                os.replace(temporary, failure_path)
            except (OSError, UnicodeError, ValueError):
                pass
            with self._lock:
                self._jobs[job_id] = replace(
                    self._jobs[job_id],
                    state=BatchJobState.FAILED,
                    progress=100,
                    detail=f"Failed at {stage}",
                    target=target,
                    error=f"[{stage}] {type(error).__name__}: {error}",
                    error_detail=error_detail,
                )
                self._publish_locked(EngineEventKind.JOB_FINISHED, job_id, 100, "Failed")
        finally:
            self._release_executor_if_terminal()

    def _release_executor_if_terminal(self) -> None:
        executor = None
        with self._lock:
            if self._executor is not None and all(
                job.state in TERMINAL_STATES for job in self._jobs.values()
            ):
                executor, self._executor = self._executor, None
                self._futures.clear()
                self._publish_locked(EngineEventKind.BATCH_FINISHED, None, 100, "Batch finished")
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def _publish_locked(
        self,
        kind: EngineEventKind,
        job_id: str | None,
        progress: int | None,
        detail: str,
        data: Mapping[str, str] | None = None,
    ) -> None:
        self._event_sequence += 1
        self._events.append(
            EngineEvent(
                self._event_sequence,
                kind,
                job_id,
                progress,
                detail,
                tuple(sorted((data or {}).items())),
            )
        )
