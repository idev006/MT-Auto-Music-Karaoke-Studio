from pathlib import Path

import pytest
from sqlalchemy import select

from mt_engine.adapters.persistence import session_factory, upgrade
from mt_engine.adapters.persistence.models import (
    Batch,
    Configuration,
    Job,
    JobRun,
    JobRunBranch,
    OutboxEvent,
    Project,
)
from mt_engine.adapters.persistence.repositories import (
    ActiveRunExistsError,
    RunRepository,
    StaleOwnershipError,
    StaleRevisionError,
)
from mt_engine.domain.states import BranchState, JobState, RunState

NOW = "2026-11-07T12:00:00Z"


def _database(tmp_path: Path):
    engine = upgrade(tmp_path / "jobs.db")
    sessions = session_factory(engine)
    with sessions.begin() as session:
        session.add(Project(id="p1", name="Project", created_at=NOW))
        session.add(
            Configuration(
                id="c1", schema_version=1, content_hash="c" * 64, payload_json="{}", created_at=NOW
            )
        )
        session.flush()
        session.add(
            Batch(
                id="b1",
                project_id="p1",
                config_id="c1",
                state="RUNNING",
                revision=1,
                request_id="request-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.flush()
        session.add(
            Job(
                id="j1",
                batch_id="b1",
                source_root_id="source",
                source_relpath="เพลงหนึ่ง",
                state=JobState.READY.value,
                revision=1,
                active_run_id=None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    return sessions


def _create_first_run(sessions, repository: RunRepository) -> None:
    with sessions.begin() as session:
        repository.create_run(
            session,
            job_id="j1",
            run_id="r1",
            expected_job_revision=1,
            input_hash="a" * 64,
            config_hash="b" * 64,
            event_id="e1",
            correlation_id="c1",
            now=NOW,
        )


def test_create_run_is_atomic_with_branches_and_outbox(tmp_path: Path):
    sessions = _database(tmp_path)
    repository = RunRepository()
    with sessions.begin() as session:
        created = repository.create_run(
            session,
            job_id="j1",
            run_id="r1",
            expected_job_revision=1,
            input_hash="a" * 64,
            config_hash="b" * 64,
            event_id="e1",
            correlation_id="correlation-1",
            now=NOW,
        )

    assert created.run_number == 1
    assert created.state is RunState.QUEUED
    with sessions() as session:
        job = session.get(Job, "j1")
        assert job is not None
        assert job.active_run_id == "r1"
        assert job.state == JobState.QUEUED.value
        assert job.revision == 2
        branches = session.scalars(
            select(JobRunBranch).where(JobRunBranch.run_id == "r1")
        ).all()
        assert {(branch.branch, branch.state) for branch in branches} == {
            ("MP3", BranchState.NOT_STARTED.value),
            ("MP4", BranchState.NOT_STARTED.value),
        }
        assert session.scalar(select(OutboxEvent.event_type)) == "job_run.queued"


def test_only_one_active_run_per_job(tmp_path: Path):
    sessions = _database(tmp_path)
    repository = RunRepository()
    _create_first_run(sessions, repository)

    with sessions.begin() as session, pytest.raises(ActiveRunExistsError):
        repository.create_run(
            session,
            job_id="j1",
            run_id="r2",
            expected_job_revision=2,
            input_hash="a" * 64,
            config_hash="b" * 64,
            event_id="e2",
            correlation_id="c2",
            now=NOW,
        )


def test_stale_job_revision_cannot_create_run(tmp_path: Path):
    sessions = _database(tmp_path)
    with sessions.begin() as session, pytest.raises(StaleRevisionError):
        RunRepository().create_run(
            session,
            job_id="j1",
            run_id="r1",
            expected_job_revision=99,
            input_hash="a" * 64,
            config_hash="b" * 64,
            event_id="e1",
            correlation_id="c1",
            now=NOW,
        )


def test_claim_increments_owner_epoch_and_rejects_stale_owner(tmp_path: Path):
    sessions = _database(tmp_path)
    repository = RunRepository()
    _create_first_run(sessions, repository)
    with sessions.begin() as session:
        claim = repository.claim_run(
            session,
            run_id="r1",
            owner_id="worker-1",
            expected_run_revision=1,
            now_ms=1000,
            lease_duration_ms=5000,
            now=NOW,
        )

    assert claim.owner_epoch == 1
    assert claim.revision == 2
    with sessions() as session:
        repository.require_current_owner(
            session, run_id="r1", owner_id="worker-1", owner_epoch=1
        )
        with pytest.raises(StaleOwnershipError):
            repository.require_current_owner(
                session, run_id="r1", owner_id="worker-old", owner_epoch=0
            )


def test_create_run_rolls_back_state_and_event_together(tmp_path: Path):
    sessions = _database(tmp_path)
    with pytest.raises(RuntimeError), sessions.begin() as session:
        RunRepository().create_run(
            session,
            job_id="j1",
            run_id="r1",
            expected_job_revision=1,
            input_hash="a" * 64,
            config_hash="b" * 64,
            event_id="e1",
            correlation_id="c1",
            now=NOW,
        )
        session.flush()
        raise RuntimeError("simulate command failure")

    with sessions() as session:
        assert session.get(JobRun, "r1") is None
        assert session.scalar(select(OutboxEvent.seq)) is None
        job = session.get(Job, "j1")
        assert job is not None and job.active_run_id is None
