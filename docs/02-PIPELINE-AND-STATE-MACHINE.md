# Production pipeline and state-machine contract

Status: approved architecture SSOT. ADR-0003 governs worker ownership and whole-run restart.

## Unit of work

- One selected song folder is one `Job`.
- One execution is one `JobRun`.
- A Job has at most one active JobRun.
- An active JobRun has at most one logical JobWorker owner.
- Retry never reopens a terminal run; it creates a new run and restarts from intake.
- Version 1 has no durable per-step resume. Step-level progress is diagnostic, not operational truth.

## End-to-end pipeline

```text
Batch Intake -> Job Creation -> Run Admission -> Discover -> Validate -> Manifest
                                                        +-> MP3 copy/APIC/QC
                                                        +-> audio/lyrics/ASR/alignment/review
                                                            -> ASS/render/MP4 QC
                                                        -> branch aggregation
                                                        -> fenced publication
                                                        -> Run/Job/Batch result
```

MP3 and MP4 branches are logically independent. MP3 success remains usable when MP4 fails or waits for input/review. See `11-END-TO-END-SEQUENCES.md` for normative interaction order.

## State machines

### Batch

`NEW, READY, RUNNING, PAUSING, PAUSED, COMPLETED, COMPLETED_WITH_ISSUES, FAILED, CANCELLING, CANCELLED`

### Job

`DISCOVERED, READY, QUEUED, RUNNING, NEEDS_INPUT, NEEDS_REVIEW, PARTIAL_SUCCESS, COMPLETED, FAILED, CANCELLING, CANCELLED`

### JobRun

`CREATED, QUEUED, RUNNING, NEEDS_INPUT, NEEDS_REVIEW, CANCEL_REQUESTED, SUCCEEDED, PARTIAL_SUCCESS, FAILED, INTERRUPTED, CANCELLED`

Terminal run states: `SUCCEEDED, PARTIAL_SUCCESS, FAILED, INTERRUPTED, CANCELLED`. A terminal run is immutable except for retention/audit metadata.

### Branch outcome

`NOT_STARTED, RUNNING, NEEDS_INPUT, NEEDS_REVIEW, SUCCEEDED, FAILED, CANCELLED, SKIPPED`

### Artifact

`PLANNED, STAGING, GENERATED, VERIFYING, VERIFIED, PUBLISHING, PUBLISHED, REJECTED, ORPHANED, SUPERSEDED`

### Review

`DRAFT, REVIEW_REQUIRED, IN_REVIEW, APPROVED, REJECTED, SUPERSEDED`

## Aggregation truth

| MP3 | MP4 | Run/Job result |
|---|---|---|
| SUCCEEDED | SUCCEEDED | SUCCEEDED / COMPLETED |
| SUCCEEDED | FAILED | PARTIAL_SUCCESS |
| SUCCEEDED | NEEDS_INPUT or NEEDS_REVIEW | PARTIAL_SUCCESS while action remains visible |
| FAILED | any non-success | FAILED |
| CANCELLED | CANCELLED or NOT_STARTED | CANCELLED |

Batch is `COMPLETED` only when all required Jobs complete. Mixed completed/partial/failed/cancelled results produce `COMPLETED_WITH_ISSUES`. `FAILED` is reserved for a batch that cannot produce any usable job result or suffers an application-level failure.

## Job ownership and resource protocol

The Batch Coordinator atomically claims a queued run and assigns `owner_id`, monotonically increasing `owner_epoch`, lease expiration and heartbeat. A JobWorker processes state-changing messages serially. All tool requests/results carry `job_id`, `run_id`, `owner_epoch` and `operation_id`.

Media/AI adapters do not write SQLite. They write only to the run-specific staging location and return typed results. The JobWorker validates results, then the command coordinator commits state and outbox events transactionally.

Initial resource profile for Windows 11 CPU-only / 8 GB:

- Multiple active JobWorkers are allowed subject to measured admission limits.
- I/O and metadata operations use bounded lightweight capacity.
- faster-whisper, Demucs and final FFmpeg render all acquire one shared global `HEAVY` token.
- Database mutation is serialized through one application command coordinator with short transactions.
- A second engine coordinator for the same data root is prohibited by an application-instance lock; database CAS remains the correctness boundary.

## Transition and race rules

Every durable transition includes expected revision, actor, reason, UTC timestamp and correlation ID.

- Job ownership acquisition/renewal uses compare-and-swap and coordinator/database time.
- Results with stale `run_id`, `owner_epoch`, operation ID or input/config fingerprint are rejected.
- Cancel and completion compete at the same optimistic revision. The first valid commit wins; the loser reloads state.
- Publisher rechecks active run, owner epoch, cancellation state, fingerprints and verified artifact status immediately before finalization.
- State update and outbox insert occur in one database transaction.
- UI and workers cannot assign state fields directly; they submit commands.

## Retry, crash and pause

- Transient tool failures may receive a small bounded retry inside the same operation only when the adapter can prove no externally visible side effect. This is not durable step resume.
- Any terminal run failure or application restart creates no automatic mid-run continuation.
- Startup marks abandoned non-terminal runs `INTERRUPTED`, releases ownership and reconciles/quarantines staging.
- Retry creates a new JobRun and workspace and revalidates all inputs from the beginning.
- Pause means stop admitting new JobRuns and allow currently running operations to reach a safe terminal or cancellation boundary. Version 1 does not freeze an FFmpeg/ASR process for later continuation.

## Workspace and publication

```text
{work_root}/jobs/{job_id}/
  manifest.json
  runs/{run_id}/
    events.jsonl
    staging/
    evidence/
    logs/
```

The workspace path never represents workflow state. Source folders remain read-only. Per-run `events.jsonl` is diagnostic/audit output, not the concurrency SSOT.

Database and filesystem are not one atomic transaction. Publisher uses same-volume temporary publication and reconciliation. An artifact is publishable only when bound to the active run/owner/operation and marked `VERIFIED`.

## Observability

Durable events include event ID, schema version, sequence, UTC time, batch/job/run IDs, owner epoch, correlation ID and payload. Progress events are advisory and may be memory/log only. Snapshot queries are authoritative. Logs must be structured, redact secrets/raw lyrics by default and include tool versions and operation IDs.

## Acceptance scenarios

- 1, 2, 5 and 10-folder isolation and bounded concurrency.
- At most one active run and owner per Job.
- One job failure/cancel does not stop siblings.
- Whole-run retry creates distinct IDs and workspace.
- Cancel versus success and delayed stale-result rejection.
- Crash/restart produces `INTERRUPTED`, never false success.
- MP3 verified plus MP4 failure remains truthful `PARTIAL_SUCCESS`.
- Heavy token is never exceeded under load.
