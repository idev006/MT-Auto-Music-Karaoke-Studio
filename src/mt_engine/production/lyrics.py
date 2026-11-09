"""Lyrics extraction, local transcription evidence and conservative timing proposal."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path

from faster_whisper import WhisperModel
from mutagen.id3 import ID3


@dataclass(frozen=True, slots=True)
class TranscriptWord:
    start: float
    end: float
    text: str
    probability: float


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: tuple[TranscriptWord, ...] = ()


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
    canonical_lyrics: tuple[str, ...],
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
        vad_filter=False,
        word_timestamps=True,
        condition_on_previous_text=False,
        initial_prompt=" ".join(canonical_lyrics)[:1000],
    )
    materialized = tuple(
        TranscriptSegment(
            float(segment.start),
            float(segment.end),
            segment.text.strip(),
            tuple(
                TranscriptWord(
                    float(word.start),
                    float(word.end),
                    word.word.strip(),
                    float(word.probability),
                )
                for word in (segment.words or ())
                if word.word.strip()
            ),
        )
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
    lyrics: tuple[str, ...],
    transcript: tuple[TranscriptSegment, ...],
    *,
    audio_duration: float | None = None,
) -> tuple[TimedLine, ...]:
    """Allocate canonical lyric lines across the ASR-observed vocal window by text weight.

    This produces review-required timing evidence, not an approved alignment claim.
    """
    start = max(0.0, transcript[0].start)
    end = max(start + 0.1, transcript[-1].end)
    observed_duration = end - start
    # Singing over accompaniment can make a small Whisper model return only a
    # short island in the middle of a song. Never compress the entire lyric
    # sheet into that island: fall back to a conservative whole-song window.
    if audio_duration and observed_duration < audio_duration * 0.35:
        edge_padding = min(10.0, audio_duration * 0.05)
        start = edge_padding
        end = max(start + 0.1, audio_duration - edge_padding)
    if not (audio_duration and observed_duration < audio_duration * 0.35):
        aligned = _text_aligned_timing(lyrics, transcript)
        if aligned is not None:
            return aligned
    return _proportional_timing(lyrics, start, end)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _proportional_timing(
    lyrics: tuple[str, ...], start: float, end: float
) -> tuple[TimedLine, ...]:
    weights = [max(1, len(_normalize(line))) for line in lyrics]
    total_weight = sum(weights)
    duration = end - start
    cursor = start
    timed: list[TimedLine] = []
    for index, (line, weight) in enumerate(zip(lyrics, weights, strict=True)):
        line_end = end if index == len(lyrics) - 1 else cursor + duration * weight / total_weight
        timed.append(TimedLine(cursor, max(cursor + 0.1, line_end), line))
        cursor = line_end
    return tuple(timed)


def _text_aligned_timing(
    lyrics: tuple[str, ...], transcript: tuple[TranscriptSegment, ...]
) -> tuple[TimedLine, ...] | None:
    """Anchor canonical lines to monotonic ASR segments, then fill only gaps."""
    anchors: dict[int, tuple[float, float]] = {}
    for start_index, group_size, segment_index in _global_anchor_matches(lyrics, transcript):
        segment = transcript[segment_index]
        group = lyrics[start_index : start_index + group_size]
        weights = [max(1, len(_normalize(line))) for line in group]
        total = sum(weights)
        position = segment.start
        for offset, weight in enumerate(weights):
            line_end = (
                segment.end
                if offset == group_size - 1
                else position + (segment.end - segment.start) * weight / total
            )
            anchors[start_index + offset] = (position, line_end)
            position = line_end

    if len(anchors) < max(2, len(lyrics) // 5):
        return None

    timings: list[TimedLine | None] = [None] * len(lyrics)
    for index, (start, end) in anchors.items():
        timings[index] = TimedLine(start, max(start + 0.1, end), lyrics[index])

    anchor_indices = sorted(anchors)
    boundaries = [-1, *anchor_indices, len(lyrics)]
    for left_index, right_index in pairwise(boundaries):
        missing = list(range(left_index + 1, right_index))
        if not missing:
            continue
        left_time = (
            transcript[0].start if left_index == -1 else anchors[left_index][1]
        )
        right_time = (
            transcript[-1].end if right_index == len(lyrics) else anchors[right_index][0]
        )
        if right_time <= left_time:
            required = 0.5 * len(missing)
            right_time = (
                transcript[-1].end if right_index == len(lyrics) else anchors[right_index][0]
            )
            left_time = max(0.0, right_time - required)
            if left_index >= 0 and timings[left_index] is not None:
                previous = timings[left_index]
                shortened_end = max(previous.start + 0.1, left_time)
                timings[left_index] = TimedLine(previous.start, shortened_end, previous.text)
                left_time = shortened_end
        filled = _proportional_timing(
            tuple(lyrics[index] for index in missing), left_time, right_time
        )
        for index, timing in zip(missing, filled, strict=True):
            timings[index] = timing

    return tuple(timing for timing in timings if timing is not None)


def _global_anchor_matches(
    lyrics: tuple[str, ...], transcript: tuple[TranscriptSegment, ...]
) -> tuple[tuple[int, int, int], ...]:
    """Globally align ordered lyric groups to ordered ASR segments.

    Dynamic programming prevents repeated lyrics from greedily consuming every
    canonical line near the beginning of a song.
    """
    lyric_count = len(lyrics)
    segment_count = len(transcript)
    negative_infinity = float("-inf")
    scores = [
        [negative_infinity] * (segment_count + 1) for _ in range(lyric_count + 1)
    ]
    previous: dict[tuple[int, int], tuple[int, int, tuple[str, int] | None]] = {}
    scores[0][0] = 0.0

    def update(
        next_i: int,
        next_j: int,
        score: float,
        prior_i: int,
        prior_j: int,
        action: tuple[str, int] | None,
    ) -> None:
        if score > scores[next_i][next_j]:
            scores[next_i][next_j] = score
            previous[(next_i, next_j)] = (prior_i, prior_j, action)

    for lyric_index in range(lyric_count + 1):
        for segment_index in range(segment_count + 1):
            current = scores[lyric_index][segment_index]
            if current == negative_infinity:
                continue
            if lyric_index < lyric_count:
                update(
                    lyric_index + 1,
                    segment_index,
                    current - 0.4,
                    lyric_index,
                    segment_index,
                    None,
                )
            if segment_index < segment_count:
                update(
                    lyric_index,
                    segment_index + 1,
                    current - 0.08,
                    lyric_index,
                    segment_index,
                    None,
                )
            if lyric_index < lyric_count and segment_index < segment_count:
                segment_text = _normalize(transcript[segment_index].text)
                for group_size in range(1, min(3, lyric_count - lyric_index) + 1):
                    candidate = _normalize(
                        "".join(lyrics[lyric_index : lyric_index + group_size])
                    )
                    similarity = SequenceMatcher(
                        None, candidate, segment_text, autojunk=False
                    ).ratio()
                    if similarity < 0.24:
                        continue
                    update(
                        lyric_index + group_size,
                        segment_index + 1,
                        current + similarity * 3 + group_size * 0.1,
                        lyric_index,
                        segment_index,
                        ("match", group_size),
                    )

    matches = []
    state = (lyric_count, segment_count)
    while state != (0, 0):
        prior_i, prior_j, action = previous[state]
        if action is not None and action[0] == "match":
            matches.append((prior_i, action[1], prior_j))
        state = (prior_i, prior_j)
    return tuple(reversed(matches))
