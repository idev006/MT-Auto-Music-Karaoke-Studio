"""Human-reviewed timing lock ingestion for correctness-only rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .lyrics import HighlightSpan, TimedLine


class TimingLockError(ValueError):
    """A timing lock is missing, stale, incomplete or structurally invalid."""


@dataclass(frozen=True, slots=True)
class VerifiedTimingLock:
    timing: tuple[TimedLine, ...]
    reviewer: str
    reviewed_at: str
    audio_sha256: str
    lyrics_sha256: str


def lyrics_sha256(lyrics: tuple[str, ...]) -> str:
    canonical = "\n".join(lyrics).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_verified_timing_lock(
    path: Path,
    *,
    expected_audio_sha256: str,
    expected_lyrics: tuple[str, ...],
) -> VerifiedTimingLock:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TimingLockError(f"Cannot read timing lock: {path}") from exc

    if payload.get("schema_version") != 1 or payload.get("state") != "LOCKED":
        raise TimingLockError("Timing lock must use schema_version=1 and state=LOCKED")
    if payload.get("render_mode") != "SYLLABLE_PROGRESSIVE":
        raise TimingLockError("Correctness-only MP4 requires render_mode=SYLLABLE_PROGRESSIVE")
    if payload.get("audio_sha256") != expected_audio_sha256:
        raise TimingLockError("Timing lock audio hash does not match the source MP3")
    expected_lyrics_hash = lyrics_sha256(expected_lyrics)
    if payload.get("lyrics_sha256") != expected_lyrics_hash:
        raise TimingLockError("Timing lock lyrics hash does not match canonical lyrics")
    reviewer = str(payload.get("reviewer", "")).strip()
    reviewed_at = str(payload.get("reviewed_at", "")).strip()
    if not reviewer or not reviewed_at:
        raise TimingLockError("Timing lock requires reviewer and reviewed_at evidence")

    raw_lines = payload.get("lines")
    if not isinstance(raw_lines, list) or len(raw_lines) != len(expected_lyrics):
        raise TimingLockError("Timing lock must contain every canonical lyric line exactly once")

    timing = []
    previous_end = 0.0
    for expected_index, (raw_line, expected_text) in enumerate(
        zip(raw_lines, expected_lyrics, strict=True)
    ):
        if raw_line.get("line_index") != expected_index or raw_line.get("text") != expected_text:
            raise TimingLockError(f"Timing lock line {expected_index} does not match canonical lyrics")
        start = float(raw_line["start"])
        end = float(raw_line["end"])
        if start < previous_end or end <= start:
            raise TimingLockError(f"Timing lock line {expected_index} overlaps or has invalid duration")
        raw_spans = raw_line.get("highlight_spans")
        if not isinstance(raw_spans, list) or not raw_spans:
            raise TimingLockError(
                f"Timing lock line {expected_index} requires reviewed progressive spans"
            )
        spans = tuple(
            HighlightSpan(
                text=str(raw_span["text"]),
                start=float(raw_span["start"]),
                end=float(raw_span["end"]),
                sustained=bool(raw_span.get("sustained", False)),
                evidence="human_locked",
            )
            for raw_span in raw_spans
        )
        if any(
            raw_span.get("unit") != "THAI_SYLLABLE" or raw_span.get("state") != "LOCKED"
            for raw_span in raw_spans
        ):
            raise TimingLockError(
                f"Timing lock line {expected_index} contains a non-locked syllable span"
            )
        if "".join(span.text for span in spans) != expected_text:
            raise TimingLockError(f"Timing lock spans do not reconstruct line {expected_index}")
        if abs(spans[0].start - start) > 0.001 or abs(spans[-1].end - end) > 0.001:
            raise TimingLockError(f"Timing lock spans do not cover line {expected_index}")
        for left, right in pairwise(spans):
            if left.end > right.start or left.end <= left.start:
                raise TimingLockError(f"Timing lock spans overlap in line {expected_index}")
        if spans[-1].end <= spans[-1].start:
            raise TimingLockError(f"Timing lock final span is invalid in line {expected_index}")
        timing.append(TimedLine(start, end, expected_text, spans))
        previous_end = end

    return VerifiedTimingLock(
        tuple(timing), reviewer, reviewed_at, expected_audio_sha256, expected_lyrics_hash
    )
