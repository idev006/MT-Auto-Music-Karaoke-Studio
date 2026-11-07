# Requirement traceability and delivery matrix

This document makes the approval/test relationship explicit. State values: DOCUMENTED, SCAFFOLDED, IMPLEMENTED, VERIFIED. DOCUMENTED is **not** a delivery claim.

| Requirement | Design owner | Contract/Doc | Validation | State |
|---|---|---|---|---|
| 1–N folder intake | AssetEngine | 01, 02, 09 | integration multi-folder scenarios | DOCUMENTED |
| safe asset mapping | Preflight | 01, 06 | ambiguity and explicit single-image-role tests | VERIFIED (single-folder slice) |
| MP3 cover without audio changes | ArtworkEngine | 01, 02, 12 | audio-payload hash/APIC readback | VERIFIED (fixture) |
| continuous still-image MP4 | VideoEngine | 01, 02, 12 | full decode, probe and reference frame | VERIFIED (fixture) |
| Thai lyric timing & review | Alignment/Review | 02, 05 | annotated benchmark | DOCUMENTED |
| karaoke display 14 property groups | Layout/Renderer | 05 | schema/visual tests | DOCUMENTED |
| 8 x 5 presets | Creative/Renderer | 05 | version/preview parity | DOCUMENTED |
| R-301 headless operational engine | Application | 02, 06, 12, ADR-0003 | real-media E2E plus state/ownership/recovery tests | IMPLEMENTED (direct single-folder slice) |
| R-308 one JobWorker per folder run | Application | 02, 11, ADR-0003 | one-owner, stale-result, whole-run retry tests | DOCUMENTED |
| R-309 bounded parallel jobs | Scheduler | 02, 11, Kanban plan | 1/2/5/10-job and HEAVY-token tests | DOCUMENTED |
| R-310 memory/log versus SQLite ownership | Persistence/Observability | 02, 03, ADR-0003 | crash/restart and source-immutability tests | DOCUMENTED |
| SQLite via SQLAlchemy/Alembic | Persistence | 03 | fresh migration, FK, rollback, incompatible revision tests | VERIFIED (initial schema slice) |
| fault isolation / whole-run restart | Recovery | 04, 11, ADR-0003 | failure/cancel/interrupted/new-run scenarios | DOCUMENTED |
| path-independent portable | PathManager | 08 | relocated root / clean PC | SCAFFOLDED |
| numeral ASCII 0–9 | Formatting boundary | 08 | unicode-digit tests | SCAFFOLDED |
| PySide6 UI event sync | Qt Adapter | 08 | reconnect/Qt test | DOCUMENTED |
| KPI release gates | QA | KPI_FRAMEWORK, 07 | evidence dashboard | DOCUMENTED |

## Sign-off
ADR-0003 and end-to-end sequences are the current worker/retry SSOT and supersede older step-resume assumptions. The persistence foundation implements fenced ownership, while the media vertical-slice CLI still bypasses that coordinator. Real rendered-media evidence exists in document 12; multi-worker and alignment-quality acceptance do not. Every IMPLEMENTED/VERIFIED change requires passing evidence, source commit SHA, environment and reviewer attribution.
