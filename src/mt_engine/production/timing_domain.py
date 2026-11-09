"""Versioned singing-aware timing contracts and fail-closed validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from itertools import pairwise

from .lyrics import TimedLine


class PhraseState(StrEnum):
    AUTO = "AUTO"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    LOCKED = "LOCKED"


@dataclass(frozen=True, slots=True)
class SyllableSpan:
    text: str
    sung_start: float
    sung_end: float
    highlight_start: float
    highlight_end: float
    sustained: bool
    confidence: float
    evidence: str


@dataclass(frozen=True, slots=True)
class PhraseOccurrence:
    phrase_id: str
    line_index: int
    occurrence_index: int
    text: str
    sung_start: float
    sung_end: float
    highlight_start: float
    highlight_end: float
    confidence: float
    evidence: tuple[str, ...]
    state: PhraseState
    syllables: tuple[SyllableSpan, ...] = ()


@dataclass(frozen=True, slots=True)
class TimelineCandidate:
    schema_version: int
    candidate_id: str
    audio_sha256: str
    lyrics_revision_id: str
    method: str
    phrases: tuple[PhraseOccurrence, ...]

    def to_primitive(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TimelineFinding:
    code: str
    severity: str
    line_indices: tuple[int, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class TimelineValidation:
    status: str
    findings: tuple[TimelineFinding, ...]
    line_count: int
    minimum_duration: float | None
    maximum_duration: float | None

    def to_primitive(self) -> dict[str, object]:
        return asdict(self)


def validate_timeline(
    timing: tuple[TimedLine, ...],
    *,
    minimum_phrase_seconds: float = 0.5,
    maximum_phrase_seconds: float = 12.0,
    maximum_normalized_characters_per_second: float = 12.0,
) -> TimelineValidation:
    findings: list[TimelineFinding] = []
    durations = [line.end - line.start for line in timing]
    for index, duration in enumerate(durations):
        if duration <= 0:
            findings.append(
                TimelineFinding("NON_POSITIVE_DURATION", "BLOCK", (index,), f"{duration:.3f}s")
            )
        elif duration < minimum_phrase_seconds:
            findings.append(
                TimelineFinding(
                    "PHRASE_TOO_SHORT", "BLOCK", (index,),
                    f"{duration:.3f}s < {minimum_phrase_seconds:.3f}s",
                )
            )
        if duration > maximum_phrase_seconds:
            findings.append(
                TimelineFinding(
                    "PHRASE_TOO_LONG", "REVIEW_REQUIRED", (index,),
                    f"{duration:.3f}s > {maximum_phrase_seconds:.3f}s",
                )
            )
        normalized_character_count = sum(character.isalnum() for character in timing[index].text)
        reading_rate = normalized_character_count / duration if duration > 0 else float("inf")
        if reading_rate > maximum_normalized_characters_per_second:
            findings.append(
                TimelineFinding(
                    "IMPLAUSIBLE_LYRIC_RATE", "BLOCK", (index,),
                    (
                        f"{reading_rate:.2f} chars/s > "
                        f"{maximum_normalized_characters_per_second:.2f} chars/s"
                    ),
                )
            )
    for left_index, (left, right) in enumerate(pairwise(timing)):
        if left.end > right.start:
            findings.append(
                TimelineFinding(
                    "PHRASE_OVERLAP", "BLOCK", (left_index, left_index + 1),
                    f"overlap={left.end - right.start:.3f}s",
                )
            )
    severities = {finding.severity for finding in findings}
    status = "BLOCKED" if "BLOCK" in severities else (
        "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in severities else "PASS"
    )
    return TimelineValidation(
        status, tuple(findings), len(timing),
        min(durations) if durations else None,
        max(durations) if durations else None,
    )
