# ADR-0001: Foundation architecture
Status: Accepted as design baseline; implementation pending
Date: 2026-11-07

## Decision
Use a UI-agnostic Python modular monolith structured around ports/adapters and durable workflow orchestration. SQLite operational SSOT + transactional outbox; filesystem immutable assets with hashes; Git engineering SSOT. A portable Windows PySide6 UI is a later adapter. Central PathManager resolves every managed path.

## Rationale
The primary deployment target is one Windows PC, potentially 8 GB RAM without a GPU. Microservices or remote queue infrastructure create avoidable operational dependencies. Media and AI workers still require process isolation.

## Consequences
- No Qt import inside engine/domain.
- Headless CLI/tests before desktop UI.
- Per-job independent MP3 and MP4 branches with distinct state.
- Copy-on-write outputs; never overwrite source media.
- Explicit ASCII-digit presentation formatting.
- Schema versions for events, presets, timing and manifests.
- Reference frame/ground-truth alignment evaluations required for releases.

## Revisit when
Multi-machine distributed compute, simultaneous editors, or persistent remote hosting becomes a demonstrated requirement.
