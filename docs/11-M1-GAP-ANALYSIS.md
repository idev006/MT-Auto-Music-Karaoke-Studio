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
| Migration backup and recovery | NOT IMPLEMENTED | Requires SQLite backup API, disk preflight, restore and failure-injection tests. |
| ADR-0003 follow-up schema | NOT IMPLEMENTED | Initial revision predates JobRun, branch outcome, job ownership/epoch, consumer cursor and full artifact provenance requirements. |
| Operational repositories | NOT IMPLEMENTED | Optimistic concurrency, idempotent request handling, one-owner fencing and query projections are next. |
| Batch/Job/JobRun/Branch state machines | NOT IMPLEMENTED | Approved states and aggregation truth are documented; legal transition code is absent. |
| Batch Coordinator and JobWorker | NOT IMPLEMENTED | One-owner whole-run execution, shared HEAVY token, cancel race and stale-result rejection are absent. |
| Multi-folder asset intake | NOT IMPLEMENTED | Discovery, classification and ambiguity contracts have no implementation. |
| Headless CLI | NOT IMPLEMENTED | No command entry point exists. |
| Remote CI | DOCUMENTED, NOT VERIFIED | Workflow exists; this local run does not establish GitHub Actions status. |

## Local quality evidence

- Environment: Windows, CPython 3.12.10 x64.
- `python -m pytest -q`: 12 passed, 0 failed, 0 skipped.
- `python -m ruff check src tests migrations`: passed with no findings.
- No KPI score is claimed beyond these test counts; media, performance, portability and remote-CI gates were not run.

## Next dependency-ordered slice

Implement M1-00 versioned boundary contracts and typed Batch/Job/JobRun/Branch/Artifact states. Then add the ADR-0003 follow-up migration and repository commands with optimistic revision/owner fencing plus atomic outbox insertion before implementing the Batch Coordinator and JobWorker.
