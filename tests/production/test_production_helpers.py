from pathlib import Path

import pytest

from mt_engine.production.intake import IntakeError, discover_song
from mt_engine.production.lyrics import TranscriptSegment, propose_timing
from mt_engine.production.media import write_ass


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
