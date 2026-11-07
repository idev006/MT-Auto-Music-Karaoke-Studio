from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from mt_engine.adapters.persistence.migration import (
    InsufficientMigrationSpaceError,
    MigrationFailedError,
    backup_database,
    upgrade_safely,
)

FIRST_REVISION = "106a0b13ddd3"


def _upgrade_to_first_revision(database_path: Path) -> None:
    config = Config(Path(__file__).resolve().parents[2] / "alembic.ini")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, FIRST_REVISION)
        connection.execute(
            text("INSERT INTO projects (id, name, created_at) VALUES ('p1', 'Preserved', :now)"),
            {"now": "2026-11-07T12:00:00Z"},
        )
    engine.dispose()


def test_safe_upgrade_backs_up_previous_revision_and_preserves_data(tmp_path: Path):
    database_path = tmp_path / "data" / "jobs.db"
    database_path.parent.mkdir()
    _upgrade_to_first_revision(database_path)

    outcome = upgrade_safely(database_path, backup_dir=tmp_path / "backups")

    assert outcome.previous_revision == FIRST_REVISION
    assert outcome.current_revision == "b7f41c92a003"
    assert outcome.backup_path is not None and outcome.backup_path.is_file()
    with outcome.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT name FROM projects WHERE id='p1'")).scalar_one()
            == "Preserved"
        )
    backup_engine = create_engine(f"sqlite:///{outcome.backup_path.as_posix()}")
    assert "job_runs" not in inspect(backup_engine).get_table_names()
    backup_engine.dispose()


def test_failed_upgrade_restores_previous_database(monkeypatch, tmp_path: Path):
    database_path = tmp_path / "data" / "jobs.db"
    database_path.parent.mkdir()
    _upgrade_to_first_revision(database_path)

    def destructive_failure(config, revision):
        connection = config.attributes["connection"]
        connection.exec_driver_sql("DROP TABLE projects")
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(
        "mt_engine.adapters.persistence.migration.command.upgrade", destructive_failure
    )

    with pytest.raises(MigrationFailedError) as failure:
        upgrade_safely(database_path, backup_dir=tmp_path / "backups")

    assert failure.value.backup_path.is_file()
    restored = create_engine(f"sqlite:///{database_path.as_posix()}")
    with restored.connect() as connection:
        assert (
            connection.execute(text("SELECT name FROM projects WHERE id='p1'")).scalar_one()
            == "Preserved"
        )
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == FIRST_REVISION
        )
    restored.dispose()


def test_fresh_database_needs_no_backup(tmp_path: Path):
    outcome = upgrade_safely(tmp_path / "data" / "fresh.db", backup_dir=tmp_path / "backups")

    assert outcome.backup_path is None
    assert outcome.current_revision == "b7f41c92a003"


def test_backup_fails_before_migration_when_disk_space_is_insufficient(monkeypatch, tmp_path: Path):
    database_path = tmp_path / "jobs.db"
    database_path.write_bytes(b"database bytes")
    monkeypatch.setattr(
        "mt_engine.adapters.persistence.migration.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=0),
    )

    with pytest.raises(InsufficientMigrationSpaceError):
        backup_database(database_path, tmp_path / "backups")
