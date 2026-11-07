# MT Auto Music & Karaoke Studio

Portable, headless-first Windows media production engine. **Status: architecture and foundation scaffold; production pipeline not implemented yet.**

## Purpose
For each of 1–N user-selected song folders, (A) embed cover art into a **copy** of an existing MP3 without audio re-encoding and (B) generate an MP4 with a user-selected still image displayed for the entire song and Thai karaoke lyrics synchronized to the original recording.

## Architectural principles
- Modular monolith + ports/adapters, UI-agnostic Python engine.
- Durable workflow orchestration, step/job/batch states, recoverable jobs.
- Operational SSOT: SQLite; asset SSOT: immutable files + hashes; engineering SSOT: Git.
- Event outbox for reliable UI synchronization; Qt bridge is an adapter, not a domain dependency.
- Central PathManager; portable Windows onedir packaging; never mutate source assets.
- Arabic numerals (0–9) for all program-generated presentation, irrespective of Windows locale.
- Quality gates for media integrity and human review for uncertain lyrics alignment.

## Planned deliverables
1. `song_with_cover.mp3` — MP3 audio frames preserved, with embedded ID3/APIC cover.
2. `karaoke.mp4` — 1080p/30 fps H.264/AAC baseline, fixed user image, synced Thai lyrics.
3. Internal `timing.json`, `karaoke.ass`, `qc_report.json`, and manifest.

## Repository map
- [Project charter](PROJECT_CHARTER.md)
- [Architecture](ARCHITECTURE.md)
- [Requirements](REQUIREMENTS.md)
- [KPI framework](KPI_FRAMEWORK.md)
- [Roadmap](DEVELOPMENT_ROADMAP.md)
- [Contracts](docs/contracts/README.md)
- [Decisions](docs/adr/0001-foundation.md)
- [Engine scaffold](src/mt_engine/)
- [Tests](tests/)

## Local development
Requires Python 3.11+ for development.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

No installer or executable is published yet. No automatic lyrics alignment or video rendering is implemented in this foundation milestone.
