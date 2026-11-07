# Operational SSOT — SQLite, SQLAlchemy 2.x and Alembic

**Mandatory decision:** SQLite uses SQLAlchemy 2.x for persistence and **Alembic for every production database schema migration**. Never use `metadata.create_all()` as a production schema upgrade strategy. Python development baseline: CPython 3.12.10 x64.

## Ownership
- Operational truth (Batch/Job/JobRun/branch state, ownership, approvals, revisions, event outbox, errors and published artifact manifests) lives in SQLite. Version 1 does not persist fine-grained step checkpoints for resume.
- File bytes live in filesystem; database stores safe root_id + relative locator + content hash + metadata.
- Versioned project schemas/configuration/presets live in Git; deployed presets are versioned immutable bundles.
- GUI is a projection; never independently mutates operational state.

## Initial normalized relational schema
| Table | Key / notable columns | Invariant |
|---|---|---|
| projects | id, name, created_at | project ownership |
| batches | id, project_id, state, revision, config_id | multiple jobs |
| jobs | id, batch_id, source_root_id, state, revision, active_run_id | one song folder; at most one active run |
| job_runs | id, job_id, state, revision, owner_id, owner_epoch, lease expiration, input/config hashes | immutable execution history; retry creates a row |
| job_run_branches | run_id, branch, state, revision | independent MP3/MP4 outcomes |
| assets | id, job_id, root_id, relpath, role, sha256, size, media_meta_json | role mapping audit |
| configurations | id, schema_version, hash, payload_json | immutable config revision |
| lyrics_revisions | id, job_id, source_asset_id, text_hash, normalized_json, approval | original text retained |
| timing_revisions | id, job_id, lyrics_revision_id, timeline_json, approval, model_version | approved reference |
| workflow_steps | id, job_id, kind, state, latest_attempt, revision | legacy foundation table; not operational SSOT for v1 whole-run resume |
| step_attempts | id, step_id, started_at, finished_at, error_id, worker_id, input_hash | legacy diagnostics/reserved evolution |
| artifacts | id, job_id, run_id, branch, operation_id, owner_epoch, input/config hashes, locator, sha256, validation, status | fenced and verified before publish |
| errors | id, job_id, step_id, code, severity, retryable, details_json, correlation_id | diagnostic record |
| outbox_events | seq autoincrement, event_id unique, type, payload_json, emitted_at, delivered_at | transactional outbox |
| job_ownership | job_id/run_id, owner_id, owner_epoch, lease_expiration, heartbeat | one active logical JobWorker owner |
| consumer_cursors | consumer_id, last_seq, updated_at | independent event replay/reconnect |
| schema_metadata | key, value | optional app metadata (Alembic revision stays in alembic_version) |

## Migration lifecycle
1. Engineers alter SQLAlchemy model and add explicit Alembic revision.
2. Run `alembic revision --autogenerate -m "..." ` only as a draft; **manually review** output.
3. Test upgrade from fresh DB and previous fixture; run foreign-key integrity checks.
4. Back up existing SQLite DB before migration; check free disk, exclusive app-level DB lock and schema version.
5. Perform `alembic upgrade head`; verify current revision and application schema compatibility.
6. A newer-than-supported DB revision must block startup safely, not be silently downgraded.
7. Migration failure -> rollback/restore from valid backup, stop production worker startup, report diagnostic.
8. Release artifacts bundle all revisions and compatible SQLAlchemy models.

## SQLite specifics
- Configure `PRAGMA foreign_keys=ON` for every connection.
- Consider WAL for desktop concurrency, set `busy_timeout` and use a single writer coordinator for state transitions.
- Do not store large audio/image bytes in SQLite; use hashes/locators.
- Backup with SQLite backup API or a checkpoint-safe mechanism, not naive copy while WAL is active.
- Use explicit transactions for state update + outbox insert; unique request IDs and optimistic revisions.
- Use coordinator/database time and a monotonic owner epoch for ownership fencing; never trust worker wall clocks for correctness.
- Avoid autogenerate assumptions around constraints and SQLite table rebuilds: Alembic `batch_alter_table` may be necessary.

## Directory design
```text
alembic.ini
migrations/
  env.py
  script.py.mako
  versions/
src/mt_engine/adapters/persistence/
  db.py
  models.py
  repositories.py
```
The migration configuration resolves the database path through PathManager/runtime configuration. No machine-specific paths in alembic.ini.

## Required tests
Upgrade empty DB, upgrade previous release, verify tables/indexes/FKs and revision head, reject incompatible future revision, preserve sample job records across migration, rollback from interrupted/corrupt update, and test moved portable application DB.

Alembic runtime/configuration, SQLAlchemy models, initial revision `106a0b13ddd3` and ADR-0003 follow-up revision `b7f41c92a003` are implemented. The follow-up adds JobRuns, one-active-run enforcement, owner epoch/lease fields, branch outcomes, consumer cursors and artifact provenance. Fresh upgrade, previous-revision data preservation, model/migration parity, table/FK inspection, atomic run/outbox rollback, stale revision/ownership rejection and incompatible-revision rejection have local automated tests. Safe upgrade uses the SQLite backup API, performs a free-space preflight and restores the prior database after an injected migration failure.
