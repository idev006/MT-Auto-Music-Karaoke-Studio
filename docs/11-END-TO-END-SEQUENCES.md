# End-to-end execution sequences

Status: approved architecture contract. These sequences implement ADR-0003 and are acceptance-test sources.

## Participants and ownership

- UI/CLI sends commands and reads snapshots/events; it never calls media tools or SQLite directly.
- Engine Facade validates commands and optimistic revisions.
- Batch Coordinator admits jobs under configured worker/resource limits.
- One JobWorker owns one active JobRun and serializes its state changes.
- Tool adapters return typed results and never mutate operational state.
- SQLite is operational truth; the Job workspace contains manifest, staging, evidence and diagnostic logs.
- Publisher accepts only artifacts from the active fenced run after QC.

## Happy path: one song end to end

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as CLI / PySide6
    participant E as Engine Facade
    participant B as Batch Coordinator
    participant DB as SQLite SSOT
    participant J as JobWorker
    participant W as Run Workspace
    participant M as MP3 Adapter
    participant ASR as faster-whisper Adapter
    participant A as Alignment Engine
    participant S as ASS Generator
    participant F as FFmpeg Adapter
    participant Q as QA Engine
    participant P as Publisher

    User->>UI: Select 1-N folders, output root and config
    UI->>E: CreateBatch(request_id, folders, config)
    E->>DB: Create Batch and Jobs atomically
    DB-->>E: Batch snapshot
    E-->>UI: Accepted snapshot

    B->>DB: Claim next Job and create JobRun
    DB-->>B: run_id, owner_epoch, revision
    B->>J: Start fenced JobRun
    J->>W: Create stable run workspace
    J->>J: Discover, classify and validate assets

    alt Mapping is ambiguous or required asset missing
        J->>DB: Commit NEEDS_INPUT and diagnostic event
        DB-->>UI: Snapshot/event
    else Assets valid
        J->>W: Write immutable manifest and input fingerprints

        rect rgb(235,245,255)
            Note over J,Q: MP3 branch
            J->>M: Copy source and embed cover in staging
            M-->>J: Staged MP3 result
            J->>Q: Verify APIC, metadata policy and audio frames
            Q-->>J: Verified MP3 evidence
            J->>DB: Commit MP3 branch SUCCEEDED
        end

        rect rgb(245,235,255)
            Note over J,Q: MP4 branch
            J->>F: Prepare deterministic working audio
            F-->>J: Audio evidence
            J->>ASR: Transcribe with model/config provenance
            ASR-->>J: TranscriptCandidate
            J->>A: Match supplied lyrics and propose timing
            A-->>J: TimelineCandidate and confidence

            alt Review required
                J->>DB: Commit NEEDS_REVIEW
                DB-->>UI: Review request and snapshot
                User->>UI: Correct or approve timing
                UI->>E: ApproveTiming(expected_revision)
                E->>DB: Store immutable approval revision
                DB-->>J: Approved timing available
            end

            J->>S: Generate escaped, Thai-safe ASS
            S-->>J: Subtitle artifact and evidence
            J->>F: Render selected still image, audio and ASS
            F-->>J: Staged MP4 result
            J->>Q: Decode, duration, stream and visual QC
            Q-->>J: Verified MP4 evidence
            J->>DB: Commit MP4 branch SUCCEEDED
        end

        J->>P: Publish fenced verified artifacts
        P->>DB: Recheck active run, epoch, revision and cancellation
        P->>W: Same-volume atomic publication
        P-->>J: Published manifests
        J->>DB: Commit Run SUCCEEDED and Job COMPLETED
        DB-->>UI: Completed snapshot/event
        UI-->>User: Show MP3, MP4 and QC report
    end
```

## Failure isolation across songs

```mermaid
sequenceDiagram
    autonumber
    participant B as Batch Coordinator
    participant DB as SQLite
    participant JA as JobWorker A
    participant JB as JobWorker B
    participant T as Tool Adapter

    B->>JA: Start Song A / Run A-001
    B->>JB: Start Song B / Run B-001
    par Song A fails
        JA->>T: Execute operation
        T-->>JA: Classified failure
        JA->>DB: Run A-001 FAILED, preserve diagnostics
    and Song B succeeds
        JB->>T: Execute operation
        T-->>JB: Verified result
        JB->>DB: Run B-001 SUCCEEDED
    end
    B->>DB: Aggregate Batch
    DB-->>B: COMPLETED_WITH_ISSUES
```

## Whole-run retry

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI
    participant E as Engine Facade
    participant DB as SQLite
    participant B as Batch Coordinator
    participant J as New JobWorker
    participant W as Workspace

    User->>UI: Retry failed song
    UI->>E: RetryJob(job_id, expected_revision)
    E->>DB: Verify no active run and prior run is terminal
    DB-->>E: Run A-001 FAILED
    E->>DB: Create Run A-002 with new owner epoch and snapshots
    E->>W: Create new RUN-A-002 workspace
    E-->>B: Queue Run A-002
    B->>J: Start Run A-002
    J->>J: Restart from intake; do not reuse prior staging
```

## Cancellation and stale-result rejection

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI
    participant E as Engine Facade
    participant DB as SQLite
    participant J as JobWorker
    participant T as Tool Process
    participant P as Publisher

    J->>T: Start operation(run_id, owner_epoch, operation_id)
    User->>UI: Cancel song
    UI->>E: CancelJob(expected_revision)
    E->>DB: Commit CANCEL_REQUESTED if revision matches
    DB-->>J: Cancellation message
    J->>T: Graceful stop, then kill process tree on timeout
    J->>DB: Commit Run CANCELLED
    T-->>J: Delayed success from old operation
    J->>DB: Validate run, epoch and operation
    DB-->>J: Reject stale result
    J-xP: Publication forbidden
```

## Restart after application crash

On startup, the coordinator marks an interrupted non-terminal run as `INTERRUPTED`; it does not infer success from staging files and does not resume midway. Diagnostics and staged files are retained or quarantined according to retention policy. The operator or configured policy creates a new run from intake. Verified artifacts are never deleted implicitly.

## Required sequence tests

- Happy path with supplied approved timing.
- `NEEDS_INPUT` asset mapping and `NEEDS_REVIEW` timing approval.
- MP3 success plus MP4 failure yields `PARTIAL_SUCCESS`.
- One song fails while sibling jobs continue.
- Retry creates new IDs, workspace and fingerprints.
- Cancel competes with tool completion; only one valid revision wins.
- Delayed old-run result cannot mutate state or publish.
- Crash/restart never reports staging as published success.
