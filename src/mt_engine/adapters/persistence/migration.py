"""Programmatic Alembic lifecycle and application schema compatibility checks."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from .db import create_sqlite_engine


class IncompatibleSchemaError(RuntimeError):
    """The database revision is absent from this application's migration graph."""


class InsufficientMigrationSpaceError(RuntimeError):
    """The backup destination cannot safely hold a pre-migration database copy."""


class MigrationFailedError(RuntimeError):
    """A migration failed after a recoverable backup was created and restored."""

    def __init__(self, message: str, *, backup_path: Path):
        super().__init__(message)
        self.backup_path = backup_path


@dataclass(frozen=True, slots=True)
class MigrationOutcome:
    engine: Engine
    previous_revision: str | None
    current_revision: str
    backup_path: Path | None


def _config() -> Config:
    project_root = Path(__file__).resolve().parents[4]
    return Config(project_root / "alembic.ini")


def supported_head() -> str:
    head = ScriptDirectory.from_config(_config()).get_current_head()
    if head is None:
        raise RuntimeError("No Alembic head revision is bundled")
    return head


def current_revision(engine: Engine) -> str | None:
    if not inspect(engine).has_table("alembic_version"):
        return None
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def assert_schema_compatible(engine: Engine) -> None:
    revision = current_revision(engine)
    if revision is None:
        raise IncompatibleSchemaError("Database has not been migrated")
    script = ScriptDirectory.from_config(_config())
    try:
        script.get_revision(revision)
    except Exception as exc:
        raise IncompatibleSchemaError(
            f"Database revision {revision!r} is not supported by this application"
        ) from exc
    if revision != script.get_current_head():
        raise IncompatibleSchemaError(
            f"Database revision {revision!r} requires upgrade to {script.get_current_head()!r}"
        )


def _assert_known_revision(revision: str | None) -> None:
    if revision is None:
        return
    try:
        ScriptDirectory.from_config(_config()).get_revision(revision)
    except Exception as exc:
        raise IncompatibleSchemaError(
            f"Database revision {revision!r} is not supported by this application"
        ) from exc


def backup_database(database_path: Path, backup_dir: Path) -> Path:
    """Create a checkpoint-safe SQLite backup using the SQLite backup API."""
    database_path = database_path.resolve()
    backup_dir = backup_dir.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    database_size = database_path.stat().st_size
    required_bytes = max(database_size * 2, 1024 * 1024)
    if shutil.disk_usage(backup_dir).free < required_bytes:
        raise InsufficientMigrationSpaceError(
            f"Migration backup requires at least {required_bytes} free bytes"
        )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / (
        f"{database_path.stem}.pre-migration.{timestamp}.{uuid4().hex[:8]}.db"
    )
    with sqlite3.connect(database_path) as source, sqlite3.connect(backup_path) as destination:
        source.backup(destination)
    return backup_path


def restore_database(backup_path: Path, database_path: Path) -> None:
    """Restore a SQLite database from a validated backup without naive file copying."""
    with (
        sqlite3.connect(backup_path.resolve()) as source,
        sqlite3.connect(database_path.resolve()) as destination,
    ):
        source.backup(destination)


def upgrade_safely(database_path: Path, *, backup_dir: Path) -> MigrationOutcome:
    """Upgrade to head, backing up and restoring an existing older database on failure."""
    database_path = database_path.resolve()
    existed_with_data = database_path.is_file() and database_path.stat().st_size > 0
    engine = create_sqlite_engine(database_path)
    previous_revision = current_revision(engine)
    _assert_known_revision(previous_revision)
    head = supported_head()
    if previous_revision == head:
        return MigrationOutcome(engine, previous_revision, head, None)

    backup_path = backup_database(database_path, backup_dir) if existed_with_data else None
    config = _config()
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        assert_schema_compatible(engine)
    except Exception as exc:
        engine.dispose()
        if backup_path is not None:
            restore_database(backup_path, database_path)
            raise MigrationFailedError(
                "Database migration failed; the pre-migration backup was restored",
                backup_path=backup_path,
            ) from exc
        raise
    return MigrationOutcome(engine, previous_revision, head, backup_path)


def upgrade(database_path: Path, revision: str = "head") -> Engine:
    engine = create_sqlite_engine(database_path)
    config = _config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
    assert_schema_compatible(engine)
    return engine
