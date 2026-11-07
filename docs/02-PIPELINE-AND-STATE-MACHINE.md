# Production pipeline and state-machine contract

## DAG
```text
Batch Intake -> Discover -> Validate -> Manifest
                                  +-> Cover Prepare -> MP3 Stage -> APIC Embed -> MP3 QC -> MP3 Publish
                                  +-> Audio Prep -----+
                                  +-> Lyrics Parse ---+-> Alignment -> Review Gate -> Subtitle -> Composite -> MP4 Render -> MP4 QC -> MP4 Publish
                                                                                                         
                    Branch results -> Job Aggregation -> Batch Summary
```

## Deterministic dependencies
- Asset discovery depends on selected folder roots and scanner version.
- Cover embedding depends on audio content hash + artwork content hash + metadata policy version.
- Lyrics normalization depends on lyrics revision and parser version.
- Alignment depends on audio hash, lyrics revision, algorithm/model version and alignment config.
- Subtitle depends on approved timeline revision + karaoke object/preset revision.
- Render depends on source audio, background image hash, subtitle artifact hash, output profile, fonts and FFmpeg build.
- MP3 cover branch **must not** depend on lyrics alignment/render branch.

## States
Step: PENDING, READY, RUNNING, BLOCKED, RETRY_WAIT, SUCCEEDED, FAILED, CANCELLED, SKIPPED.
Job: DISCOVERED, VALIDATING, READY, RUNNING, NEEDS_INPUT, NEEDS_REVIEW, PARTIAL_SUCCESS, COMPLETED, FAILED, CANCELLED.
Batch: NEW, RUNNING, PAUSED, COMPLETED, COMPLETED_WITH_ISSUES, FAILED, CANCELLED.
Every state transition validates legal source/target, timestamps, actor, reason and monotonic revision. FAILED and CANCELLED are terminal for a given attempt; Retry creates a new attempt, not a silent modification of history.

## Command contracts
`CreateBatch(folders, output_root, config_version, request_id)`
`ConfirmAssetMapping(job_id, mapping, expected_revision)`
`StartBatch(batch_id)` / `PauseBatch` / `ResumeBatch` / `CancelJob`
`ApproveLyrics(job_id, lyrics_revision)`
`ApproveTiming(job_id, timeline_revision, reviewer)`
`ApplyPreset(job_id, preset_id, preset_version, overrides)`
`RetryStep(job_id, step_id, expected_revision)`

## Worker protocol
Orchestrator leases a READY step to a Worker with attempt ID/lease expiry; Worker writes outputs to step-specific staging and returns typed StepResult, not DB writes. Coordinator validates outputs and transactionally commits state/outbox event. Heartbeat/timeout recovers orphan leases. Subprocess tree cleanup required on Windows. Never run CPU-heavy media tasks in Qt UI thread.

## Persistence / exactly-once misconception
Step execution is *at least once* under crash/retry. Ensure **idempotent effective results** via artifact keys, input+config hashes, staging isolation and atomic publish. Same-filesystem rename is atomic for a file, but SQLite and filesystem are not one atomic transaction; recovery reconciles final paths and DB artifact manifest.

## Failure policy
Permanent missing or ambiguous assets -> NEEDS_INPUT. Low-confidence/inconsistent timing -> NEEDS_REVIEW. Transient busy DB/temporary locks -> bounded retry with backoff. Resource exhaustion -> suspend scheduling until corrected. Invalid MP4 -> retain diagnostics, never publish, retry only when causes are addressed. MP3 complete + MP4 blocked => PARTIAL_SUCCESS.

## Observability
Events `batch.created`, `job.validated`, `step.started`, `step.progress`, `step.failed`, `timing.review_required`, `artifact.verified`, `artifact.published`. Payload includes event ID, schema version, monotonic sequence, timestamp UTC, batch/job/step IDs, attempt ID, correlation ID. Progress is advisory; SSOT query is authoritative.

## Resource scheduling
Baseline Windows 8 GB CPU-only: one heavyweight worker at a time (align or render), bounded FFmpeg threads, disk preflight, cancellation signal then forced subtree termination after timeout. Benchmark before raising concurrency.
