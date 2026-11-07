# Automated test strategy and acceptance evidence

## Testing principles
Tests begin before GUI implementation; run headless in CI and Windows local terminal. Distinguish a documented KPI target from an empirically measured score. Critical tests must pass 100% before release; coverage alone is not sufficient.

## Test suites
| Suite | Examples | Frequency |
|---|---|---|
| Unit | path roots, digit format, event/state transitions, lyric segmentation | every push |
| Contract | typed adapters, event payload schema, error classification, migration version | every push |
| Integration | DB transactions+outbox, orchestrator+worker, cache dependencies | every push |
| Media E2E | embed APIC and compare MP3 frames; still-image MP4+ASS and decode | release / on media changes |
| Visual regression | Thai combining marks, multiple fonts, lyric safe area, preview-parity key frames | media release |
| Lyrics benchmark | phrase MAE, word P95, repeated chorus, speech vs singing | offline benchmark |
| Fault injection | worker kill, disk full, DB busy, event dupes, moved roots | nightly / release |
| Portability | relocated Windows onedir, paths with Unicode, no Python installed | release |
| Performance | 8 GB RAM CPU-only, 1/10/50/100 jobs, render RTF | milestone |
| Accessibility/locale | program numerals 0–9, long Thai lines, controls on multiple DPI | UI release |

## Reference assets
Small synthesized/publicly usable test MP3 and cover art go into test fixtures; large or copyrighted song samples must not be committed unless rights permit. Audio for Thai benchmark is versioned with annotation provenance, permissions, model and reviewer IDs. Redact any sensitive content.

## CI
Windows runners Python 3.12 as required; optional Python 3.11 compatibility test allowed but not the primary target. Install editable package and run lint, pytest and schema/contract checks. Alembic tests must verify upgrade of empty and prior-schema DB; data invariants and rollback. Run resource-heavy tests separately with explicit labels.

## Acceptance artifacts
Each release produces a run manifest: Git SHA, OS/CPU/RAM/Python versions, dependencies, tools (FFmpeg), input fixture hashes, pass/fail/blocked, actual KPI values and logs/diagnostic links. No score without evidence.

## Immediate foundation status
Basic PathManager and ASCII numeral tests are written. CI file exists but passing run status and full media tests are **not yet verified**. GUI, alignment and renderer are not implemented.
