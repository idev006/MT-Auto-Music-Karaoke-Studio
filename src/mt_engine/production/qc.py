"""Evidence-first karaoke frame sampling and alignment quality checks."""

from __future__ import annotations

import statistics
import subprocess
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image

from .lyrics import TimedLine, TranscriptSegment


@dataclass(frozen=True, slots=True)
class AlignmentCheck:
    line_index: int
    timestamp: float
    expected_text: str
    asr_text: str | None
    similarity: float
    has_overlapping_asr_evidence: bool
    status: str


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def build_alignment_checks(
    timing: tuple[TimedLine, ...], transcript: tuple[TranscriptSegment, ...]
) -> tuple[AlignmentCheck, ...]:
    checks = []
    for index, line in enumerate(timing):
        overlapping = [
            segment
            for segment in transcript
            if segment.start < line.end and segment.end > line.start
        ]
        evidence = " ".join(segment.text for segment in overlapping).strip()
        similarity = (
            SequenceMatcher(
                None, _normalize(line.text), _normalize(evidence), autojunk=False
            ).ratio()
            if evidence
            else 0.0
        )
        checks.append(
            AlignmentCheck(
                line_index=index,
                timestamp=(line.start + line.end) / 2,
                expected_text=line.text,
                asr_text=evidence or None,
                similarity=round(similarity, 4),
                has_overlapping_asr_evidence=bool(overlapping),
                status="PASS" if overlapping and similarity >= 0.24 else "REVIEW_REQUIRED",
            )
        )
    return tuple(checks)


def build_timing_diagnostics(
    timing: tuple[TimedLine, ...],
    transcript: tuple[TranscriptSegment, ...],
    *,
    audio_duration: float,
) -> dict[str, object]:
    """Summarize evidence quality without claiming synchronization accuracy."""
    checks = build_alignment_checks(timing, transcript)
    durations = [line.end - line.start for line in timing]
    rates = [
        sum(character.isalnum() for character in line.text) / duration
        if duration > 0
        else float("inf")
        for line, duration in zip(timing, durations, strict=True)
    ]
    timestamp_tokens = [word for segment in transcript for word in segment.words]
    asr_window = transcript[-1].end - transcript[0].start if transcript else 0.0
    single_character_tokens = sum(len(word.text) == 1 for word in timestamp_tokens)
    return {
        "schema_version": 1,
        "scope": "diagnostic_evidence_not_sync_certification",
        "audio_duration_seconds": audio_duration,
        "asr_window_seconds": asr_window,
        "asr_window_ratio": round(asr_window / audio_duration, 4) if audio_duration else 0.0,
        "transcript_segment_count": len(transcript),
        "timestamp_token_count": len(timestamp_tokens),
        "single_character_timestamp_token_ratio": (
            round(single_character_tokens / len(timestamp_tokens), 4)
            if timestamp_tokens
            else 0.0
        ),
        "line_count": len(timing),
        "lines_with_progressive_spans": sum(bool(line.highlight_spans) for line in timing),
        "lines_without_progressive_spans": sum(not line.highlight_spans for line in timing),
        "alignment_pass_count": sum(check.status == "PASS" for check in checks),
        "alignment_review_count": sum(check.status != "PASS" for check in checks),
        "duration_seconds": {
            "minimum": min(durations) if durations else None,
            "median": statistics.median(durations) if durations else None,
            "maximum": max(durations) if durations else None,
        },
        "normalized_character_rate_per_second": {
            "median": statistics.median(rates) if rates else None,
            "maximum": max(rates) if rates else None,
        },
        "suspect_initial_segment": (
            {
                "start": transcript[0].start,
                "end": transcript[0].end,
                "text": transcript[0].text,
                "duration_seconds": transcript[0].end - transcript[0].start,
            }
            if transcript and transcript[0].start <= 0.1 and transcript[0].end >= 10.0
            else None
        ),
        "lowest_similarity_lines": [
            asdict(check)
            for check in sorted(checks, key=lambda item: item.similarity)[:12]
        ],
    }


def select_frame_samples(
    checks: tuple[AlignmentCheck, ...], *, count: int = 12
) -> tuple[AlignmentCheck, ...]:
    if not checks or count <= 0:
        return ()
    count = min(count, len(checks))
    risky_count = count // 2
    risky = sorted(
        checks,
        key=lambda check: (check.status == "PASS", check.similarity, check.line_index),
    )[:risky_count]
    stratified_count = count - risky_count
    stratified = [
        checks[round(position * (len(checks) - 1) / max(1, stratified_count - 1))]
        for position in range(stratified_count)
    ]
    selected = {check.line_index: check for check in risky}
    for check in stratified:
        selected.setdefault(check.line_index, check)
    if len(selected) < count:
        broader_stratified = [
            checks[round(position * (len(checks) - 1) / max(1, count * 2 - 1))]
            for position in range(count * 2)
        ]
        for check in broader_stratified:
            selected.setdefault(check.line_index, check)
            if len(selected) >= count:
                break
    return tuple(sorted(selected.values(), key=lambda check: check.timestamp))


def extract_qc_frames(
    ffmpeg: Path,
    video: Path,
    samples: tuple[AlignmentCheck, ...],
    destination: Path,
) -> tuple[dict[str, object], ...]:
    destination.mkdir(parents=True, exist_ok=True)
    evidence = []
    for sample_number, sample in enumerate(samples, start=1):
        frame = destination / f"sample_{sample_number:02d}_{sample.timestamp:07.2f}s.png"
        subprocess.run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{sample.timestamp:.3f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-y",
                str(frame),
            ],
            check=True,
        )
        with Image.open(frame) as image:
            grayscale = image.convert("L")
            roi = grayscale.crop((0, int(image.height * 0.82), image.width, image.height))
            bright_pixels = sum(1 for value in roi.getdata() if value >= 180)
        evidence.append(
            {
                **asdict(sample),
                "frame": str(frame.name),
                "subtitle_bright_pixels": bright_pixels,
                "subtitle_pixels_present": bright_pixels >= 100,
                "rendered_text_exact_match": "HUMAN_REVIEW_REQUIRED",
            }
        )
    return tuple(evidence)
