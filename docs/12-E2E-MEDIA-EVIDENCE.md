# Real-media end-to-end evidence

Evidence date: 2026-11-07. Environment: Windows, CPython 3.12 x64, local FFmpeg build dated 2025-10-30. This record proves the direct single-folder media vertical slice only; it is not evidence for multi-worker scheduling, portable packaging, or timing accuracy.

## Fixture and outputs

- Source folder: `src_for_test/เหงาเหลือเกิน`
- Destination folder: `dest_for_test/เหงาเหลือเกิน`
- Run: `7c46dcb4385740468483af7131e5b6dc`
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
| Twelve-frame sampling | PASS — 12 MP4 frames generated; all contain subtitle-region pixels |
| Temporal sync gate | REVIEW REQUIRED — 16 of 46 lines lack sufficient overlapping ASR evidence |
| Reported 2:01 example | CAUGHT — sample at 119.95 s has no overlapping ASR evidence, similarity 0.0 |
| Exact frame-text OCR | REVIEW REQUIRED — no Thai OCR adapter is installed; no false automated PASS is emitted |
| Automated suite | PASS — 61 tests; Ruff clean; portrait, landscape and square policies covered |

## Honest limitation

Lyrics were read from embedded ID3 text. The earlier VAD-enabled pass detected only a short island and could not synchronize the song. The current pass disables VAD, supplies canonical lyrics as the decoding prompt, and produces ASR segments spanning 241.64 seconds of the 272.43-second song. A monotonic fuzzy aligner anchors canonical groups of one to three lines to those timestamps and interpolates only unrecognized gaps; automated checks require all 46 events to remain ordered and non-overlapping.

The risk-prioritized QC correctly demonstrates that this is still insufficient for release: 16 interpolated/low-confidence lines require review, including the user-reported line near 2:01. The run records `SUCCEEDED_WITH_TEST_TIMING_OVERRIDE`, `review_required=true`, and `measured_alignment_kpi=false`. The next alignment tranche needs vocal separation and/or a Thai forced-alignment adapter before the temporal gate can pass.

## Latest diagnostic run — 2026-11-11

This later record supersedes the earlier run only for current implementation behavior. It remains
diagnostic evidence, not synchronization acceptance.

- Fixture: `src_for_test/อยู่เป็นเพื่อนกันนาน ๆ นะ v9`
- Run ID: `15aa43ea247048c2ba543c5dd879981c`
- Output: `dest_for_test/อยู่เป็นเพื่อนกันนาน ๆ นะ v9/karaoke_diagnostic.mp4`
- Video SHA-256: `7293c08fd4a6697612c20300b65cf9995bd7d76609014e7086038a410147f2c3`
- Media verification: complete FFmpeg decode PASS; H.264 + AAC; 1080x1920
- QC sampling: 12 current managed frames; subtitle-region pixels present in all samples
- OpenRouter spend: USD 0.00356855
- Pipeline checkpoint: `COMPLETE`
- Product state: `DIAGNOSTIC_VIDEO_READY_TIMING_BLOCKED`
- Timeline: `BLOCKED`, 6 findings; 8 alignment lines require review
- Automated suite at the same code state: Ruff PASS; pytest `150 passed`

The run proves intake, USLT sidecar fallback, ASR, optional cloud evidence, ASS, FFmpeg, progress,
QC, checkpoint and diagnostic publication. It does not prove lyric/audio synchronization. The
manifest release output remains null and no `karaoke.mp4` was published.
