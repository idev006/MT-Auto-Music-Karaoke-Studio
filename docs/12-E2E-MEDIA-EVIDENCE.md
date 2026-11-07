# Real-media end-to-end evidence

Evidence date: 2026-11-07. Environment: Windows, CPython 3.12 x64, local FFmpeg build dated 2025-10-30. This record proves the direct single-folder media vertical slice only; it is not evidence for multi-worker scheduling, portable packaging, or timing accuracy.

## Fixture and outputs

- Source folder: `src_for_test/เหงาเหลือเกิน`
- Destination folder: `dest_for_test/เหงาเหลือเกิน`
- Run: `194c1f4277d04070b1be750bdcaef91d`
- Output MP3: `song_with_cover.mp3`
- Output MP4: `karaoke.mp4`
- Production evidence: `production_data/manifest.json`, `qc_report.json`, `timing.json`, `karaoke.ass`

The single portrait image was explicitly authorized for both cover and video background. The source MP3 SHA-256 remained `be54051e1827e7a07e62a57c28d07ee4a1c0ae054706a575934a3adf35f604fc` after production.

## Verified results

| Check | Result |
|---|---|
| MP3 source audio preserved | PASS — source/output MPEG audio payload SHA-256 both `d82fc07dfeee15a36305939510bf0b556f875b5fb23b71a53bbeb0f15529f253` |
| Embedded cover | PASS — one APIC frame; image hash matches input |
| MP4 decode | PASS — complete FFmpeg decode to null |
| Orientation selection | PASS — 1055x1490 portrait input selected the 1080x1920 (9:16) canvas |
| MP4 streams | PASS — 1080x1920 H.264/yuv420p and AAC, duration 273.633333 s |
| Thai subtitle render | PASS — visual sample at 120 s rendered Thai text and active highlight |
| Missing-subtitle regression | PASS — visual sample at 47 s contains a lyric event and active highlight |
| Automated suite | PASS — 61 tests; Ruff clean; portrait, landscape and square policies covered |

## Honest limitation

Lyrics were read from embedded ID3 text. The earlier VAD-enabled pass detected only a short island and could not synchronize the song. The current pass disables VAD, supplies canonical lyrics as the decoding prompt, and produces ASR segments spanning 241.64 seconds of the 272.43-second song. A monotonic fuzzy aligner anchors canonical groups of one to three lines to those timestamps and interpolates only unrecognized gaps; automated checks require all 46 events to remain ordered and non-overlapping. The run still records `SUCCEEDED_WITH_TEST_TIMING_OVERRIDE`, `review_required=true`, and `measured_alignment_kpi=false`: segment-level synchronization is materially improved, but word-level alignment has not yet been benchmarked or human-approved.
