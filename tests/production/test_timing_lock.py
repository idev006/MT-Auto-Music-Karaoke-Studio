import json
from pathlib import Path

import pytest

from mt_engine.production.timing_lock import (
    TimingLockError,
    load_verified_timing_lock,
    lyrics_sha256,
)


def _payload(lyrics: tuple[str, ...], audio_hash: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "state": "LOCKED",
        "render_mode": "SYLLABLE_PROGRESSIVE",
        "audio_sha256": audio_hash,
        "lyrics_sha256": lyrics_sha256(lyrics),
        "reviewer": "Sr Sound Engineer",
        "reviewed_at": "2026-11-09T12:00:00+07:00",
        "lines": [
            {
                "line_index": 0,
                "text": lyrics[0],
                "start": 1.0,
                "end": 3.0,
                "highlight_spans": [
                    {
                        "text": "หนึ่ง ", "start": 1.0, "end": 2.0,
                        "unit": "THAI_SYLLABLE", "state": "LOCKED",
                    },
                    {
                        "text": "สอง", "start": 2.0, "end": 3.0, "sustained": True,
                        "unit": "THAI_SYLLABLE", "state": "LOCKED",
                    },
                ],
            }
        ],
    }


def test_loads_complete_hash_bound_human_timing_lock(tmp_path: Path):
    lyrics = ("หนึ่ง สอง",)
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(_payload(lyrics, "abc"), ensure_ascii=False), encoding="utf-8")

    lock = load_verified_timing_lock(
        path, expected_audio_sha256="abc", expected_lyrics=lyrics
    )

    assert lock.reviewer == "Sr Sound Engineer"
    assert lock.timing[0].highlight_spans[-1].sustained is True
    assert lock.timing[0].highlight_spans[-1].evidence == "human_locked"


def test_rejects_timing_lock_for_different_audio(tmp_path: Path):
    lyrics = ("หนึ่ง สอง",)
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(_payload(lyrics, "old"), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TimingLockError, match="audio hash"):
        load_verified_timing_lock(
            path, expected_audio_sha256="new", expected_lyrics=lyrics
        )


def test_rejects_lock_without_progressive_spans(tmp_path: Path):
    lyrics = ("หนึ่ง สอง",)
    payload = _payload(lyrics, "abc")
    payload["lines"][0]["highlight_spans"] = []
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(TimingLockError, match="requires reviewed progressive spans"):
        load_verified_timing_lock(
            path, expected_audio_sha256="abc", expected_lyrics=lyrics
        )
