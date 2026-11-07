# MT Auto Music & Karaoke Studio Product Delivery Plan

> **For agentic workers:** Implement one Kanban card at a time. Every card uses test-first development, passes its stated quality gate, updates requirement traceability, and ends in a reviewable commit before the next dependent card starts.

**Goal:** Deliver a headless, recoverable Windows engine that converts 1–N song folders into verified MP3-with-cover and MP4 Thai-karaoke outputs, followed by a thin PySide6 UI and portable onedir release.

**Architecture:** A modular monolith applies hexagonal boundaries around a durable application orchestrator. SQLite is the operational SSOT; filesystem artifacts remain immutable or staged until verified; UI and CLI communicate only through commands, queries and events. MP3 and MP4 branches execute independently and aggregate to truthful full or partial outcomes.

**Tech Stack:** CPython 3.12.10 x64, SQLAlchemy 2.x, Alembic, SQLite, pytest, Ruff, FFmpeg/FFprobe, Mutagen, Pillow, faster-whisper/CTranslate2, optional Demucs, ASS/libass, future PySide6 and PyInstaller onedir.

## Global Constraints

- Primary platform: Windows 11 x64, CPU-only capable, minimum target RAM 8 GB.
- Development runtime: CPython 3.12.10 x64; supported range remains `>=3.12,<3.13` until a compatibility decision changes it.
- Development FFmpeg root: `D:\libs\ffmpeg`; resolve it through configuration/PathManager, never domain constants or persisted installation paths.
- Never modify original MP3, images or lyrics; all production uses isolated staging.
- MP3 cover embedding must not re-encode audio and must verify audio-frame integrity.
- MP4 uses the operator-selected still image for the whole song and the original MP3 as authoritative audio input.
- Supplied lyrics remain canonical source text; presentation formatting and normalization never mutate the original revision.
- All program-generated displayed numerals use ASCII digits `0–9` regardless of Windows locale.
- All persistent schema changes use reviewed Alembic revisions; production must not use `metadata.create_all()` as migration logic.
- State update and durable outbox insertion share one database transaction.
- No quality gate, KPI or completion claim is valid without recorded execution evidence.

---

## 1. Documentation readiness decision

**Decision: READY WITH CONDITIONS for incremental development.** The repository has enough approved SSOT to continue Milestone 1 and deterministic media slices. It is not yet a complete production acceptance package.

Ready now:

- Product scope, inputs, outputs and non-goals are explicit.
- Architecture boundaries and headless-first rule are explicit.
- Pipeline DAG, states, error taxonomy and partial-success rule are documented.
- Initial operational data model and first Alembic revision exist and have local tests.
- Test categories, provisional KPIs, portable-path policy and requirement traceability exist.

Conditions to close during delivery:

- Freeze versioned Python DTO/JSON schemas as each boundary is implemented.
- Create legally usable media fixtures and a human-annotated Thai-song alignment benchmark.
- Record FFmpeg/font/model redistribution and licensing decisions before portable packaging.
- Measure faster-whisper model/VAD/vocal-separation choices instead of selecting them by assumption.
- Define preview/final-render parity evidence before the preset catalog expands beyond the first 8 presets.
- Verify GitHub Actions and clean-PC portability independently; local test results are not substitutes.

## 2. Agile operating model

Use continuous-flow Kanban with weekly replenishment and review rather than fixed feature sprints. A planning week may contain several small cards, but work is pulled only when capacity exists.

### Board columns and WIP limits

| Column | Meaning | WIP limit |
|---|---|---:|
| Backlog | Ordered but not yet acceptance-ready | unlimited |
| Ready | Meets Definition of Ready and can start immediately | 6 |
| In Development | Test and implementation actively changing | 2 |
| Review | Diff, architecture and security review | 2 |
| Verification | Automated/integration/manual evidence collection | 2 |
| Blocked | External decision, fixture or environment dependency | no limit; reviewed daily |
| Done | Definition of Done satisfied and committed | unlimited |

Expedite lane: maximum 1 card, reserved for data-loss, source-overwrite, migration corruption, security or release-blocking defects. Normal feature priority cannot use this lane.

### Definition of Ready

A card enters Ready only when it has:

- A linked requirement and owning phase.
- Explicit inputs, outputs and failure behavior.
- Named files/modules expected to change.
- Executable acceptance tests and required fixtures.
- Dependency and rollback notes.
- No unresolved architecture decision that would materially change implementation.

### Definition of Done

A card is Done only when:

- Its behavioral tests were written and observed failing before implementation where practical.
- Unit/contract/integration tests for the card pass.
- Ruff passes; type checking passes after the type-checking gate is introduced.
- Original-input immutability and relevant failure paths are tested.
- SSOT, traceability and migration/contracts are updated when affected.
- Evidence records the command, environment, pass/fail/skip totals and Git SHA.
- Diff is reviewed, contains no unrelated edits and has a meaningful commit.
- No status is called production-ready solely because tests in a narrower scope passed.

### Cadence

- Daily: inspect flow, unblock work, enforce WIP and record new risks.
- Weekly replenishment: select the next dependency-ready cards and clarify acceptance tests.
- Weekly product review: demonstrate headless behavior using real commands and artifacts, not mock UI screens.
- At phase gate: run the complete relevant regression suite, update KPI evidence and decide proceed/remediate.
- Retrospective after every phase: record defect escape, cycle time, blocked time and changes to working policy.

## 3. Delivery phases and gates

### Parallel and multi-worker execution model

The engine accepts and advances many folder jobs concurrently. Concurrency is controlled by resource class rather than one global worker count:

| Pool | Example steps | Initial 8 GB default | Execution mode |
|---|---|---:|---|
| I/O | discovery, hashing, copy, manifest, publish | 4 | bounded threads |
| Metadata | Pillow/Mutagen parsing and validation | 2 | bounded threads or processes |
| Audio light | FFprobe, audio preparation | 2 | subprocess slots |
| ASR heavy | faster-whisper, optional Demucs | 1 | isolated worker process |
| Render heavy | FFmpeg final render | 1 | isolated subprocess tree |
| Database writer | state/outbox/checkpoint commits | 1 coordinator | short transactions |

These are safe initial defaults, not fixed product limits. A resource profile may raise them after memory/CPU/disk benchmarks. Logical concurrency remains greater than one even when only one heavyweight step runs: while Job A renders, other jobs may scan, validate, prepare metadata or wait at review gates.

Scheduler rules:

- Persist every READY step before dispatch; workers never own authoritative state.
- Lease work atomically with `worker_id`, `attempt_id`, heartbeat and expiration.
- Use dependency-aware fair scheduling across jobs; one folder cannot monopolize all slots.
- Enforce per-resource semaphores plus global memory/disk-pressure backpressure.
- Use one staging directory per `job_id/step_id/attempt_id`; workers cannot share writable artifact paths.
- Workers return typed `StepResult`; only the coordinator commits state and outbox events.
- Treat execution as at-least-once; input fingerprints, artifact keys and unique constraints make results effectively idempotent.
- Cancellation targets one job/attempt and its Windows subprocess tree without stopping other jobs.
- A failed folder affects only its job/branch. Other eligible folders continue, and verified outputs remain available.
- On restart, expire stale leases, inspect staged artifacts and reschedule only incomplete or invalidated steps.

Required parallel acceptance scenarios:

- Process 1, 2, 5 and 10 folder jobs with deterministic fake workers and prove every job remains isolated.
- Run simultaneous I/O/metadata steps while a heavyweight slot is occupied.
- Prove ASR/render pool limits are never exceeded under load.
- Kill one worker and recover its expired lease without duplicating another job's artifact.
- Cancel one job while sibling jobs continue to completion.
- Inject SQLite busy, disk pressure and duplicate/out-of-order results without false success or deadlock.
- Measure peak RAM, CPU, disk throughput, queue wait and per-job completion time before increasing defaults.

### Phase 0 — Baseline and governance

**Outcome:** reproducible development baseline and truthful project status.

Current evidence: documentation scaffold, PathManager/numeral helpers and the initial persistence migration exist. Local baseline is 12 passing tests at commit `d388d187a39e588b7f69077dc3901d3805dfd463`; remote CI is unverified.

Exit gate:

- Clean editable installation succeeds on Python 3.12.10.
- Ruff and all foundation tests pass.
- GitHub Actions result is recorded.
- No local-only absolute path is committed as runtime truth.

### Phase 1 — Headless operational foundation

**Outcome:** create, persist, execute, interrupt and resume independent jobs without media production.

Ordered Kanban cards:

1. **M1-01 Typed states and legal transitions**
   - Create `src/mt_engine/domain/states.py` and `src/mt_engine/domain/transitions.py`.
   - Test `tests/domain/test_transitions.py` for every legal edge, illegal edge and terminal-attempt rule.
   - Accept when batch/job/step transition tables match `docs/02-PIPELINE-AND-STATE-MACHINE.md` exactly.

2. **M1-02 Transactional repositories and optimistic revision**
   - Create `src/mt_engine/adapters/persistence/repositories.py` and application-facing persistence protocols.
   - Test stale revision, duplicate `request_id`, rollback, event uniqueness and two-job isolation.
   - Accept when aggregate mutation and outbox event are committed or rolled back together.

3. **M1-03 Migration safety lifecycle**
   - Extend `src/mt_engine/adapters/persistence/migration.py` with SQLite backup API, disk preflight and restore-on-failure.
   - Test fresh upgrade, previous fixture preservation, unknown future revision and injected failure recovery.
   - Accept when worker startup is blocked until the schema is compatible and verified.

4. **M1-04 Typed error contract and retry policy**
   - Create `src/mt_engine/domain/errors.py` and `src/mt_engine/application/retry.py`.
   - Test E01–E10 serialization, severity/scope, retry eligibility, bounded attempts and backoff bounds.
   - Accept when no public failure relies on a raw traceback as its user message.

5. **M1-05 Durable orchestrator and leases**
   - Create focused modules under `src/mt_engine/application/workflow/` for definitions, scheduler, coordinator and recovery.
   - Test lease acquisition, heartbeat expiry, retry as a new attempt, cancellation, duplicate result, fair multi-job scheduling, resource-pool limits and restart reconciliation.
   - Accept when at-least-once execution produces idempotent effective state.

6. **M1-06 Multi-folder intake and immutable manifests**
   - Create `src/mt_engine/intake/` modules for selection normalization, scanning, classification and validation.
   - Test 1/N folders, nested duplicates, Thai paths, missing folders, multiple MP3s, ambiguous images and output-tree exclusion.
   - Accept when ambiguity becomes `NEEDS_INPUT`; the engine never silently selects a conflicting role.

7. **M1-07 Headless CLI**
   - Create `src/mt_engine/cli.py` and declare the project script entry point in `pyproject.toml`.
   - Provide commands for database status/upgrade, intake, batch status, start, cancel and resume.
   - Accept when a temporary workspace completes a fake-worker batch without importing PySide6.

Phase gate: orchestrator crash/retry/cancel/resume/duplicate-event/job-isolation tests all pass; 1/2/5/10-folder parallel scenarios respect configured pool limits; database migration and source immutability gates pass; CLI drives the workflow end to end with fake adapters.

### Phase 2 — MP3 artwork vertical slice

**Outcome:** verified `song_with_cover.mp3` without audio re-encoding.

Ordered cards:

1. **M2-01 Media tool and file-inspection ports** — resolve FFmpeg/FFprobe and capability versions; validate executable paths without shell strings.
2. **M2-02 MP3 and artwork preflight** — Mutagen/Pillow adapters validate audio, image format, dimensions and mapping.
3. **M2-03 Copy and APIC embedding** — write only to attempt staging; retain protected metadata under a versioned policy.
4. **M2-04 Audio-frame integrity QC** — compare extracted MP3 audio-frame content independently from changed ID3 bytes and read APIC back.
5. **M2-05 Safe publication** — collision policy, verified manifest, same-volume atomic rename and orphan reconciliation.

Tests live under `tests/media/mp3/` with legally generated MP3/image fixtures. Phase gate requires damaged-file, ID3-version, multiple-APIC, metadata-retention, disk failure and original-hash tests. MP3 branch must remain publishable when the MP4 branch is blocked.

### Phase 3 — Deterministic MP4 karaoke vertical slice

**Outcome:** verified MP4 from an approved timing fixture, without relying on automatic transcription.

Ordered cards:

1. **M3-01 FFmpeg capability adapter** — verify `ffmpeg`, `ffprobe`, libass, HarfBuzz/FreeType, H.264 and AAC support from configured/bundled tools.
2. **M3-02 Versioned timeline and minimal display schema** — keep approved text/timing separate from visual configuration.
3. **M3-03 ASS subtitle generator** — deterministic Thai-safe layout, outline and karaoke tags from the approved timeline.
4. **M3-04 Still-image video renderer** — argument-list subprocess invocation, bounded threads, cancellation and staging cleanup.
5. **M3-05 MP4 QC and publication** — decode, stream/profile, duration tolerance, sampled-frame image/subtitle evidence and manifest reconciliation.

Tests live under `tests/media/video/`; deterministic fixtures include Thai combining marks, long lines and Unicode paths. Phase gate produces a real H.264/AAC MP4 using the selected still image and records FFmpeg build and fixture hashes.

### Phase 4 — Thai lyrics intelligence and review

**Outcome:** proposed timings with measured confidence and a human-correctable path.

Ordered cards:

1. **M4-01 Lyrics ingestion/revisions** — TXT, DOCX and ID3 adapters; encoding diagnostics; immutable original text.
2. **M4-02 Audio preparation profiles** — FFmpeg normalization and optional Demucs adapter with cached, versioned outputs.
3. **M4-03 Faster-whisper adapter** — local model manager, CPU `int8`, segment/word timestamps, VAD configuration, provenance and cancellation.
4. **M4-04 Lyrics matching** — occurrence-aware matching for repeated hooks, omissions and recognition differences.
5. **M4-05 Alignment candidates** — confidence and evidence per phrase/token; no automatic approval below the measured threshold.
6. **M4-06 Review commands** — corrections create new timing revisions using optimistic concurrency.
7. **M4-07 Thai benchmark** — compare model size, original/vocal-separated audio and VAD profiles against human ground truth.

Benchmark evidence records phrase MAE, word P95, coverage, runtime and memory. Phase gate requires a declared dataset and measured values; provisional KPI targets may fail without being rewritten to claim success.

### Phase 5 — Recovery depth, karaoke object and presets

**Outcome:** resilient batch production and visually verified first preset tranche.

Ordered cards:

1. Dependency fingerprinting and selective step invalidation.
2. Bounded scheduling for 8 GB CPU-only systems.
3. Full 14-group/84-property versioned KaraokeDisplayObject schema.
4. Renderer capability validation and property inheritance.
5. First 8 presets, one per catalog group.
6. Fault-injection suite FI-01–FI-16.
7. Cache lifecycle, provenance and safe cleanup.
8. Expand presets to 24 and then 40 only after separate visual-QA gates.

Phase gate requires crash recovery, no duplicate published artifact, truthful partial success, safe-area evidence and preview/final reference-frame parity for the released preset tranche.

### Phase 6 — Thin PySide6 UI and Windows portable release

**Outcome:** relocatable onedir desktop application over the already verified engine.

Ordered cards:

1. Query/command/event facade and snapshot reconciliation.
2. Qt queued signal/slot bridge with event deduplication and throttled progress.
3. Folder mapping and batch monitor screens.
4. Job error/action screen and timing reviewer.
5. Preset preview and output history.
6. PyInstaller onedir resource manifest including migrations, FFmpeg, fonts, models/presets and notices.
7. Relocation, Unicode path, Thai locale, DPI and clean-PC test matrix.

Phase gate requires launch without installed Python, no media work on the UI thread, restart/reconnect consistency, ASCII-digit compliance, relocated application/data roots and documented license inventory.

## 4. Initial Kanban backlog

| Priority | Card | Depends on | Acceptance summary | Initial state |
|---:|---|---|---|---|
| 1 | M1-01 Typed states/transitions | persistence baseline | exhaustive legal/illegal transition tests | Ready |
| 2 | M1-02 Repositories/outbox | M1-01 | optimistic revision and atomic event tests | Backlog |
| 3 | M1-03 Migration safety | persistence baseline | backup, preservation and recovery tests | Ready |
| 4 | M1-04 Error/retry contracts | M1-01 | E01–E10 and bounded retry tests | Backlog |
| 5 | M1-05 Orchestrator/leases | M1-02, M1-04 | crash/retry/cancel/idempotency tests | Backlog |
| 6 | M1-06 Multi-folder intake | M1-02, M1-04 | 1–N/ambiguity/Unicode tests | Backlog |
| 7 | M1-07 CLI | M1-05, M1-06 | fake-worker headless integration | Backlog |
| 8 | M2-01 Media tool resolver | M1 gate | configured/bundled/PATH capability tests | Backlog |
| 9 | M2-02 MP3/image preflight | M2-01 | damaged/ambiguous asset tests | Backlog |
| 10 | M2-03 APIC embedding | M2-02 | metadata and staged-copy tests | Backlog |

Only M1-01 and M1-03 may enter In Development initially, respecting the WIP limit of 2. M1-02 is replenished after M1-01 review; M1-04 may proceed in parallel with M1-03 when capacity opens.

## 5. Metrics for process improvement

Track process metrics separately from product KPIs:

- Lead time: Ready to Done.
- Cycle time: In Development to Done.
- Blocked time and cause.
- Throughput: Done cards per week.
- Work-item age for every active card.
- Defect escape: defects found after the card's verification gate.
- Rework ratio: reopened cards / Done cards.

These metrics guide flow improvements; they are not product-quality evidence. Product KPIs continue to follow `KPI_FRAMEWORK.md` and require named datasets and measurement procedures.

## 6. Planning and commit policy

- Before each phase, create a detailed implementation plan in `docs/superpowers/plans/` for that subsystem with exact interfaces, tests and file changes.
- Prefer one reviewable behavior per commit; never combine schema, orchestrator and UI changes merely to reduce commit count.
- Use feature branches or pull requests for architecture-impacting slices when repository workflow supports them.
- At every phase gate update `docs/10-REQUIREMENT-TRACEABILITY.md`, this board and the evidence record.
- Push or release only after explicit repository publication authority and successful applicable gates.

## 7. Immediate execution sequence

1. Pull **M1-01 Typed states and legal transitions** into In Development.
2. Write its detailed test-first implementation plan with exact state enums and transition matrix from `docs/02-PIPELINE-AND-STATE-MACHINE.md`.
3. In parallel capacity, pull **M1-03 Migration safety lifecycle** only after defining a recoverable backup/restore acceptance fixture.
4. Review each diff independently; do not begin M1-05 until repository and error contracts are stable.
5. Demonstrate the Phase 1 gate through the headless CLI before any PySide6 production screen begins.
