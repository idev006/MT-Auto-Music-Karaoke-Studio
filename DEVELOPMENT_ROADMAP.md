# Development roadmap — evidence-driven milestones

Primary development runtime: **CPython 3.12.10 x64**. SQLite persistence requires **SQLAlchemy 2.x + Alembic**. All milestones require contract, tests and evidence before a VERIFIED label.

## M0 — Project documentation & scaffold
Architecture, requirements, KPIs, error recovery, module contracts, data model and Alembic design, UI/portable policy, traceability, initial PathManager and number-format unit tests.
**Status: documentation and scaffold created**; actual migration engine/production features not yet implemented.

## M1 — Headless operational foundation
Define SQLAlchemy schema, create first explicit Alembic revision, upgrade fresh SQLite and previous fixture, startup revision check, file-backed SSOT, transactional outbox, state machine, durable workflow orchestrator, batch folder intake and CLI commands. Add automated state/migration/fault tests.

## M2 — MP3 artwork vertical slice
Asset validation -> copy MP3 -> Mutagen ID3/APIC -> verify audio frame integrity and preserved metadata -> stage/QC/publish. Test damaged files, ambiguous mapping and ID3 variants.

## M3 — Deterministic MP4 vertical slice
Use pre-approved timing fixture and user-selected still image -> ASS subtitle -> FFmpeg H.264/AAC -> decode/duration/frame QC -> publish. Test Thai fonts and MP4 playback.

## M4 — Thai lyrics intelligence
Build human-annotated baseline on actual Thai songs, analyze vocal alignment tools, compare MAE/P95, provide review/correction workflow, keep AI provider modular.

## M5 — Batch recovery, presets and media QA
Karaoke display object (14 groups), presets staged 8 -> 24 -> 40, step invalidation/cache, error injection, cancel/pause/retry/resume, resource benchmarks.

## M6 — Windows PySide6 & portable release
Build signal/slot event bridge and desktop UI, progress dashboard, preset browser, timeline editor and preview. PyInstaller onedir with resources including Alembic migrations. Test relocated folder, fresh Windows without Python, Thai/English locale ASCII digits and 8 GB RAM performance.

## Gate policy
A passing test runner alone is insufficient; archive concrete evidence and trace requirements to tested behavior. All existing source media remains immutable. Scope creep outside MP3 cover + MP4 karaoke requires explicit decision.
