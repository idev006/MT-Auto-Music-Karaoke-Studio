# Architecture baseline — MT Auto Music & Karaoke Studio

Status: implemented diagnostic vertical slice; alignment/review and release hardening remain active.

**Architecture:** Python modular monolith + hexagonal ports/adapters + durable event-driven orchestrator + SQLite operational SSOT.

```text
PySide6 desktop | CLI | optional future API
                    |
       Commands / Queries / Typed Event Gateway
                    |
 Batch Coordinator: admission, ownership, resources
                    |
 1–N JobWorkers (one owner per active Folder Run)
             /               \
   MP3 cover branch       MP4 karaoke branch
   copy -> APIC -> QC     lyrics/audio -> align -> approve -> ASS -> FFmpeg -> QC
             \               /
       Artifact publishing + report
                    |
 SQLite / SQLAlchemy + Alembic | filesystem assets + hashes
              Transactional Outbox
                    |
        UI snapshot + events bridge
```

## Layer rules
Domain models cannot import PySide6, FFmpeg, SQLAlchemy or cloud providers. The application layer owns commands/queries and orchestration. Infrastructure adapters implement explicit typed ports and are testable via fakes. UI never accesses the database directly. Each module has I/O/error contract, verification hook and version.

## Ownership
- Database: jobs, steps, attempts, revisions, approvals, outbox, checkpoints, artifact manifests.
- Filesystem: original media bytes immutable, staging/output bytes referenced by root-relative locators and hash.
- Git repository: source, schemas, tests, deployment and ADRs.
- PathManager: resolves development/frozen resources, portable data and external root rebinding.

## SQLite migration mandate
All persistent schema changes must be implemented as **Alembic revisions**, driven by SQLAlchemy 2.x models. No production use of `metadata.create_all()` as a migration mechanism. Pre-migration backup, revision compatibility checks, WAL/foreign-key integrity and migration failure recovery are mandatory. See [Database design](docs/03-DATABASE-SSOT-ALEMBIC.md).

## State, ownership and events
One folder is one Job; every execution is an immutable-history JobRun. At most one logical JobWorker owns an active run and serializes its state-changing messages. Retry creates a new run and restarts from intake; version 1 deliberately has no durable per-step resume. MP3/MP4 branch outcomes remain independent, with PARTIAL_SUCCESS possible. State update and outbox insertion occur in one transaction. Consumers deduplicate event IDs, use sequence/cursors and reconcile from SSOT after reconnect. Cross-filesystem/DB publication uses fenced verification and reconciliation rather than fake atomicity. See ADR-0003 and the end-to-end sequences.

## Runtime and deployment
Development: CPython **3.12.10 x64**. Windows 11 CPU-only 8 GB baseline, heavyweight subprocess isolation and conservative concurrency. `ApplicationOrchestrator` is the process-wide owner of admission, immutable progress snapshots, typed sequenced events, cancellation, worker lifecycle and CPU budget; each active worker owns one folder. FFmpeg emits machine-readable progress into the engine event stream. PySide6 is a presentation shell over commands and `OrchestratorView`; it owns no state classification or scheduling policy. Distribution uses a ZIP containing a PyInstaller onedir payload, PowerShell-backed `install.bat`, and `run.bat`. Arabic digits ASCII 0–9 are explicitly formatted in UI regardless of Windows locale.

## Detailed specifications
See [Docs Index](docs/README.md), [Pipeline](docs/02-PIPELINE-AND-STATE-MACHINE.md), [Module Contracts](docs/06-MODULE-CONTRACTS.md), [Error Handling](docs/04-ERROR-RECOVERY.md), [Test Plan](docs/07-TEST-STRATEGY.md).
