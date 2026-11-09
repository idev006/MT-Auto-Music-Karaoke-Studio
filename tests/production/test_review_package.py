from mt_engine.production.lyrics import TimedLine, TranscriptSegment
from mt_engine.production.review_package import build_timing_review_package
from mt_engine.production.timing_domain import validate_timeline


def test_review_package_assigns_stable_repeat_occurrences_and_unknown_state():
    timing = (
        TimedLine(1.0, 3.0, "ฮุก"),
        TimedLine(10.0, 12.0, "ฮุก"),
    )
    transcript = (TranscriptSegment(1.0, 3.0, "ฮุก"),)

    package = build_timing_review_package(
        timing,
        transcript,
        validate_timeline(timing),
        audio_sha256="audio",
        lyrics_sha256="lyrics",
    )

    first, second = package["phrases"]
    assert first["occurrence_index"] == 0
    assert second["occurrence_index"] == 1
    assert first["phrase_id"] != second["phrase_id"]
    assert first["state"] == "PROPOSED"
    assert second["state"] == "UNKNOWN"
    assert package["review_policy"] == (
        "NO_PROGRESSIVE_HIGHLIGHT_WITHOUT_HUMAN_SYLLABLE_LOCK"
    )


def test_review_package_marks_structural_failure_as_conflict():
    timing = (TimedLine(1.0, 1.1, "บรรทัดที่สั้นผิดปกติ"),)

    package = build_timing_review_package(
        timing,
        (),
        validate_timeline(timing),
        audio_sha256="audio",
        lyrics_sha256="lyrics",
    )

    assert package["phrases"][0]["state"] == "CONFLICT"
    assert package["counts"]["CONFLICT"] == 1
