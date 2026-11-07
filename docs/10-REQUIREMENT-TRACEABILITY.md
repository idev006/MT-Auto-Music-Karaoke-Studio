# Requirement traceability and delivery matrix

This document makes the approval/test relationship explicit. State values: DOCUMENTED, SCAFFOLDED, IMPLEMENTED, VERIFIED. DOCUMENTED is **not** a delivery claim.

| Requirement | Design owner | Contract/Doc | Validation | State |
|---|---|---|---|---|
| 1–N folder intake | AssetEngine | 01, 02, 09 | integration multi-folder scenarios | DOCUMENTED |
| safe asset mapping | Preflight | 01, 06 | ambiguous role tests | DOCUMENTED |
| MP3 cover without audio changes | ArtworkEngine | 01, 02 | frame compare/ID3 readback | DOCUMENTED |
| continuous still-image MP4 | VideoEngine | 01, 02 | frame sample coverage | DOCUMENTED |
| Thai lyric timing & review | Alignment/Review | 02, 05 | annotated benchmark | DOCUMENTED |
| karaoke display 14 property groups | Layout/Renderer | 05 | schema/visual tests | DOCUMENTED |
| 8 x 5 presets | Creative/Renderer | 05 | version/preview parity | DOCUMENTED |
| durable orchestrator | Application | 02, 06 | recovery/state tests | DOCUMENTED |
| SQLite via SQLAlchemy/Alembic | Persistence | 03 | fresh migration, FK, rollback, incompatible revision tests | VERIFIED (initial schema slice) |
| fault isolation / resume | Recovery | 04 | injection scenarios | DOCUMENTED |
| path-independent portable | PathManager | 08 | relocated root / clean PC | SCAFFOLDED |
| numeral ASCII 0–9 | Formatting boundary | 08 | unicode-digit tests | SCAFFOLDED |
| PySide6 UI event sync | Qt Adapter | 08 | reconnect/Qt test | DOCUMENTED |
| KPI release gates | QA | KPI_FRAMEWORK, 07 | evidence dashboard | DOCUMENTED |

## Sign-off
Architecture baseline approved for documentation; no actual rendered-media or alignment quality acceptance yet. Every IMPLEMENTED/VERIFIED change requires passing evidence, source commit SHA, environment and reviewer attribution.
