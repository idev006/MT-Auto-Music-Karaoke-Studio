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

## Correctness-only release workflow

A final `karaoke.mp4` is a released artifact, not merely a successful FFmpeg render:

1. A timing lock declares `LOCKED` and `SYLLABLE_PROGRESSIVE`, binds the source audio and
   canonical lyrics SHA-256 hashes, identifies the reviewer and review time, and contains every
   canonical line in order. Every progressive unit declares `THAI_SYLLABLE` and `LOCKED` and the
   spans reconstruct the canonical text exactly.
2. `produce-song --timing-lock <file>` bypasses ASR timing, validates the lock and renders
   `production_data/review_candidate.mp4`. It does not publish `karaoke.mp4`; state becomes
   `AWAITING_FINAL_LISTENING_QC`.
3. A sound engineer listens to the complete rendered candidate. The sign-off binds the candidate,
   audio and lyrics hashes and declares `full_listening_completed=true`.
4. `release-reviewed --target <folder> --signoff <file>` verifies the candidate has not changed,
   verifies automated media QC and atomically publishes `karaoke.mp4`. The released state is
   `RELEASED_VERIFIED`.

Changing audio, lyrics or rendered candidate bytes invalidates the corresponding lock/sign-off.
Automated proposals, including structurally plausible ones, cannot enter this release path without
human locks and final listening sign-off.
An explicitly enabled unreviewed test run may create
`production_data/diagnostic_candidate.mp4` for engineering evidence, but its manifest output
`mp4` remains null and it can never be released through the final-listening command.

## Pre-render validation

Expensive rendering is downstream of deterministic gates. The engine inventories every embedded
`USLT` and `SYLT` frame before timing work. Conflicting USLT texts fail closed; identical duplicate
frames are permitted and selected deterministically. USLT is the canonical text authority only and
never timing truth. SYLT, when present, is candidate timing evidence that still requires validation
against the current audio and locks.

For a correctness-only review render, `pre_render_validation.json` records audio and lyrics
identity, timing-lock hash, timeline structure, locked-span completeness, audio-duration bounds and
ASS centisecond projection error. A failed locked gate prevents `write_ass` and FFmpeg execution.
Acoustic alignment remains explicitly marked pending until an independently benchmarked analyzer
exists; human timing locks are the current authority and final listening QC remains mandatory.
No percentage-based synchronization tolerance is part of the specification.

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

Implementation retains faster-whisper word timestamps/probabilities as diagnostic evidence only.
Automatic ASR proposals no longer create progressive ASS spans: Thai Whisper tokens are not
syllable boundaries, and whitespace tokens are not a valid Thai singing unit. Unlocked diagnostic
candidates render `LINE_CUE_ONLY` without `\\kf`. Progressive spans can enter the renderer only
through a hash-bound human timing lock.

Each run also emits `timing_review_package.json`, borrowing the useful stable-identity and review
workflow concepts from reference-anchor karaoke tools without importing their English-centric
word/syllable assumptions. Every canonical line receives a deterministic phrase ID, repeat
occurrence index, ASR evidence summary and one of `PROPOSED`, `UNKNOWN`, `CONFLICT`, or `LOCKED`.
Repeated text therefore remains distinct across the song and unresolved evidence cannot silently
become release timing.

The runner now fails closed when structural timing validation is `BLOCKED`: it persists timing,
QC and manifest evidence, publishes no `karaoke.mp4`, skips frame/Vision QC and records
`BLOCKED_TIMING_VALIDATION`. The MP3 cover branch remains independently publishable. This safety
behavior does not improve alignment accuracy; it prevents an invalid timing candidate from being
mistaken for a completed karaoke video.
