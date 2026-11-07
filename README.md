# MT Auto Music & Karaoke Studio

**Headless media vertical slice v0.2.0 | Real single-folder E2E verified; orchestration and alignment quality remain unfinished.**

This project is a local-first, portable Windows application with a Python headless production engine. Each of **1–N user-selected song directories** provides an existing MP3, optional cover/background images and optional TXT/DOCX lyrics. The engine will **embed a cover image into a copy of the existing MP3 without audio re-encoding** and create an **MP4 with the user-selected still image shown throughout the song plus synchronized Thai karaoke text**. No music generation is included.

The default video canvas follows the selected background image: portrait images produce 1080×1920 (9:16), while landscape and square images produce 1920×1080 (16:9).

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
Present: persistence and state foundations, fenced run repository, safe migrations, versioned engine contracts, a real single-folder headless CLI, ID3 cover embedding without MP3 audio re-encoding, faster-whisper transcription, ASS karaoke generation, and FFmpeg H.264/AAC rendering with decode/probe QC. The Thai fixture `เหงาเหลือเกิน` completed locally into the matching destination folder; see [E2E evidence](docs/12-E2E-MEDIA-EVIDENCE.md).

This is a vertical slice, not a production release. The CLI currently runs the media path directly and is not yet connected to the SQLite coordinator/JobWorker/resource governor. Timing is an ASR-guided proposal requiring human review; no alignment KPI is claimed. Multi-folder scheduling, PySide6 UI, and portable EXE remain pending. CI status has not been independently verified.
