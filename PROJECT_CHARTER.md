# Project charter — MT Auto Music & Karaoke Studio

## Vision
Produce repeatable, auditable, high-quality audio-cover and karaoke-video deliverables from **1–N song asset folders**, primarily on Windows 11 (CPU-only / 8 GB RAM target).

## In scope
- A folder typically has an existing MP3, cover image, still image for MP4 and optional lyrics TXT/DOCX.
- Folder discovery, asset classification, ambiguous mapping review, validation and batch queuing.
- Non-destructive cover embedding in a copied MP3 (ID3/APIC).
- Still-image MP4, lyric synchronization, Thai-safe subtitle typography and optional word highlighting.
- Quality assurance, preview, review gates, checkpoint/retry/recovery, SSOT/event journal.
- Future PySide6 portable application; headless engine with CLI/test access first.
- Preset target catalog: eight visual groups, five presets each (40 planned), delivered incrementally.

## Out of scope
- Composing, synthesizing, remixing or mastering music.
- Re-encoding source MP3 audio during cover embedding.
- Guaranteed fully automatic and exact Thai lyric alignment without measured evidence.
- Installer.exe, cloud microservices, mandatory paid AI services.

## Success criteria
- No original files modified.
- Outputs never declared complete until required quality gates pass.
- Failed job or MP4 branch does not invalidate another job or successfully produced MP3 branch.
- Windows deployment independent of absolute install path; visible program numerals ASCII 0–9.
- Engine and workflows testable without desktop UI.

## Decisions pending validation
- Alignment engine performance on sung Thai (with human-annotated ground truth).
- Preview/final renderer parity; font bundling/licensing.
- Device playback compatibility matrix and runtime performance on minimum hardware.

Owner approval: initial repository foundation authorized 2026-11-07. This document is a requirements baseline, not acceptance evidence.
