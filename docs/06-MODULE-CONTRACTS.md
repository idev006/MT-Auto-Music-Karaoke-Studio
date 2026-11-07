# Module contracts and engineering boundaries

## Architecture rule
Only application/orchestrator coordinates modules. Domain code imports no Qt, FFmpeg, SQLAlchemy or providers. Adapters implement protocols; capability contracts are versioned. Side effects occur only at explicit ports.

## Modules and contracts
| Module | Input | Output | Failure semantics |
|---|---|---|---|
| FolderIntake | folder list, scan mode | normalized BatchCandidate | duplicate/not found |
| AssetDiscovery | folder URI, scanner profile | candidate AssetInventory | no match/ambiguous |
| Preflight | asset mapping, output policy | ValidationReport, manifest | corrupt/readonly |
| AudioAnalyzer | MP3 bytes locator | duration/audio profile/analysis artifacts | invalid audio/timeout |
| LyricsParser | TXT/DOCX or existing ID3 lyric payload | versioned LyricsRevision | encoding/missing |
| Alignment | approved lyrics, audio locator, model configuration | TimelineCandidate+confidence+provenance | low confidence/model unavailable |
| TimingReview | candidate + corrections + expected revision | approved TimingRevision | conflict/rejection |
| Artwork | MP3 locator, cover locator, metadata policy | staged MP3, verification report | invalid tag/frame mismatch |
| PresetResolver | id, version, overrides, renderer capability | effective KaraokeDisplayObject | unsupported feature |
| SubtitleRenderer | timeline, object, image dimensions | ASS/SRT + reference frames | overflow/font absent |
| VideoRenderer | background, MP3, ASS, profile | staged MP4 + media info | FFmpeg failure/resource |
| QA | staged artifact, expected invariants | signed/traceable QCResult | rejected artifact |
| Publisher | verified staging, root-relative destination | final ArtifactManifest | collision/full disk |
| PathManager | runtime and logical root IDs | validated filesystem Paths | root missing/traversal |
| Persistence | commands, expected revision | snapshots + atomic outbox insert | revision conflict/DB busy |
| EventGateway | durable events, consumer cursor | UI updates/snapshots | disconnect/replay |
| Orchestrator | DAG/step result/state | state transitions and next steps | illegal transition |

## Example protocol style (illustrative, not implemented)
```python
from typing import Protocol

class ArtworkPort(Protocol):
    def embed_cover(self, request: "CoverRequest") -> "StagedMP3": ...

class VideoRenderPort(Protocol):
    def render(self, request: "RenderRequest") -> "StagedVideo": ...
```

## Versioned DTO minimums
- `JobManifest`: id, schema_version, asset refs+hashes, immutable config revision, branch states.
- `StepRequest`: job_id, step_id, attempt_id, input_hash, config_snapshot, deadline.
- `StepResult`: status, verified staging refs, metrics, typed error, tool_versions.
- `DomainEvent`: event_id, monotonic sequence, schema_version, event_type, UTC time, correlation ID, payload.
- `LyricsTimeline`: lyrics_revision, model, phrase_occurrence IDs, segments and tokens with rational/decimal time; approval.
- `ArtifactManifest`: output root ID, relative locator, hash, codec metadata, QC evidence, source hashes.
- `ErrorRecord`: error code and classified remediation.
- `PresetDescriptor`: id/version/schema_version, inherited settings, required capabilities.

## Contract rules
1. Input/Output schema never depends on PySide6 types.
2. Each adapter has contract tests and fake/stub implementation for unit tests.
3. Interface changes require schema migration or compatibility strategy, contract fixtures and ADR.
4. Worker and UI events use at-least-once semantics and idempotent consumers.
5. Filename/paths use validated root-relative references; no arbitrary raw shell command strings.
6. Timing SSOT cannot be overwritten by visual overrides; edits create new revisions.
7. Program-generated displayed digits use ASCII 0–9; source bytes preserved.
