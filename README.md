# MT Auto Music & Karaoke Studio

**Project foundation baseline v0.1.0 | Milestone 1 persistence slice implemented; engine features not finished.**

This project is a local-first, portable Windows application with a Python headless production engine. Each of **1–N user-selected song directories** provides an existing MP3, optional cover/background images and optional TXT/DOCX lyrics. The engine will **embed a cover image into a copy of the existing MP3 without audio re-encoding** and create an **MP4 with the user-selected still image shown throughout the song plus synchronized Thai karaoke text**. No music generation is included.

## Platform decisions
- **CPython 3.12.10 x64** is the primary development runtime.
- **SQLite + SQLAlchemy 2.x + Alembic** for operational SSOT and all schema migrations.
- Modular Monolith + Hexagonal/Ports & Adapters + Event-Driven Orchestrator.
- Future **PySide6 Windows UI**, portable onedir executable without installer.
- Central PathManager for relocatable bundles and workspaces; UI-generated numbers always ASCII digits 0–9.
- Original MP3 and other source assets never overwritten; verified staged outputs only.
- Alignment accuracy requires measured Thai song benchmark and a human review path.

## Clone and set up developer environment (Windows CMD)
```bat
git clone https://github.com/idev006/MT-Auto-Music-Karaoke-Studio.git
cd MT-Auto-Music-Karaoke-Studio
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -v
```
On an existing clone, `git pull --ff-only origin main` and check `dir pyproject.toml`. Do not delete uncommitted files. A clean development install pulls SQLAlchemy and Alembic as project dependencies. The initial reviewed migration is bundled and is exercised through the programmatic persistence migration API and automated tests.

## Documentation index
Start with [Documentation Index](docs/README.md) for detailed links. Key entrypoints:
- [Project charter](PROJECT_CHARTER.md)
- [System architecture](ARCHITECTURE.md)
- [Requirements](REQUIREMENTS.md)
- [KPI framework](KPI_FRAMEWORK.md)
- [Development roadmap](DEVELOPMENT_ROADMAP.md)
- [SSOT and Alembic design](docs/03-DATABASE-SSOT-ALEMBIC.md)
- [Test strategy](docs/07-TEST-STRATEGY.md)
- [Windows portable / UI](docs/08-WINDOWS-PORTABLE-AND-UI.md)

## Current implementation status
Present: repository governance docs, Python package foundation, PathManager prototype, Arabic numeral display helper, SQLAlchemy operational models, initial Alembic revision, migration compatibility guard, basic tests and a Windows GitHub Actions workflow. Not yet present: operational repositories, state-machine/orchestrator implementation, cover embedding, alignment, karaoke video renderer, PySide6 UI, runnable portable EXE. CI passing status has not been independently verified. See [Traceability Matrix](docs/10-REQUIREMENT-TRACEABILITY.md) and [M1 Gap Analysis](docs/11-M1-GAP-ANALYSIS.md).
