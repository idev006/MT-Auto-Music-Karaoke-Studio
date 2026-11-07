# MT Auto Music & Karaoke Studio — Documentation Index

Documentation baseline date: 2026-11-07. **Milestone 1 persistence slice is implemented and locally verified; the product is not implementation-complete.**

## Read in this order
1. [Project Charter](../PROJECT_CHARTER.md) — goals, scope and non-goals.
2. [System Specification](01-SYSTEM-SPECIFICATION.md) — users, inputs, outputs and acceptance gates.
3. [Architecture](../ARCHITECTURE.md) — system shape and dependency boundaries.
4. [Pipeline and State Machine](02-PIPELINE-AND-STATE-MACHINE.md) — whole-run execution, ownership, states and retries.
5. [End-to-End Sequences](11-END-TO-END-SEQUENCES.md) — normative happy, failure, retry, cancel and crash interactions.
6. [Database / SSOT / Alembic](03-DATABASE-SSOT-ALEMBIC.md) — schemas, migration policy and data durability.
7. [Module Contracts](06-MODULE-CONTRACTS.md) — ports, adapters, DTOs and versioning.
8. [Error & Recovery](04-ERROR-RECOVERY.md) — fault matrix, recovery policy and injection scenarios.
9. [Karaoke Object & Presets](05-KARAOKE-OBJECT-AND-PRESETS.md) — 14 groups / 84 properties and 8 x 5 catalog.
10. [KPI Framework](../KPI_FRAMEWORK.md) — 10 groups / 32 planned indicators.
11. [Testing Strategy](07-TEST-STRATEGY.md) — CI, fixtures, benchmarking and evidence.
12. [Windows Portable & PySide6](08-WINDOWS-PORTABLE-AND-UI.md) — UI independence, portable deployment and path policy.
13. [Operations & Delivery](09-USER-OPERATIONS-AND-DELIVERY.md) — input examples, QC and outputs.
14. [Requirements Traceability](10-REQUIREMENT-TRACEABILITY.md) — evidence/status for each feature.
15. [Development Roadmap](../DEVELOPMENT_ROADMAP.md) — milestones M0–M6.
16. [ADR-0001](adr/0001-foundation.md), [ADR-0002](adr/0002-python-sqlite-alembic.md) and [ADR-0003](adr/0003-job-run-worker-and-restart-policy.md) — architecture decisions.
17. [Contract Registry](contracts/README.md) — planned versioned contracts.
18. [M1 Gap Analysis](11-M1-GAP-ANALYSIS.md) — evidence-backed implementation status and next dependency.
19. [Agile/Kanban Product Delivery Plan](superpowers/plans/2026-11-07-product-delivery-kanban.md) — phased execution, WIP policy and acceptance gates.

## Current decisions
- Windows x64 primary development runtime Python 3.12.10 in a local virtual environment.
- SQLite + SQLAlchemy 2.x + Alembic required. Initial operational schema revision `106a0b13ddd3` is implemented; backup/restore orchestration remains pending.
- PySide6 portable app follows a headless Python engine; no Installer.exe.
- Existing MP3 remains the audio source; embed cover only into a copy; separate MP4 with a user-provided still image and synchronized lyrics.
- Multiple folders (1–N) with independent jobs and partial success behavior.
- One active logical JobWorker owns one folder run; failure/retry creates a new whole run rather than resuming steps in version 1.
- Multiple jobs may progress concurrently, while faster-whisper, Demucs and final FFmpeg render share one initial HEAVY token.
- SSOT, Event Gateway, Orchestrator, Central PathManager and automated tests are foundational.
- All program-generated displayed numbers use Arabic/ASCII digits 0–9.

## Source status
`src/mt_engine` currently contains PathManager, number formatter, v1 boundary contracts, typed state machines and the initial persistence adapter. The implemented initial schema predates ADR-0003; a follow-up migration is required before JobWorker implementation. Full repositories/coordinator, audio analysis, artwork generation, MP4 karaoke renderer and GUI are planned. Local tests are evidence only for their stated scope; no claim of passing remote CI or Windows portable acceptance is made.
