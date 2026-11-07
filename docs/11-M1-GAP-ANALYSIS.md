# Milestone 1 gap analysis

Evidence date: 2026-11-07. Scope: local repository at the current working tree. A filename or design document is not counted as implementation evidence.

| Capability | Status | Evidence / gap |
|---|---|---|
| PathManager and ASCII numeral formatter | VERIFIED | Existing unit tests pass for relocation, Unicode path, traversal and digit conversion. |
| SQLAlchemy operational data model | IMPLEMENTED | Models cover all tables in `docs/03-DATABASE-SSOT-ALEMBIC.md`; behavioral repository APIs are not yet implemented. |
| Initial Alembic migration | VERIFIED | Revision `106a0b13ddd3`; automated fresh upgrade validates the exact 15-table inventory and current head. |
| SQLite connection safeguards | VERIFIED | Automated test observes `foreign_keys=1`; adapter sets a bounded busy timeout. WAL policy remains pending. |
| Startup schema compatibility | VERIFIED | Unmigrated, stale and unknown/future revisions fail closed through the migration adapter; future-revision test is present. |
| Transactional outbox schema | VERIFIED (schema/transaction boundary) | Unique event IDs, pending-event index and state+event rollback test. Dispatcher/delivery cursor is not implemented. |
| Migration backup and recovery | VERIFIED | Safe upgrade uses SQLite backup API, disk preflight, previous-revision preservation and restore after injected destructive failure. |
| ADR-0003 follow-up schema | VERIFIED | Revision `b7f41c92a003` adds JobRuns, branch outcomes, one-active-run constraint, owner epoch/lease, consumer cursors and artifact provenance; Alembic reports no model drift. |
| Operational Run repository | VERIFIED (foundation) | Atomic run/branches/outbox creation, optimistic revision, one-active-run rejection, owner claim/epoch and stale-owner rejection are tested. Completion/cancel commands and query projections remain. |
| Versioned boundary contracts | VERIFIED (v1 foundation) | Immutable fenced ToolRequest/ToolResult, DomainEvent and ArtifactManifest contracts plus deterministic primitive serialization and architecture import tests. |
| Batch/Job/JobRun/Branch/Artifact/Review state machines | VERIFIED (domain foundation) | Typed enums, legal transition guards and branch aggregation truth tests are implemented; persistence integration is pending. |
| Batch Coordinator and JobWorker | NOT IMPLEMENTED | One-owner whole-run execution, shared HEAVY token, cancel race and stale-result rejection are absent. |
| Single-folder asset intake | VERIFIED (vertical slice) | Unicode folder discovery requires exactly one MP3 and one image; assigning one image to cover and background requires an explicit flag. Multi-folder intake remains absent. |
| Headless CLI | IMPLEMENTED (vertical slice) | `mt-karaoke produce-song` produces real MP3/MP4 artifacts but does not yet drive the SQLite coordinator/JobWorker. |
| MP3 artwork output | VERIFIED (fixture) | APIC readback matches the input image and MP3 audio-frame payload hashes are identical. |
| Karaoke MP4 output | VERIFIED (fixture) | FFmpeg full decode passed; ffprobe reports 1920x1080 H.264/yuv420p plus AAC. Timing remains review-required. |
| Remote CI | DOCUMENTED, NOT VERIFIED | Workflow exists; this local run does not establish GitHub Actions status. |

## Local quality evidence

- Environment: Windows, CPython 3.12.10 x64.
- `python -m pytest -q`: 57 passed, 0 failed, 0 skipped.
- `python -m ruff check src tests migrations`: passed with no findings.
- Real-media fixture evidence is recorded in document 12. No alignment, concurrency, performance, portability or remote-CI KPI is claimed.

## Next dependency-ordered slice

Connect the proven media adapters to typed error/whole-run retry commands, then implement the Batch Coordinator, one-folder JobWorker and shared HEAVY resource token before enabling multi-folder execution.
