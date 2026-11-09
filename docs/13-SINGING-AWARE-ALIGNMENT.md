# Singing-aware lyrics alignment

Status: approved architecture, incremental implementation. This document is the SSOT for melisma, sustained syllables, phrase locks and karaoke synchronization quality. Speech recognition timestamps and Vision QC alone are not release evidence for sung alignment.

## Root cause

Singing differs from speech: vowels may be sustained, pitch may slide, phrases repeat, breaths create gaps, accompaniment masks consonants and harmonies compete with the lead vocal. The legacy implementation stores only `TimedLine(start, end, text)` and renders one uniform ASS `\\kf` tag for the whole line. It cannot represent a sustained final syllable and must not claim word-level synchronization.

## Target pipeline

`AudioPrep -> optional VocalSeparator -> VocalAnalyzer -> PhraseAligner -> ThaiSyllableAligner -> SustainDetector -> TimingValidator -> PhraseLockManager -> ReviewWorkflow -> ASS Renderer`

Whisper is a replaceable phrase-anchor adapter. OpenRouter Vision is a render-text adapter. Neither owns the timing SSOT. Vocal separation is conditional and uses the global HEAVY token on the 8 GB profile.

## Timing SSOT v2

- `TimelineCandidate`: immutable candidate identity, audio/lyrics/config hashes, method and provenance.
- `PhraseOccurrence`: line and occurrence identity, sung onset/offset, highlight onset/offset, confidence, evidence and review state.
- `SyllableSpan`: separate sung and highlight clocks, sustain flag, confidence and evidence.
- `PhraseState`: `AUTO`, `REVIEW_REQUIRED`, or `LOCKED`.

Sound-engineering policy keeps acoustic truth separate from presentation timing:

- `sung_start` uses the earliest reliable consonant attack. A detected vowel onset is a
  `VOWEL_FALLBACK` and requires review; it must not silently impersonate a consonant boundary.
- The pilot presentation preset uses 120 ms highlight lead, 80 ms release lag and 1,200 ms
  static line pre-roll. These are versioned, configurable hypotheses to calibrate with listeners,
  never offsets baked into acoustic evidence.
- A melisma remains one lyric syllable through its detected sung tail. Pitch changes do not
  create extra lyric tokens, and Thai code points are never treated as independent syllables.
- Phrase-only evidence renders as `LINE_CUE_ONLY`; it must not produce a progressive `\\kf`
  sweep. Progressive rendering requires evidence or a lock for every displayed unit.
- Canonical lead, backing vocal and ad-lib are separate lanes. Secondary vocals cannot consume,
  shift or create primary canonical occurrences.

Approved corrections create a new immutable revision. Phrase Lock must preserve approved onset, offset and syllable spans across reruns. Existing `timing_revisions.timeline_json` may carry schema v2 until benchmark evidence justifies normalized tables.

## Fail-closed gates

1. Timeline integrity: positive duration, no overlap, provisional minimum phrase duration 0.5 s; durations over 12 s require review.
   The provisional normalized-character rate gate is only an emergency plausibility check, not
   proof of Thai syllable alignment. A blocked candidate may persist evidence and publish the
   independent MP3 branch, but it must not render or publish an MP4.
2. Render fidelity: 10–15 stratified plus risk-prioritized frames; Vision/OCR cannot override temporal failure.
3. Phrase accuracy benchmark: onset/offset measured against human annotations.
4. Sustain benchmark: final sung syllable/highlight offset measured against human annotations.
5. Repeat identity: wrong chorus occurrence count must be zero.
6. Lock preservation: approved phrases remain byte-for-byte equivalent in timing projection.

Provisional experimental targets—not achieved claims—are phrase onset MAE <=150 ms, phrase offset MAE <=250 ms, syllable onset P95 <=300 ms, sustained-syllable offset <=300 ms, wrong chorus match 0 and approved phrase preservation 100%.

## Delivery phases

1. Contracts and evidence: Timing SSOT v2, structural validator, retain Whisper word timestamps, renderer compatibility projection.
2. Singing renderer: Thai grapheme/syllable segmentation, multiple ASS karaoke tags, explicit sustained-tail hold.
3. CPU-friendly DSP: analyze 16 kHz mono phrase windows for vocal onset/offset and voiced tail; results remain review-required until benchmarked.
4. Conditional Demucs adapter: source-hash cache, disk/RAM preflight and one HEAVY token; compare original/center/vocal-stem evidence.
5. Phrase Lock and review UI: immutable revisions, localized recompute and import/export corrections.
6. Thai singing benchmark: normal, fast, long melisma, repeated hook, instrumental gaps, harmony and loud accompaniment; separate development and holdout sets.

## Current evidence

The `อยู่เป็นเพื่อนกันนาน ๆ นะ v9` candidate spans most of the song after global sequence alignment, but strict validation blocks it: four phrases are about 0.10–0.145 s, two exceed 12 s and one pair overlaps by 0.086 s. This candidate is not synchronized or publishable even when OpenRouter confirms the rendered text.

Implementation now retains faster-whisper word timestamps/probabilities and can render multiple ASS `\\kf` spans for whitespace-delimited lyric tokens. The final token holds through the phrase end and is marked sustained when its evidence-backed duration is materially longer than the typical token. This removes the one-tag renderer limitation, but it remains `REVIEW_REQUIRED` until Thai syllable segmentation and voiced-tail DSP are benchmarked.

The runner now fails closed when structural timing validation is `BLOCKED`: it persists timing,
QC and manifest evidence, publishes no `karaoke.mp4`, skips frame/Vision QC and records
`BLOCKED_TIMING_VALIDATION`. The MP3 cover branch remains independently publishable. This safety
behavior does not improve alignment accuracy; it prevents an invalid timing candidate from being
mistaken for a completed karaoke video.
