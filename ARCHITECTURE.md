# Architecture baseline — MT Auto Music & Karaoke Studio

Status: design baseline. Core implementations are pending.

**Architecture:** Python modular monolith + hexagonal ports/adapters + durable event-driven orchestrator + SQLite operational SSOT.

```text
PySide6 desktop (future) | CLI (future) | optional API
                    |
       Commands / Queries / Event Gateway
                    |
   Orchestrator: DAG, Job Queue, Scheduler, Recovery
                    |
          1–N independent Song Jobs
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

## State and events
Step state machine is explicit, job branches tracked independently, with PARTIAL_SUCCESS possible. State update and outbox event insert occur in one transaction. Consumers deduplicate event_id, use sequence, and reconcile from SSOT after reconnect. Cross-filesystem/DB publish consistency requires reconciliation rather than fake atomicity.

## Runtime and deployment
Development: CPython **3.12.10 x64**. Windows 11 CPU-only 8 GB baseline, heavyweight subprocess isolation, conservative concurrency. Future PySide6 desktop; PyInstaller onedir packaging, no installer. Arabic digits ASCII 0–9 explicitly formatted in UI regardless of Windows locale.

## Detailed specifications
See [Docs Index](docs/README.md), [Pipeline](docs/02-PIPELINE-AND-STATE-MACHINE.md), [Module Contracts](docs/06-MODULE-CONTRACTS.md), [Error Handling](docs/04-ERROR-RECOVERY.md), [Test Plan](docs/07-TEST-STRATEGY.md).
