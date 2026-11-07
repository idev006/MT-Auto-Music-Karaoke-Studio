"""Programmatic Alembic lifecycle and application schema compatibility checks."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from .db import create_sqlite_engine


class IncompatibleSchemaError(RuntimeError):
    """The database revision is absent from this application's migration graph."""


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


def upgrade(database_path: Path, revision: str = "head") -> Engine:
    engine = create_sqlite_engine(database_path)
    config = _config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
    assert_schema_compatible(engine)
    return engine
