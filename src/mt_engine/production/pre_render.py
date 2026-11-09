"""Deterministic gates that run before expensive media rendering."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .lyrics import EmbeddedLyricsInventory
from .media import sha256_file
from .timing_domain import TimelineValidation
from .timing_lock import VerifiedTimingLock


def build_pre_render_validation_report(
    *,
    audio_payload_sha256: str,
    audio_duration_seconds: float,
    inventory: EmbeddedLyricsInventory,
    timing_lock_path: Path | None,
    verified_lock: VerifiedTimingLock | None,
    timeline_validation: TimelineValidation,
) -> dict[str, object]:
    blocking_findings: list[str] = []
    if verified_lock is None:
        blocking_findings.append("HUMAN_TIMING_LOCK_REQUIRED")
    if timeline_validation.status == "BLOCKED":
        blocking_findings.append("TIMELINE_STRUCTURE_BLOCKED")

    final_timing_end = verified_lock.timing[-1].end if verified_lock else None
    if final_timing_end is not None and final_timing_end > audio_duration_seconds:
        blocking_findings.append("TIMELINE_EXCEEDS_AUDIO_DURATION")
    locked_span_count = (
        sum(len(line.highlight_spans) for line in verified_lock.timing)
        if verified_lock
        else 0
    )
    projection_boundaries = (
        [
            boundary
            for line in verified_lock.timing
            for span in line.highlight_spans
            for boundary in (span.start, span.end)
        ]
        if verified_lock
        else []
    )
    maximum_projection_error_ms = max(
        (abs(round(value * 100) / 100 - value) * 1000 for value in projection_boundaries),
        default=0.0,
    )

    return {
        "schema_version": 1,
        "audio_payload_sha256": audio_payload_sha256,
        "audio_duration_seconds": audio_duration_seconds,
        "embedded_lyrics": asdict(inventory),
        "timing_lock_sha256": sha256_file(timing_lock_path) if timing_lock_path else None,
        "gates": {
            "G0_INPUT_IDENTITY": "PASS" if verified_lock else "BLOCKED",
            "G1_USLT_TEXT_IDENTITY": "PASS" if verified_lock else "BLOCKED",
            "G2_TIMELINE_STRUCTURE": (
                "PASS" if timeline_validation.status != "BLOCKED" else "BLOCKED"
            ),
            "G3_EVIDENCE_COMPLETENESS": "PASS" if locked_span_count else "BLOCKED",
            "G4_ACOUSTIC_ALIGNMENT": "HUMAN_LOCK_AUTHORITY_ACOUSTIC_VETO_PENDING",
            "G5_ASS_PROJECTION_PREFLIGHT": (
                "PASS" if maximum_projection_error_ms <= 5.000001 else "BLOCKED"
            ),
        },
        "locked_line_count": len(verified_lock.timing) if verified_lock else 0,
        "locked_span_count": locked_span_count,
        "final_timing_end_seconds": final_timing_end,
        "ass_projection_max_rounding_error_ms": maximum_projection_error_ms,
        "release_decision": (
            "PASS_FOR_REVIEW_RENDER" if not blocking_findings else "BLOCKED"
        ),
        "blocking_findings": blocking_findings,
        "non_claims": [
            "USLT proves canonical text identity but contains no timing truth",
            "Pre-render validation does not replace post-render mux and listening QC",
        ],
    }
