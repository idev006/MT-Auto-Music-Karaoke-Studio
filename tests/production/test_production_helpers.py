from itertools import pairwise
from pathlib import Path

import pytest
from PIL import Image

from mt_engine.production.intake import IntakeError, discover_song
from mt_engine.production.lyrics import TimedLine, TranscriptSegment, propose_timing
from mt_engine.production.media import LANDSCAPE_CANVAS, PORTRAIT_CANVAS, video_canvas, write_ass
from mt_engine.production.qc import build_alignment_checks, select_frame_samples


def test_discovery_requires_explicit_single_image_dual_role(tmp_path: Path):
    (tmp_path / "song.mp3").write_bytes(b"mp3")
    (tmp_path / "image.png").write_bytes(b"png")

    with pytest.raises(IntakeError, match="explicit mapping"):
        discover_song(tmp_path, single_image_for_both=False)

    assets = discover_song(tmp_path, single_image_for_both=True)
    assert assets.mp3.name == "song.mp3"
    assert assets.image.name == "image.png"


def test_discovery_rejects_ambiguous_mp3s(tmp_path: Path):
    (tmp_path / "one.mp3").write_bytes(b"one")
    (tmp_path / "two.mp3").write_bytes(b"two")
    (tmp_path / "image.jpg").write_bytes(b"image")

    with pytest.raises(IntakeError, match="exactly 1 MP3"):
        discover_song(tmp_path, single_image_for_both=True)


def test_asr_guided_proposal_preserves_canonical_lines_and_vocal_window():
    lyrics = ("บรรทัดแรก", "บรรทัดที่สองยาวกว่า")
    transcript = (
        TranscriptSegment(5.0, 10.0, "บรรทัดแรก"),
        TranscriptSegment(10.0, 20.0, "บรรทัดที่สอง"),
    )

    timing = propose_timing(lyrics, transcript)

    assert tuple(line.text for line in timing) == lyrics
    assert timing[0].start == 5.0
    assert timing[-1].end == 20.0
    assert timing[0].end == timing[1].start


def test_timing_falls_back_when_asr_covers_only_a_short_song_island():
    lyrics = tuple(f"บรรทัด {index}" for index in range(20))
    transcript = (
        TranscriptSegment(107.0, 110.0, "ช่วงสั้น"),
        TranscriptSegment(110.0, 124.0, "กลางเพลง"),
    )

    timing = propose_timing(lyrics, transcript, audio_duration=273.0)

    assert timing[0].start == 10.0
    assert timing[-1].end == 263.0
    assert any(line.start <= 47.0 <= line.end for line in timing)


def test_text_alignment_anchors_combined_lines_and_interpolates_gap():
    lyrics = (
        "เช้าวันนี้ไม่มีเธอเหมือนเคย",
        "ไม่มีใครเอ่ยถามฉันว่าเป็นอย่างไร",
        "หวานหวาน เธอรู้ไหมว่าฉันเหงาใจ",
        "เมื่อไม่มีเธออยู่ใกล้เหมือนวันวาน",
        "ห้องเดิมที่คุ้นเคยยังอยู่ตรงนี้",
        "แต่ไม่มีเธอคนดีอยู่ข้างกัน",
    )
    transcript = (
        TranscriptSegment(15.0, 27.0, lyrics[0] + lyrics[1]),
        TranscriptSegment(30.0, 38.0, lyrics[2]),
        TranscriptSegment(44.0, 51.0, lyrics[4]),
        TranscriptSegment(52.0, 57.0, lyrics[5]),
    )

    timing = propose_timing(lyrics, transcript, audio_duration=70.0)

    assert timing[0].start == 15.0
    assert timing[1].end == 27.0
    assert timing[2].start == 30.0
    assert timing[3].start == 38.0
    assert timing[3].end == 44.0
    assert timing[4].start == 44.0
    assert timing[5].end == 57.0
    assert all(left.end <= right.start for left, right in pairwise(timing))


def test_text_alignment_does_not_overlap_unrecognized_adlib_with_next_anchor():
    lyrics = ("บรรทัดแรก", "หวานหวาน", "ห้องเดิมที่คุ้นเคย")
    transcript = (
        TranscriptSegment(36.0, 44.0, lyrics[0]),
        TranscriptSegment(44.0, 51.0, lyrics[2]),
    )

    timing = propose_timing(lyrics, transcript, audio_duration=60.0)

    assert tuple(line.text for line in timing) == lyrics
    assert timing[0].end <= timing[1].start
    assert timing[1].end <= timing[2].start


def test_ass_generation_escapes_override_syntax(tmp_path: Path):
    timing = propose_timing(
        (r"ข้อความ {อันตราย} \N",),
        (TranscriptSegment(1.0, 3.0, "ข้อความ"),),
    )
    destination = tmp_path / "karaoke.ass"

    write_ass(timing, destination)

    content = destination.read_text(encoding="utf-8-sig")
    assert r"\{อันตราย\}" in content
    assert r"\\N" in content
    assert r"{\kf200}" in content


@pytest.mark.parametrize(
    ("image_size", "expected_canvas"),
    [
        ((800, 1200), PORTRAIT_CANVAS),
        ((1200, 800), LANDSCAPE_CANVAS),
        ((1000, 1000), LANDSCAPE_CANVAS),
    ],
)
def test_video_canvas_follows_image_orientation(
    tmp_path: Path,
    image_size: tuple[int, int],
    expected_canvas: tuple[int, int],
):
    image = tmp_path / "background.png"
    Image.new("RGB", image_size).save(image)

    assert video_canvas(image) == expected_canvas


def test_ass_play_resolution_matches_portrait_canvas(tmp_path: Path):
    destination = tmp_path / "portrait.ass"
    write_ass(
        (propose_timing(("เนื้อเพลง",), (TranscriptSegment(1.0, 3.0, "เนื้อเพลง"),))[0],),
        destination,
        canvas=PORTRAIT_CANVAS,
    )

    content = destination.read_text(encoding="utf-8-sig")
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content


def test_qc_flags_interpolated_line_without_asr_evidence_and_samples_it():
    timing = (
        propose_timing(("บรรทัดตรง",), (TranscriptSegment(10.0, 15.0, "บรรทัดตรง"),))[0],
        propose_timing(("บรรทัดไม่มีหลักฐาน",), (TranscriptSegment(20.0, 25.0, "อื่น"),))[0],
    )
    transcript = (TranscriptSegment(10.0, 15.0, "บรรทัดตรง"),)

    checks = build_alignment_checks(timing, transcript)
    samples = select_frame_samples(checks, count=2)

    assert checks[0].status == "PASS"
    assert checks[1].status == "REVIEW_REQUIRED"
    assert checks[1].has_overlapping_asr_evidence is False
    assert checks[1] in samples


def test_qc_selects_twelve_frames_and_prioritizes_low_confidence():
    timing = tuple(
        TimedLine(index * 5.0, index * 5.0 + 4.0, f"บรรทัด {index}")
        for index in range(20)
    )
    transcript = tuple(
        TranscriptSegment(line.start, line.end, line.text)
        for line in timing
        if line.text != "บรรทัด 9"
    )

    samples = select_frame_samples(build_alignment_checks(timing, transcript), count=12)

    assert len(samples) == 12
    assert any(sample.line_index == 9 for sample in samples)
