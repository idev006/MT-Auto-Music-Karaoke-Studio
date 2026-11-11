# Development handoff — 2026-11-11

This is the primary entry point for the next developer or AI agent. Read it before changing code.
It records observed repository state, verified behavior, known limitations and the next tranche.
Do not infer release readiness from the existence of an MP4.

## Repository state

- Repository: `https://github.com/idev006/MT-Auto-Music-Karaoke-Studio.git`
- Local branch at handoff: `main`
- Base commit before the current working tranche: `c916097`
- Primary runtime: Windows 11 x64, CPython 3.12, CPU-only
- Local FFmpeg used for verification: `D:\libs\ffmpeg`
- Development model cache: `models\faster-whisper`
- Default Thai font: `assets\Fonts\THSarabun Bold.ttf`
- The working tranche contains engine, UI, tests, deployment scripts and documentation changes.
  Inspect `git status` before editing and never discard uncommitted user work.

Secrets are not repository assets. `config/openrouter.env` is ignored and must never be printed,
committed or copied into examples. Model caches, media outputs and release ZIPs are also ignored.

## What is implemented

### Engine and media

- Strict one-song-folder intake with one MP3 and one or two mapped images.
- Canonical lyrics from primary-MP3 USLT, with deterministic fallback to one `*.mp3--` USLT
  sidecar. Conflicting or ambiguous lyric sources fail closed.
- Faster Whisper CPU transcription with a process-wide lock protecting shared downloads and RAM.
- Optional OpenRouter modes `off`, `auto`, and `always`, sharing a USD 0.20 per-song ceiling.
- Monotonic canonical-line timing proposal, structural validation and human timing-lock path.
  Unreviewed timing renders line cues only; progressive highlighting requires locked spans.
- Portrait images produce 1080x1920; landscape and square images produce 1920x1080.
- ASS generation with canvas-aware virtual blocks, dynamic Thai font fitting and presets.
- FFmpeg H.264/AAC rendering with machine-readable progress and defensive progress parsing.
- APIC cover embedding into a copied MP3 with audio-payload hash verification.

### Runtime reliability

- `ApplicationOrchestrator` owns a bounded worker pool; one worker owns one source folder.
- UI receives immutable snapshots and typed sequenced events; it has no media business logic.
- `workers * CPU threads per worker` cannot exceed logical CPU count.
- One atomic `production_data/run_state.json` records
  `INTAKE -> LYRICS -> TRANSCRIBE -> TIMING -> RENDER -> QC -> COMPLETE`.
- Failure retains the last stage and writes `production_data/failure.log` with a traceback.
- Diagnostic render reuse requires matching source-audio, background, ASS and MP4 hashes, followed
  by another decode/probe. A mismatch safely renders again.
- Retry may replace managed non-release candidates; released or unmanaged output is protected.
- QC removes only engine-owned `sample_*.png` before creating a fresh 12-frame evidence set.

### Desktop shell

- PySide6 UI follows the OS theme and formats program-created numbers as ASCII digits 0–9.
- Multiple folders, configurable workers, CPU threads, model, preset and OpenRouter mode.
- Per-job progress, FFmpeg metrics, cancellation, full error details and output-folder opening.
- `run.bat` launches the installed executable when present, otherwise the `.venv` development
  executable. Source-mode smoke test has passed.

## Verified commands and results

```bat
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m pytest -q
cmd.exe /c call run.bat --smoke-test
```

Last observed on 2026-11-11: Ruff PASS, pytest `150 passed`, and run-batch smoke exit code `0`.
These results become stale after any code change and must be rerun.

## Latest real-media E2E evidence

Fixture: `src_for_test\อยู่เป็นเพื่อนกันนาน ๆ นะ v9`

Target: `dest_for_test\อยู่เป็นเพื่อนกันนาน ๆ นะ v9`

| Evidence | Observed value |
|---|---|
| Run ID | `15aa43ea247048c2ba543c5dd879981c` |
| Product state | `DIAGNOSTIC_VIDEO_READY_TIMING_BLOCKED` |
| Video | `karaoke_diagnostic.mp4` |
| Video SHA-256 | `7293c08fd4a6697612c20300b65cf9995bd7d76609014e7086038a410147f2c3` |
| Media | H.264 + AAC, 1080x1920, complete decode PASS |
| QC samples | 12 report samples and 12 managed PNG files |
| Subtitle-region pixels | present in all sampled frames |
| OpenRouter spend | USD 0.00356855 |
| Timeline status | `BLOCKED` with 6 findings |
| Lines requiring alignment review | 8 |

The diagnostic MP4 is useful for engineering review, but it is not released karaoke. Manifest
output `mp4` remains null. Only a hash-bound human timing lock, complete listening QC and sign-off
may publish `karaoke.mp4`.

## Current root cause

The remaining product blocker is lyric-to-singing alignment, not UI or FFmpeg.

- The fixture has 44 canonical lines.
- A suspect local-ASR segment spans approximately 0–29.98 seconds and can distort allocation of the
  first two lines.
- Canonical lines 40–43 have insufficient lexical evidence near the tail. Proportional interpolation
  compresses final lines and triggers short-phrase/implausible-rate blocks.
- Current OpenRouter comparison selects either the entire local transcript or entire cloud
  transcript by aggregate score. It cannot retain good local anchors while using one better cloud
  anchor for an unresolved region.
- Vision can inspect rendered text but cannot prove synchronization with singing.

## Approved next architecture

1. Retain local and cloud transcripts as separate immutable evidence sets.
2. Add deterministic per-line/region fusion using monotonic dynamic programming. Every placed line
   cites provider segment IDs/timestamps; AI cannot invent timestamps.
3. Detect suspect initial hallucinations, repeated-line ambiguity and impossible residual windows.
   Mark unresolved lines `UNPLACED` instead of squeezing them into remaining time.
4. In `auto`, escalate only unresolved/conflicting windows with padding and cache by audio-window,
   lyrics and model hashes. Provider failure retains local diagnostic evidence.
5. A constrained mapper may return only `{line_index, segment_ids}`. The engine derives times from
   cited acoustic segments and rejects unknown IDs, overlap, non-monotonic order, weak similarity
   and implausible rate.
6. AI output remains `REVIEW_REQUIRED`; it cannot create a timing lock or authorize release.
7. Add a timing reviewer that shifts/splits/accepts lines and exports the existing hash-bound lock.

Suggested sub-budgets within the existing USD 0.20 ceiling are transcription USD 0.06, mapping
USD 0.04, Vision USD 0.08 and reserve USD 0.02. Reservation/commit and unknown-cost fail-closed
behavior are proposed, not yet implemented.

## Gate corrections still required

- Separate operational stage from product/review state in every projection.
- G1 must represent verified canonical-source/hash identity, not merely a human lock.
- G4 acoustic alignment must participate in release; Vision cannot override it.
- Release must explicitly require decode/probe/hash, rendered-text review and listening sign-off.
- Calibrate alignment thresholds using annotated Thai-song evidence; current thresholds are
  diagnostic and not quality claims.

## Prioritized backlog

### P0 — next implementation tranche

- Add evidence-source IDs and `UNPLACED` line state.
- Implement local/cloud per-line monotonic fusion and provider privacy fields.
- Add budget reservation and unknown-cost handling.
- Correct G1/G4/release assertions.
- Test complementary local/cloud anchors, repeated chorus identity, hallucinated intro, impossible
  tail, provider outage and total cost <= USD 0.20.

### P1

- Timing-review UI and timing-lock export/import.
- Conflict-window cloud requests with absolute offsets and request cache.
- Full listening/sign-off workflow in the desktop shell.

### P2

- Thai singing benchmark with human annotations and measured onset/offset metrics.
- Multi-worker benchmarks on the 8 GB Windows profile.
- Retention policy for old `.work` runs after recovery evidence is no longer needed.

### Release work — only after explicit approval

- Do not rebuild the installer during normal engine/UI development.
- Package only after engine, UI, real-media E2E and release gates are approved.
- Clean-PC acceptance without Python remains unverified.
- Font files are required by current presets, but redistribution/license evidence must be audited
  before a public binary release.

## Rules for the next AI

1. Read this document, `ARCHITECTURE.md`, `13-SINGING-AWARE-ALIGNMENT.md` and ADR-0003.
2. Run `git status`; preserve the working tree and user media.
3. Never modify source MP3 files or expose the OpenRouter key.
4. Never claim perfect synchronization from ASR, Vision, pixels or successful rendering.
5. Keep UI as a shell over engine commands/events.
6. Add tests before changing provider selection or release gates.
7. Run real-media E2E only after unit/integration tests; report diagnostic and release states apart.
8. Do not build an installer unless the user explicitly requests release packaging.
