"""SQLite operational SSOT adapter."""

from .db import create_sqlite_engine, session_factory
from .migration import (
    IncompatibleSchemaError,
    InsufficientMigrationSpaceError,
    MigrationFailedError,
    MigrationOutcome,
    current_revision,
    upgrade,
    upgrade_safely,
)

__all__ = [
    "IncompatibleSchemaError",
    "InsufficientMigrationSpaceError",
    "MigrationFailedError",
    "MigrationOutcome",
    "create_sqlite_engine",
    "current_revision",
    "session_factory",
    "upgrade",
    "upgrade_safely",
]
