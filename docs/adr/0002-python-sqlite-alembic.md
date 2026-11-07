# ADR-0002: Python 3.12 and Alembic-managed SQLite

- **Status:** Accepted for development baseline
- **Date:** 2026-11-07
- **Drivers:** Windows development environment has CPython 3.12.10; project needs reliable schema evolution, portability and an operational SSOT.

## Decision
1. Develop and test primarily on **CPython 3.12.10 x64** with per-project `.venv`.
2. Use SQLite for one-machine operational SSOT.
3. Use SQLAlchemy 2.x as persistence abstraction.
4. Use **Alembic for every production SQLite schema migration**. Explicit revision history belongs in source control and portable bundle.
5. Use migration checks/backup at startup before workers begin; reject unknown future revisions.
6. No production `metadata.create_all()` for upgrades; do not rewrite user DB schema ad hoc.
7. Include migration upgrade/rollback/failure tests in CI and release acceptance.

## Consequences
- `pyproject.toml` declares SQLAlchemy/Alembic runtime dependencies and Python >=3.12,<3.13 (for current baseline).
- Dev `pip install -e ".[dev]"` installs these dependencies.
- Future migration infrastructure will include `alembic.ini`, `migrations/env.py` and version scripts whose DB URL is obtained from PathManager.
- A source distribution without migration scripts cannot claim fully implemented SQLite persistence.
- Update Python support only through verified compatibility tests for PySide6, AI components and Windows portable packaging.

## Alternatives rejected
- Manual versionless DDL: unsafe and untraceable.
- `create_all` on every startup: does not manage schema evolution.
- Remote database or distributed microservices: unnecessary for initial local Windows target.
