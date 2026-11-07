# Requirements baseline

## Input
- R-001: Accept explicit list of 1–N folders and/or a parent directory containing song folders.
- R-002: Per folder identify an existing MP3, a cover image, a still-image MP4 background, and optionally lyrics TXT/DOCX.
- R-003: Never infer ambiguous asset roles silently. Reject or request mapping; reject damaged files.
- R-004: Each song folder is an independent Job; failed jobs never block other valid jobs.
- R-005: Original sources are read-only and hash-verified where practical.

## MP3 pipeline
- R-101: Copy input MP3 to staging and embed image in ID3/APIC, preserving audio frames.
- R-102: Verify embedded artwork reads back and source audio integrity before publish.
- R-103: MP3 cover branch may succeed while MP4 is blocked.

## MP4 pipeline
- R-201: Use user-selected still image for entire MP4; do not invent substitute imagery.
- R-202: Use the original song as audio source and H.264/AAC at 30 fps. Select the default canvas from the background image orientation: portrait produces 1080x1920 (9:16); landscape produces 1920x1080 (16:9). Square images use the landscape default.
- R-203: Lyrics are optional input; without them, the MP4 branch needs transcription or user input.
- R-204: Lyrics SSOT and timing SSOT are distinct from visual configuration.
- R-205: Thai phrasing, repeat choruses and word/syllable highlighting must be supported in intended full product.
- R-206: Uncertain alignment requires review; manual timing corrections persist independently of rendering.
- R-207: Karaoke object target has 14 property groups; preset catalog target eight groups x five presets.
- R-208: Renderer compatibility and safe-area checks precede final publish.

## Platform
- R-301: Python headless modular engine, orchestrator, reliable job queue, checkpoint and error classification.
- R-302: Operational SSOT SQLite + transactional event outbox and idempotent consumers.
- R-303: Multiple UIs over common commands/queries/events. First shipped UI intended PySide6.
- R-304: Portable Windows one-folder delivery; installer.exe not required.
- R-305: Central PathManager; no hard-coded install paths; root-relative locators.
- R-306: All program-generated displayed numerals ASCII 0–9 regardless of OS locale; preserve original lyric text in SSOT.
- R-307: Tests at unit, contract, integration, end-to-end, media and Windows portability levels.
- R-308: One folder is one Job. Each execution is an immutable-history JobRun with at most one active logical JobWorker owner; retry starts a new run from intake.
- R-309: Multiple Jobs may progress concurrently under bounded resource admission. The 8 GB baseline permits only one shared heavyweight operation across faster-whisper, Demucs and final FFmpeg render until benchmarks approve another profile.
- R-310: Runtime progress may be held in memory and per-run diagnostic logs, but operational state, ownership, branch outcomes and published artifacts remain in SQLite. No generated state/log is written into source folders.

## Error contract
- E01 Input; E02 Asset; E03 Metadata; E04 Lyrics; E05 Alignment; E06 Renderer; E07 Resource; E08 Persistence; E09 Runtime; E10 Integration.
- All errors carry code, severity, scope, retryability, correlation id, user-facing message and suggested action.
- A tool adapter may retry a proven transient, side-effect-free operation within a small bound. Failed/cancelled/interrupted runs are terminal; Job retry creates a new whole run. Missing assets/ambiguous mapping require input.
- Stage artifacts and publish only after successful media checks; preserve originals; recover stale worker leases on restart.

## Acceptance
Implementation must demonstrate the requirements with tests and evidence; requirement specification alone is not proof.
