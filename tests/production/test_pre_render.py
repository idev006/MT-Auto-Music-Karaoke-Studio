from pathlib import Path

from mt_engine.production.lyrics import (
    EmbeddedLyricsFrame,
    EmbeddedLyricsInventory,
    HighlightSpan,
    TimedLine,
)
from mt_engine.production.pre_render import build_pre_render_validation_report
from mt_engine.production.timing_domain import validate_timeline
from mt_engine.production.timing_lock import VerifiedTimingLock


def _inventory() -> EmbeddedLyricsInventory:
    frame = EmbeddedLyricsFrame("USLT", "tha", "canonical", "lyrics", 1, 0)
    return EmbeddedLyricsInventory((frame,), (), "lyrics")


def test_complete_lock_passes_for_review_render(tmp_path: Path):
    lock_path = tmp_path / "lock.json"
    lock_path.write_text("{}", encoding="utf-8")
    timing = (
        TimedLine(
            1.0,
            3.0,
            "หนึ่ง",
            (HighlightSpan("หนึ่ง", 1.0, 3.0, False, "human_locked"),),
        ),
    )
    lock = VerifiedTimingLock(timing, "Engineer", "now", "audio", "lyrics")

    report = build_pre_render_validation_report(
        audio_payload_sha256="payload",
        audio_duration_seconds=10.0,
        inventory=_inventory(),
        timing_lock_path=lock_path,
        verified_lock=lock,
        timeline_validation=validate_timeline(
            timing, maximum_normalized_characters_per_second=None
        ),
    )

    assert report["release_decision"] == "PASS_FOR_REVIEW_RENDER"
    assert report["gates"]["G1_USLT_TEXT_IDENTITY"] == "PASS"
    assert report["ass_projection_max_rounding_error_ms"] == 0.0


def test_timing_beyond_audio_duration_blocks_before_render(tmp_path: Path):
    lock_path = tmp_path / "lock.json"
    lock_path.write_text("{}", encoding="utf-8")
    timing = (
        TimedLine(
            9.0,
            11.0,
            "หนึ่ง",
            (HighlightSpan("หนึ่ง", 9.0, 11.0, False, "human_locked"),),
        ),
    )
    lock = VerifiedTimingLock(timing, "Engineer", "now", "audio", "lyrics")

    report = build_pre_render_validation_report(
        audio_payload_sha256="payload",
        audio_duration_seconds=10.0,
        inventory=_inventory(),
        timing_lock_path=lock_path,
        verified_lock=lock,
        timeline_validation=validate_timeline(
            timing, maximum_normalized_characters_per_second=None
        ),
    )

    assert report["release_decision"] == "BLOCKED"
    assert "TIMELINE_EXCEEDS_AUDIO_DURATION" in report["blocking_findings"]
