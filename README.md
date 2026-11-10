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

## Optional OpenRouter Vision QC

OpenRouter is an optional, budgeted second-opinion adapter for timestamped transcription and rendered-frame QC. Copy `config/openrouter.env.example` to the Git-ignored `config/openrouter.env`, set `OPENROUTER_API_KEY`, and select `OPENROUTER_MODE=off|auto|always`. `off` is local-only. `auto` escalates transcription only when local coverage, alignment evidence, or structural validation is weak, and skips Vision QC when local evidence does not require it. `always` requests a cloud transcription second opinion and runs eligible Vision QC for every song. The shared per-song ledger rejects reported spend above `OPENROUTER_MAX_COST_USD_PER_SONG`, whose accepted maximum is USD 0.20; the request guard prevents a new request when insufficient budget remains. Never put the real key in the example file, source code, command line, logs, or Git. The CLI can override the configured policy for one run with `--openrouter-mode off|auto|always`.

The built-in karaoke visual catalog contains 12 versioned presets in Classic, Modern, Neon,
Romantic, Fun and Accessible groups. Run `mt-karaoke list-presets` to inspect them and select one
with `produce-song --karaoke-preset romantic-rose`. Presets change ASS presentation only; lyric
text and timing remain owned by their existing SSOT.

Use `mt-karaoke preview-presets --background <image> --output-dir <folder> --ffmpeg-root <folder>`
to render one production-libass PNG per preset plus a contact sheet and hash-bound manifest. This
fast path has no audio, alignment, or MP4 work and is the required visual-design check before an
expensive video render.

Vision QC verifies rendered text only; it does not replace the ASR/audio temporal-sync gate. The adapter requests provider data collection denial, fails closed to `REVIEW_REQUIRED`, and records model results without recording the API key.
