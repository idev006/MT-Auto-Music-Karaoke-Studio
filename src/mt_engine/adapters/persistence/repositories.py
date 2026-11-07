"""Transactional repositories for ADR-0003 JobRun ownership."""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from mt_engine.domain.states import BranchState, JobState, RunState, require_transition

from .models import Job, JobRun, JobRunBranch, OutboxEvent


class RepositoryError(RuntimeError):
    """Base persistence command failure."""


class RecordNotFoundError(RepositoryError):
    """The requested aggregate does not exist."""


class StaleRevisionError(RepositoryError):
    """The caller attempted to mutate an outdated aggregate revision."""


class ActiveRunExistsError(RepositoryError):
    """A Job already has an active JobRun."""


class StaleOwnershipError(RepositoryError):
    """A tool result or heartbeat does not belong to the current owner epoch."""


@dataclass(frozen=True, slots=True)
class RunCreated:
    run_id: str
    run_number: int
    state: RunState
    revision: int


@dataclass(frozen=True, slots=True)
class RunClaim:
    run_id: str
    owner_id: str
    owner_epoch: int
    revision: int
    lease_expires_at_ms: int


class RunRepository:
    """Apply fenced run commands inside a caller-owned transaction."""

    def create_run(
        self,
        session: Session,
        *,
        job_id: str,
        run_id: str,
        expected_job_revision: int,
        input_hash: str,
        config_hash: str,
        event_id: str,
        correlation_id: str,
        now: str,
    ) -> RunCreated:
        job = session.get(Job, job_id)
        if job is None:
            raise RecordNotFoundError(f"Job {job_id!r} does not exist")
        if job.revision != expected_job_revision:
            raise StaleRevisionError(
                f"Job {job_id!r} revision is {job.revision}, expected {expected_job_revision}"
            )
        if job.active_run_id is not None:
            raise ActiveRunExistsError(
                f"Job {job_id!r} already has active run {job.active_run_id!r}"
            )

        current_job_state = JobState(job.state)
        require_transition(current_job_state, JobState.QUEUED)
        run_number = (
            session.scalar(
                select(func.coalesce(func.max(JobRun.run_number), 0)).where(JobRun.job_id == job_id)
            )
            or 0
        ) + 1
        run = JobRun(
            id=run_id,
            job_id=job_id,
            run_number=run_number,
            state=RunState.QUEUED.value,
            revision=1,
            owner_id=None,
            owner_epoch=0,
            lease_expires_at_ms=None,
            heartbeat_at_ms=None,
            input_hash=input_hash,
            config_hash=config_hash,
            created_at=now,
            updated_at=now,
            finished_at=None,
        )
        session.add(run)
        session.add_all(
            [
                JobRunBranch(
                    run_id=run_id,
                    branch=branch,
                    state=BranchState.NOT_STARTED.value,
                    revision=1,
                    updated_at=now,
                )
                for branch in ("MP3", "MP4")
            ]
        )
        session.flush()

        job.active_run_id = run_id
        job.state = JobState.QUEUED.value
        job.revision += 1
        job.updated_at = now
        session.add(
            OutboxEvent(
                event_id=event_id,
                event_type="job_run.queued",
                schema_version=1,
                aggregate_id=run_id,
                correlation_id=correlation_id,
                payload_json=json.dumps(
                    {"job_id": job_id, "run_id": run_id, "run_number": run_number},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                emitted_at=now,
                delivered_at=None,
            )
        )
        return RunCreated(run_id, run_number, RunState.QUEUED, 1)

    def claim_run(
        self,
        session: Session,
        *,
        run_id: str,
        owner_id: str,
        expected_run_revision: int,
        now_ms: int,
        lease_duration_ms: int,
        now: str,
    ) -> RunClaim:
        if lease_duration_ms <= 0:
            raise ValueError("lease_duration_ms must be positive")
        result = session.execute(
            update(JobRun)
            .where(
                JobRun.id == run_id,
                JobRun.revision == expected_run_revision,
                JobRun.state == RunState.QUEUED.value,
                JobRun.owner_id.is_(None),
            )
            .values(
                state=RunState.RUNNING.value,
                revision=JobRun.revision + 1,
                owner_id=owner_id,
                owner_epoch=JobRun.owner_epoch + 1,
                heartbeat_at_ms=now_ms,
                lease_expires_at_ms=now_ms + lease_duration_ms,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            raise StaleRevisionError(
                f"Run {run_id!r} was not queued at revision {expected_run_revision}"
            )
        run = session.get(JobRun, run_id)
        if run is None:
            raise RecordNotFoundError(f"Run {run_id!r} does not exist")
        return RunClaim(
            run_id=run.id,
            owner_id=owner_id,
            owner_epoch=run.owner_epoch,
            revision=run.revision,
            lease_expires_at_ms=run.lease_expires_at_ms or 0,
        )

    def require_current_owner(
        self,
        session: Session,
        *,
        run_id: str,
        owner_id: str,
        owner_epoch: int,
    ) -> JobRun:
        run = session.get(JobRun, run_id)
        if run is None:
            raise RecordNotFoundError(f"Run {run_id!r} does not exist")
        if run.owner_id != owner_id or run.owner_epoch != owner_epoch:
            raise StaleOwnershipError(
                f"Run {run_id!r} is owned by epoch {run.owner_epoch}, not {owner_epoch}"
            )
        return run
