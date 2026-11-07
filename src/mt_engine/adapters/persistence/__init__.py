"""SQLite operational SSOT adapter."""

from .db import create_sqlite_engine, session_factory
from .migration import IncompatibleSchemaError, current_revision, upgrade

__all__ = [
    "IncompatibleSchemaError",
    "create_sqlite_engine",
    "current_revision",
    "session_factory",
    "upgrade",
]
