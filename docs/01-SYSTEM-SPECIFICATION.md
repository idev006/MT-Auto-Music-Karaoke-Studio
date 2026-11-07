# System specification — MT Auto Music & Karaoke Studio

Status: Approved requirements baseline, implementation pending. Revision: 2026-11-07.

## Goal / actors
User provides **1–N directories**, each representing one song job. Existing MP3 is authoritative audio. System embeds selected cover into an MP3 copy, and produces a still-image MP4 with Thai karaoke text at the bottom synchronized with the song. Deliver usable, reviewed results with audit trail. Actors: desktop operator, reviewer (may be the same person), engine operator/developer.

## Scope boundaries
- No song creation, vocals synthesis, remastering, source audio modification or MP3 audio re-encoding.
- Prefer supplied lyrics as canonical words; missing lyrics may use optional transcription adapter, always with review where uncertain.
- Original input files are never overwritten. MP3 copy may have ID3/APIC metadata changes only.
- One folder = one job. Multi-MP3 or ambiguous images do not silently choose an asset.
- MP4 uses user-selected picture for entire video, does not use cover instead unless explicitly mapped.
- Supports Thai words including repeated choruses and instrumental passages, with approved timing.
- Full HD H.264/AAC default; configurable export profiles must declare validation constraints.

## Primary deliverables
1. `song_with_cover.mp3`: embedded cover readback verified, audio frame stream unchanged.
2. `karaoke.mp4`: continuous image, original-song audio content encoded to AAC for MP4, lyric overlays, verified playback.
A job is COMPLETED only if both required branches passed; otherwise PARTIAL_SUCCESS, NEEDS_INPUT/REVIEW, or FAILED.

## Supporting deliverables
`timing.json`, `karaoke.ass`, optional `karaoke.srt`, `job_manifest.json`, `qc_report.json`; batch summary CSV/JSON; structured diagnostics logs. Supporting deliverables separated from user-facing files.

## Production phases
P00 select folders -> P01 scan/classify -> P02 preflight/manifest -> split:
A: stage MP3 -> prepare cover -> ID3/APIC -> compare audio frame hashes -> publish.
B: prepare audio and lyrics -> align phrases/words -> review timing -> resolve visual preset -> generate ASS -> MP4 render -> QC -> publish.
Aggregate branch outcomes -> report. An interrupted/failed/cancelled run is terminal; Retry creates a new run and restarts the song from intake. Version 1 does not resume individual steps.

## User workflows
- Import explicit 1–N folders or select a parent directory (immediate child folders become jobs).
- Inspect asset mapping summary and correct any ambiguity.
- Start batch; watch step progress; inspect exceptions per job; pause/cancel/retry.
- Review low-confidence Thai lyrics/timing through timeline.
- Select preset; preview on own image/lyrics; approve; export.
- Open output path and batch report. Do not show a false successful state after render-only completion.

## Platform constraints
- Windows 11 x64 baseline; target 8 GB RAM, CPU-only. Development CPython **3.12.10**; preserve capability to test additional versions separately.
- Headless Python modular engine; first planned GUI PySide6; portable onedir distribution without installer.
- Central PathManager; no absolute installation paths committed into SSOT.
- UI/program-generated numbers ASCII digits 0–9, independent of Windows locale.
- SQLite operational store via SQLAlchemy 2.x, **all persistent database schema migrations via Alembic**; schema versions checked on launch.

## Security/privacy
No automatic cloud uploads. Explicit opt-in per AI provider, redact secrets from logs, never log raw audio/lyrics by default, escape/validate paths, prevent source overwrite, use isolated temp and bounded resources.

## Acceptance gates
Input mapping, MP3 frame preservation, lyric approval, renderer capability support, safe-area/layout, MP4 decode/duration, original source hash unchanged, publication integrity, UI reconciliation. See KPI_FRAMEWORK.md for proposed (unmeasured) targets.
