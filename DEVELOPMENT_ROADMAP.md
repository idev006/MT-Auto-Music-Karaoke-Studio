# Development roadmap — evidence-driven milestones

Primary development runtime: **CPython 3.12.10 x64**. SQLite persistence requires **SQLAlchemy 2.x + Alembic**. All milestones require contract, tests and evidence before a VERIFIED label.

## M0 — Project documentation & scaffold — COMPLETE
Architecture, requirements, KPIs, error recovery, module contracts, data model and Alembic design, UI/portable policy, traceability, initial PathManager and number-format unit tests.
**Status: documentation and scaffold created**; actual migration engine/production features not yet implemented.

## M1 — Headless operational foundation — PARTIAL
Freeze versioned boundary contracts and ADR-0003 state machines. Add the follow-up Alembic schema for immutable JobRuns, one-owner fencing, branch outcomes, artifact provenance and event cursors. Implement transactional repositories, Batch Coordinator, one logical JobWorker per active folder run, shared heavyweight resource governor, multi-folder intake and CLI commands. Failure/cancel/interruption is terminal for a run; Retry starts a new run from intake. Add automated ownership/race/migration/fault tests.

## M2 — MP3 artwork vertical slice — IMPLEMENTED AND LOCALLY VERIFIED
Asset validation -> copy MP3 -> Mutagen ID3/APIC -> verify audio frame integrity and preserved metadata -> stage/QC/publish. Test damaged files, ambiguous mapping and ID3 variants.

## M3 — Deterministic MP4 vertical slice — IMPLEMENTED FOR DIAGNOSTIC/LOCKED CANDIDATES
Use pre-approved timing fixture and user-selected still image -> ASS subtitle -> FFmpeg H.264/AAC -> decode/duration/frame QC -> publish. Test Thai fonts and MP4 playback.

## M4 — Thai lyrics intelligence — ACTIVE RELEASE BLOCKER
Build human-annotated baseline on actual Thai songs, analyze vocal alignment tools, compare MAE/P95, provide review/correction workflow, keep AI provider modular.

## M5 — Batch recovery, presets and media QA — PARTIAL
Karaoke display object (14 groups), presets staged 8 -> 24 -> 40, optional cache based on measured need, error injection, cancel/pause/whole-run retry and resource benchmarks. Fine-grained resume requires a future ADR and is not part of version 1.

## M6 — Windows PySide6 & portable release — UI IMPLEMENTED; CLEAN-PC RELEASE NOT VERIFIED
Build signal/slot event bridge and desktop UI, progress dashboard, preset browser, timeline editor and preview. PyInstaller onedir with resources including Alembic migrations. Test relocated folder, fresh Windows without Python, Thai/English locale ASCII digits and 8 GB RAM performance.

## Gate policy
A passing test runner alone is insufficient; archive concrete evidence and trace requirements to tested behavior. All existing source media remains immutable. Scope creep outside MP3 cover + MP4 karaoke requires explicit decision.
