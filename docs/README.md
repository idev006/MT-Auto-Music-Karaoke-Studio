# MT Auto Music & Karaoke Studio — Documentation Index

Documentation baseline date: 2026-11-07. **Milestone 1 persistence slice is implemented and locally verified; the product is not implementation-complete.**

## Read in this order
1. [Project Charter](../PROJECT_CHARTER.md) — goals, scope and non-goals.
2. [System Specification](01-SYSTEM-SPECIFICATION.md) — users, inputs, outputs and acceptance gates.
3. [Architecture](../ARCHITECTURE.md) — system shape and dependency boundaries.
4. [Pipeline and State Machine](02-PIPELINE-AND-STATE-MACHINE.md) — execution DAG, branch outcomes and retries.
5. [Database / SSOT / Alembic](03-DATABASE-SSOT-ALEMBIC.md) — schemas, migration policy and data durability.
6. [Module Contracts](06-MODULE-CONTRACTS.md) — ports, adapters, DTOs and versioning.
7. [Error & Recovery](04-ERROR-RECOVERY.md) — fault matrix, recovery policy and injection scenarios.
8. [Karaoke Object & Presets](05-KARAOKE-OBJECT-AND-PRESETS.md) — 14 groups / 84 properties and 8 x 5 catalog.
9. [KPI Framework](../KPI_FRAMEWORK.md) — 10 groups / 32 planned indicators.
10. [Testing Strategy](07-TEST-STRATEGY.md) — CI, fixtures, benchmarking and evidence.
11. [Windows Portable & PySide6](08-WINDOWS-PORTABLE-AND-UI.md) — UI independence, portable deployment and path policy.
12. [Operations & Delivery](09-USER-OPERATIONS-AND-DELIVERY.md) — input examples, QC and outputs.
13. [Requirements Traceability](10-REQUIREMENT-TRACEABILITY.md) — evidence/status for each feature.
14. [Development Roadmap](../DEVELOPMENT_ROADMAP.md) — milestones M0–M6.
15. [ADR-0001](adr/0001-foundation.md) and [ADR-0002](adr/0002-python-sqlite-alembic.md) — architecture decisions.
16. [Contract Registry](contracts/README.md) — planned versioned contracts.
17. [M1 Gap Analysis](11-M1-GAP-ANALYSIS.md) — evidence-backed implementation status and next dependency.

## Current decisions
- Windows x64 primary development runtime Python 3.12.10 in a local virtual environment.
- SQLite + SQLAlchemy 2.x + Alembic required. Initial operational schema revision `106a0b13ddd3` is implemented; backup/restore orchestration remains pending.
- PySide6 portable app follows a headless Python engine; no Installer.exe.
- Existing MP3 remains the audio source; embed cover only into a copy; separate MP4 with a user-provided still image and synchronized lyrics.
- Multiple folders (1–N) with independent jobs and partial success behavior.
- SSOT, Event Gateway, Orchestrator, Central PathManager and automated tests are foundational.
- All program-generated displayed numbers use Arabic/ASCII digits 0–9.

## Source status
`src/mt_engine` currently contains an initial PathManager, number formatter and persistence adapter. Full operational repositories/orchestrator, audio analysis, artwork generation, MP4 karaoke renderer and GUI are planned. Local tests are evidence only for their stated scope; no claim of passing remote CI or Windows portable acceptance is made.
