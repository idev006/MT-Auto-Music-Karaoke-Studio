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
| Operational repositories | NOT IMPLEMENTED | Optimistic concurrency, idempotent request handling and query projections are next. |
| Batch/job/step state machines | NOT IMPLEMENTED | States are documented and persisted as strings but legal transition logic is absent. |
| Durable workflow orchestrator | NOT IMPLEMENTED | Leasing, retry, checkpoint, cancel/resume and crash recovery are absent. |
| Multi-folder asset intake | NOT IMPLEMENTED | Discovery, classification and ambiguity contracts have no implementation. |
| Headless CLI | NOT IMPLEMENTED | No command entry point exists. |
| Remote CI | DOCUMENTED, NOT VERIFIED | Workflow exists; this local run does not establish GitHub Actions status. |

## Local quality evidence

- Environment: Windows, CPython 3.12.10 x64.
- `python -m pytest -q`: 12 passed, 0 failed, 0 skipped.
- `python -m ruff check src tests migrations`: passed with no findings.
- No KPI score is claimed beyond these test counts; media, performance, portability and remote-CI gates were not run.

## Next dependency-ordered slice

Implement typed batch/job/step states and repository commands that update an aggregate with an optimistic revision check while appending an outbox event in the same transaction. Then add duplicate request, illegal transition, stale revision and job-isolation tests before introducing the orchestrator scheduler.
