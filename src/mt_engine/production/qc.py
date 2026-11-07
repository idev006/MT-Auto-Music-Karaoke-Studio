"""Evidence-first karaoke frame sampling and alignment quality checks."""

from __future__ import annotations

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
    stratified = [
        checks[round(position * (len(checks) - 1) / max(1, count - 1))]
        for position in range(count)
    ]
    selected = {check.line_index: check for check in risky}
    for check in stratified:
        if len(selected) >= count:
            break
        selected.setdefault(check.line_index, check)
    if len(selected) < count:
        for check in checks:
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
