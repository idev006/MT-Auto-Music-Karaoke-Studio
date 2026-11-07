# Contracts and schema rules

Planned canonical types (each versioned):
- `BatchCommand`: list of validated directory roots + output root and config revision.
- `JobManifest`: job_id, source roots, asset IDs/roles/hashes, revisions, branch states.
- `StepResult`: step_id, state, retry classification, artifact IDs, error.
- `DomainEvent`: event_id, sequence, version, batch/job/step, utc timestamp, payload.
- `LyricsTimeline`: source lyrics revision, phrase occurrence ID, word/syllable timing and approval.
- `KaraokeDisplayObject`: visual properties independent from LyricsTimeline.
- `PresetDescriptor`: id/version/base preset/renderer features/property overrides.
- `ArtifactManifest`: relative output locator, hash, media info and gate evidence.
- `ErrorRecord`: code, severity, scope, retryable, correlation id, user action.

Rules:
1. Version schemas; validate boundary DTOs; preserve backward-compatible migrations.
2. Event delivery is at least once; sequence and event_id make consumers idempotent.
3. State mutation is command-driven; UI subscriptions consume events + SSOT snapshots.
4. Never store hard-coded program-root paths; root_id and relative locators resolve through PathManager.
5. Every module publishes inputs, outputs, error contract and test fixture.
6. Render-dependent visual properties must be validated against adapter feature declarations.
