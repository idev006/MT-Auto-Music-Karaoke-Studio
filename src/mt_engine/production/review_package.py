"""Stable review DTOs inspired by reference-anchor karaoke correction workflows."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from .lyrics import TimedLine, TranscriptSegment
from .qc import build_alignment_checks
from .timing_domain import TimelineValidation


def build_timing_review_package(
    timing: tuple[TimedLine, ...],
    transcript: tuple[TranscriptSegment, ...],
    validation: TimelineValidation,
    *,
    audio_sha256: str,
    lyrics_sha256: str,
) -> dict[str, object]:
    checks = build_alignment_checks(timing, transcript)
    findings_by_line: dict[int, list[dict[str, object]]] = defaultdict(list)
    for finding in validation.findings:
        primitive = {
            "code": finding.code,
            "severity": finding.severity,
            "detail": finding.detail,
        }
        for line_index in finding.line_indices:
            findings_by_line[line_index].append(primitive)

    occurrence_counts: dict[str, int] = defaultdict(int)
    phrases = []
    for index, (line, check) in enumerate(zip(timing, checks, strict=True)):
        occurrence_index = occurrence_counts[line.text]
        occurrence_counts[line.text] += 1
        phrase_id = hashlib.sha256(
            f"{lyrics_sha256}:{index}:{occurrence_index}:{line.text}".encode()
        ).hexdigest()[:24]
        line_findings = findings_by_line.get(index, [])
        if any(finding["severity"] == "BLOCK" for finding in line_findings):
            state = "CONFLICT"
        elif line.highlight_spans and all(
            span.evidence == "human_locked" for span in line.highlight_spans
        ):
            state = "LOCKED"
        elif not check.has_overlapping_asr_evidence:
            state = "UNKNOWN"
        else:
            state = "PROPOSED"
        phrases.append(
            {
                "phrase_id": phrase_id,
                "line_index": index,
                "occurrence_index": occurrence_index,
                "text": line.text,
                "proposed_start": line.start,
                "proposed_end": line.end,
                "state": state,
                "timing_source": "ASR_PHRASE_PROPOSAL_NOT_RELEASE_EVIDENCE",
                "render_mode": "LINE_CUE_ONLY",
                "asr_similarity": check.similarity,
                "has_overlapping_asr_evidence": check.has_overlapping_asr_evidence,
                "findings": line_findings,
            }
        )
    return {
        "schema_version": 1,
        "audio_sha256": audio_sha256,
        "lyrics_sha256": lyrics_sha256,
        "review_policy": "NO_PROGRESSIVE_HIGHLIGHT_WITHOUT_HUMAN_SYLLABLE_LOCK",
        "phrases": phrases,
        "counts": {
            "PROPOSED": sum(phrase["state"] == "PROPOSED" for phrase in phrases),
            "UNKNOWN": sum(phrase["state"] == "UNKNOWN" for phrase in phrases),
            "CONFLICT": sum(phrase["state"] == "CONFLICT" for phrase in phrases),
            "LOCKED": sum(phrase["state"] == "LOCKED" for phrase in phrases),
        },
    }
