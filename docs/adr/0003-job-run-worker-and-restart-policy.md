# ADR-0003: One Job Worker per Folder Run and Whole-Run Restart

- **Status:** Accepted
- **Date:** 2026-11-07
- **Supersedes:** step-worker ownership and fine-grained resume assumptions in earlier design prose

## Context

The product processes 1–N independent song folders. Earlier documents described durable step leases and selective step resume. The approved product direction now favors a simpler first production engine: one logical worker owns one folder execution, failures remain isolated to that song, and retry starts a new run from the beginning.

## Decision

1. One input song folder is one `Job`.
2. Each execution of a Job is an immutable-history `JobRun`.
3. A Job has at most one active JobRun, and an active JobRun has at most one logical `JobWorker` owner.
4. A JobWorker owns orchestration and serializes state-changing messages for its JobRun.
5. Media tools and AI adapters may use subprocesses or bounded shared resource slots, but they never own Job state and never write the operational database directly.
6. A failed or cancelled run is terminal. Retry creates a new `run_id`, workspace, ownership epoch and configuration/input snapshot, then starts at intake.
7. Version 1 does not resume from durable per-step checkpoints. Progress details may live in memory and an append-only per-run diagnostic log because they are reconstructible.
8. SQLite remains the operational SSOT for Batch, Job, JobRun, branch outcomes, ownership, review decisions and published artifacts.
9. Filesystem structure does not encode workflow state. Each run has a stable workspace; state changes never move the job between `pending/running/failed` directories.
10. Source folders are read-only. Logs, manifests, staging and evidence live under the managed work root, never beside source media.

## Runtime model

```text
Batch Coordinator
  +-- JobWorker A -> Job A / Run A-001
  +-- JobWorker B -> Job B / Run B-001
  +-- JobWorker C -> Job C / Run C-001

Each JobWorker requests bounded tool capacity:
  +-- I/O / metadata capacity
  +-- one shared HEAVY token for faster-whisper, Demucs or final FFmpeg render
  +-- one database command coordinator
```

The initial 8 GB profile permits multiple active JobWorkers but only one heavyweight operation across all jobs. Limits may change only after measured resource benchmarks.

## State and fencing

- Job ownership acquisition increments a monotonically increasing `owner_epoch`.
- Every tool request/result includes `job_id`, `run_id`, `owner_epoch` and operation ID.
- State mutation uses optimistic revision checks.
- Late results from a prior run, owner epoch or operation are rejected and cannot publish artifacts.
- Cancellation and completion race through the same revision boundary; the first valid commit wins and the loser reloads state.
- Publication rechecks active run, ownership epoch, cancellation status, input/config fingerprints and QC status immediately before finalization.

## Branch outcome policy

MP3 and MP4 work remain logically independent inside a run. Their outcomes are persisted so a verified MP3 may be published when MP4 fails or waits for review. The Job result is derived by a versioned aggregation table:

| MP3 branch | MP4 branch | Job result |
|---|---|---|
| SUCCEEDED | SUCCEEDED | COMPLETED |
| SUCCEEDED | FAILED | PARTIAL_SUCCESS |
| SUCCEEDED | NEEDS_INPUT | NEEDS_INPUT; verified MP3 remains visible |
| SUCCEEDED | NEEDS_REVIEW | NEEDS_REVIEW; verified MP3 remains visible |
| FAILED | any non-success | FAILED |
| CANCELLED | CANCELLED or not started | CANCELLED |

Retry still starts a complete new run. Version 1 may repeat previously successful lightweight work rather than introduce cache/resume complexity.

## Consequences

Positive:

- Clear folder ownership and simpler race reasoning.
- Failure isolation and batch continuation are straightforward.
- No complex checkpoint invalidation or partial step recovery in the first release.
- Run history remains auditable without rewriting failed attempts.

Costs:

- A run that fails near completion repeats work from the beginning.
- Transcription and render time may be repeated.
- Fine-grained resume, if later justified by evidence, requires a new ADR and migration.

## Rejected alternatives

- Folder location as workflow state: unsafe, cannot represent branch/review states and creates Windows file-move races.
- Memory plus log file as the only SSOT: loses authoritative coordination on crash and recreates database concurrency/indexing behavior poorly.
- Independent durable worker ownership per step: more flexible but unnecessarily complex for the first release and conflicts with one-folder ownership.

## Acceptance criteria

- 1, 2, 5 and 10-folder tests prove at most one owner per active run.
- Failure/cancel of one song does not stop sibling jobs.
- Retry creates a distinct run and workspace.
- Late results from an old run/epoch are rejected.
- Resource limits are never exceeded.
- Restart marks interrupted runs truthfully and permits a new whole-run retry.
- No source folder gains logs, staging or generated artifacts.
