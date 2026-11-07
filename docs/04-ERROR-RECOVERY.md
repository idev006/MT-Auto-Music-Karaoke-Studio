# Error taxonomy, recovery and fault isolation

## Error contract
All public failures return: code, category, message_for_user, technical_details (sanitized), severity, retryable, retry_after, scope (step/job/batch/application), affected_artifacts, correlation_id, suggested_action and timestamp. Never pass a raw traceback as the sole UI message.

## Taxonomy and default action
| Group | Examples | Default |
|---|---|---|
| E01 Input | no folder/MP3, ambiguous mapping | NEEDS_INPUT |
| E02 Asset | damaged MP3, invalid image, missing file | fail affected branch, preserve original |
| E03 Metadata | malformed ID3/APIC | safe copy rewrite or fail MP3 |
| E04 Lyrics | absent/mismatch/unclear repeated hook | NEEDS_REVIEW or NEEDS_INPUT |
| E05 Alignment | timeout, malformed model output, low confidence | bounded retry, fallback, review |
| E06 Rendering | FFmpeg nonzero, unsupported feature, corrupt output | diagnostics, no publish |
| E07 Resources | disk full, RAM threshold, process quota | stop scheduling, wait remediation |
| E08 Persistence | DB busy/constraint/migration mismatch | bounded retry or block startup |
| E09 Runtime | crash, power interruption, cancelled process | interrupt run, release ownership, start a new run on retry |
| E10 Integration | missed event, moved paths, Qt bridge reconnect | rebind and snapshot reconcile |

## Retry rules
Version 1 uses whole-run restart. A failed/cancelled/interrupted JobRun is terminal; Retry creates a new run, workspace, owner epoch and input/config snapshot and starts again at intake. A tool adapter may perform a small bounded retry inside the current operation only for an explicitly transient failure with no externally visible side effect. No infinite retries and no reopening terminal history.

## Crash consistency
- Step output uses isolated staging path with an attempt ID.
- Check file decode/hash and record verified artifact before final output publish.
- Publisher uses same-volume temporary file + atomic rename; after reboot scan for orphan .partial files and reconcile against artifact manifests.
- On app startup expire ownership leases and mark abandoned non-terminal runs `INTERRUPTED`; never infer success from staging. A new run is required to retry.
- If MP3 branch succeeds and MP4 is blocked, preserve and expose verified MP3 with PARTIAL_SUCCESS.

## Cancellation
Stop admitting new work -> commit `CANCEL_REQUESTED` with optimistic revision -> request worker graceful exit -> kill Windows subprocess tree if timeout -> quarantine staging or mark orphan safely -> commit `CANCELLED`. A delayed result from the old run/owner epoch is rejected. Never delete verified prior published artifacts without explicit command.

## Disk safety
Estimate free space before render and before DB migrations; reserve margin; monitor ongoing disk capacity. Disk-full is *not* solved by rapid repeated retry. User must choose another workspace or free space.

## Reporting
One job's error must not terminate remaining jobs. UI displays human action, error code, exact affected stage and retry option only if permitted; structured logs include correlation ID but avoid secrets and raw lyrics unless opted in.

## Fault injection acceptance set
FI-01 missing cover, FI-02 corrupt MP3, FI-03 ambiguous multiple MP3, FI-04 invalid lyrics, FI-05 alignment timeout, FI-06 AI invalid schema, FI-07 kill FFmpeg mid-render, FI-08 disk full, FI-09 SQLite busy, FI-10 crash after atomic rename before DB reconciliation, FI-11 duplicate/out-of-order event, FI-12 moved external source root, FI-13 cancel while rendering, FI-14 locale Thai numerals, FI-15 job isolation, FI-16 unsupported preset renderer feature.
Every test asserts no source changes, truthful state, no false published success and actionable diagnostics.
