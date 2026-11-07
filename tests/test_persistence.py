from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from mt_engine.adapters.persistence import (
    IncompatibleSchemaError,
    current_revision,
    session_factory,
    upgrade,
)
from mt_engine.adapters.persistence.migration import assert_schema_compatible, supported_head
from mt_engine.adapters.persistence.models import Batch, Configuration, OutboxEvent, Project

EXPECTED_TABLES = {
    "alembic_version",
    "artifacts",
    "assets",
    "batches",
    "configurations",
    "errors",
    "jobs",
    "lyrics_revisions",
    "outbox_events",
    "projects",
    "schema_metadata",
    "step_attempts",
    "timing_revisions",
    "worker_leases",
    "workflow_steps",
}


def test_fresh_database_upgrades_to_reviewed_head(tmp_path: Path):
    engine = upgrade(tmp_path / "ฐานข้อมูล" / "jobs.db")

    assert current_revision(engine) == supported_head()
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_foreign_keys_reject_orphan_batch(tmp_path: Path):
    engine = upgrade(tmp_path / "jobs.db")

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO batches "
                "(id, project_id, config_id, state, revision, request_id, updated_at, created_at) "
                "VALUES ('b1', 'missing', 'missing', 'NEW', 1, 'req-1', :now, :now)"
            ),
            {"now": "2026-11-07T00:00:00Z"},
        )


def test_state_and_outbox_rollback_in_same_transaction(tmp_path: Path):
    engine = upgrade(tmp_path / "jobs.db")
    sessions = session_factory(engine)
    now = "2026-11-07T00:00:00Z"

    with pytest.raises(RuntimeError), sessions.begin() as session:
        session.add(Project(id="p1", name="Test", created_at=now))
        session.add(
            Configuration(
                id="c1", schema_version=1, content_hash="a" * 64, payload_json="{}", created_at=now
            )
        )
        session.flush()
        session.add(
            Batch(
                id="b1",
                project_id="p1",
                config_id="c1",
                state="NEW",
                revision=1,
                request_id="req-1",
                updated_at=now,
                created_at=now,
            )
        )
        session.add(
            OutboxEvent(
                event_id="e1",
                event_type="batch.created",
                schema_version=1,
                aggregate_id="b1",
                correlation_id="corr-1",
                payload_json="{}",
                emitted_at=now,
            )
        )
        session.flush()
        raise RuntimeError("simulate command failure")

    with sessions() as session:
        assert session.get(Batch, "b1") is None
        assert session.query(OutboxEvent).count() == 0


def test_unknown_future_revision_blocks_startup(tmp_path: Path):
    engine = upgrade(tmp_path / "jobs.db")
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='future_revision'"))

    with pytest.raises(IncompatibleSchemaError, match="not supported"):
        assert_schema_compatible(engine)
