# Development roadmap

## Milestone 0 — Repository governance (this commit)
- Architecture/requirements/KPIs, ADRs, contracts, project layout and basic deterministic PathManager tests.
- Not a functioning karaoke renderer.

## Milestone 1 — Headless foundation
- SQLite migrations, job and event schemas, orchestration state machine, durable outbox, CLI, intake 1–N folders.
- Automated tests: state transitions, restart/reconnect, paths, unicode, ambiguous assets, idempotency.

## Milestone 2 — MP3 vertical slice
- Mutagen cover embed on copied MP3, readback, audio-frame integrity verification, staging/publishing.
- Test on representative MP3 metadata and corruption cases.

## Milestone 3 — MP4 deterministic slice
- Approved timing fixture -> ASS subtitles -> still-image FFmpeg MP4 -> media QC.
- Reference frames and Thai typography parity tests, CPU/render benchmarks.

## Milestone 4 — Thai alignment and review
- Audio analysis and adapter experiments, lyrics parsing (TXT/DOCX), phrase/word alignment.
- Build annotated benchmark first. Add confidence flags/manual override. Never claim 100% alignment without evidence.

## Milestone 5 — Preset library and batch hardening
- Karaoke object schema (14 groups) and staged library (8 -> 24 -> 40), schema compatibility, resilience, retry, cache invalidation, fault injection.

## Milestone 6 — Windows PySide6 desktop and portable delivery
- Qt signal/slot bridge, folder selector, job dashboard, timing review, preview and preset inspector.
- Windows one-folder bundle including vetted FFmpeg/fonts; clean-PC and relocated-path acceptance.

## Exit policy
Each milestone requires contracts, tests, QA evidence and updated ADRs. Prefer vertical end-to-end proof over prematurely implementing all 48 planned capabilities.
