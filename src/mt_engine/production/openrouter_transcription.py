"""Budgeted OpenRouter speech-to-text adapter used as alignment evidence."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen

from .lyrics import TranscriptSegment, TranscriptWord
from .openrouter_config import OpenRouterConfig, OpenRouterSpendLedger


def transcribe_openrouter(
    config: OpenRouterConfig,
    ledger: OpenRouterSpendLedger,
    audio_path: Path,
    *,
    language: str = "th",
) -> tuple[tuple[TranscriptSegment, ...], dict[str, object]]:
    if not ledger.can_start(config.request_cost_guard_usd):
        raise RuntimeError("OpenRouter request blocked by the per-song budget guard")
    audio_bytes = audio_path.read_bytes()
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise ValueError("OpenRouter transcription input exceeds the 25 MiB safe limit")
    audio_format = audio_path.suffix.lower().lstrip(".")
    if audio_format not in {"mp3", "wav", "flac", "m4a", "ogg", "webm", "aac"}:
        raise ValueError(f"Unsupported OpenRouter transcription format: {audio_format}")
    payload = {
        "model": config.transcription_model,
        "input_audio": {
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "format": audio_format,
        },
        "language": language,
        "response_format": "verbose_json",
        "timestamp_granularities": ["word", "segment"],
    }
    request = Request(
        f"{config.base_url}/audio/transcriptions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "X-Title": config.app_name,
        },
        method="POST",
    )
    with urlopen(request, timeout=config.timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    cost = float((body.get("usage") or {}).get("cost") or 0.0)
    ledger.record(
        operation="transcription",
        model=config.transcription_model,
        cost_usd=cost,
    )
    raw_words = body.get("words") or []
    segments = []
    for raw_segment in body.get("segments") or []:
        start = float(raw_segment["start"])
        end = float(raw_segment["end"])
        words = tuple(
            TranscriptWord(
                float(word["start"]),
                float(word["end"]),
                str(word.get("word") or word.get("text") or "").strip(),
                float(word.get("probability", 0.0)),
            )
            for word in raw_words
            if float(word["start"]) < end
            and float(word["end"]) > start
            and str(word.get("word") or word.get("text") or "").strip()
        )
        text = str(raw_segment.get("text") or "").strip()
        if text:
            segments.append(TranscriptSegment(start, end, text, words))
    if not segments:
        raise RuntimeError("OpenRouter transcription returned no timestamped segments")
    return tuple(segments), {
        "provider": "openrouter",
        "model": config.transcription_model,
        "language": body.get("language", language),
        "duration": body.get("duration"),
        "cost_usd": cost,
    }
