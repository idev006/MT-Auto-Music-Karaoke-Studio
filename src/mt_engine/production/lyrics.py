"""Lyrics extraction, local transcription evidence and conservative timing proposal."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel
from mutagen.id3 import ID3


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class TimedLine:
    start: float
    end: float
    text: str


def extract_lyrics(mp3_path: Path) -> tuple[str, ...]:
    tags = ID3(mp3_path)
    frames = tags.getall("USLT")
    if not frames:
        raise ValueError("No embedded USLT lyrics were found")
    lines = []
    for raw_line in frames[0].text.splitlines():
        line = raw_line.strip()
        if line and not (line.startswith("[") and line.endswith("]")):
            lines.append(line)
    if not lines:
        raise ValueError("Embedded lyrics contain no displayable lines")
    return tuple(lines)


def transcribe(
    audio_path: Path,
    *,
    model_name: str,
    model_cache: Path,
    cpu_threads: int,
) -> tuple[tuple[TranscriptSegment, ...], dict[str, str | float]]:
    model_cache.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=cpu_threads,
        download_root=str(model_cache),
    )
    segments, info = model.transcribe(
        str(audio_path),
        language="th",
        beam_size=5,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=True,
    )
    materialized = tuple(
        TranscriptSegment(float(segment.start), float(segment.end), segment.text.strip())
        for segment in segments
        if segment.text.strip()
    )
    if not materialized:
        raise RuntimeError("faster-whisper produced no transcript segments")
    return materialized, {
        "model": model_name,
        "language": info.language,
        "language_probability": float(info.language_probability),
        "compute_type": "int8",
    }


def propose_timing(
    lyrics: tuple[str, ...], transcript: tuple[TranscriptSegment, ...]
) -> tuple[TimedLine, ...]:
    """Allocate canonical lyric lines across the ASR-observed vocal window by text weight.

    This produces review-required timing evidence, not an approved alignment claim.
    """
    start = max(0.0, transcript[0].start)
    end = max(start + 0.1, transcript[-1].end)
    weights = [max(1, len("".join(line.split()))) for line in lyrics]
    total_weight = sum(weights)
    duration = end - start
    cursor = start
    timed: list[TimedLine] = []
    for index, (line, weight) in enumerate(zip(lyrics, weights, strict=True)):
        line_end = end if index == len(lyrics) - 1 else cursor + duration * weight / total_weight
        timed.append(TimedLine(cursor, max(cursor + 0.1, line_end), line))
        cursor = line_end
    return tuple(timed)
