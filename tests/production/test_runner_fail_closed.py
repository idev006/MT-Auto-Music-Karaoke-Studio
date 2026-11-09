import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mt_engine.production import runner
from mt_engine.production.intake import SongAssets
from mt_engine.production.lyrics import (
    EmbeddedLyricsFrame,
    EmbeddedLyricsInventory,
    TimedLine,
    TranscriptSegment,
)
from mt_engine.production.media import sha256_file
from mt_engine.production.release import ReleaseSignoffError, release_reviewed_candidate
from mt_engine.production.timing_lock import lyrics_sha256


def _inventory() -> EmbeddedLyricsInventory:
    frame = EmbeddedLyricsFrame("USLT", "tha", "", "lyrics", 1, 0)
    return EmbeddedLyricsInventory((frame,), (), "lyrics")


def test_blocked_timing_never_renders_or_publishes_mp4(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    mp3 = source / "song.mp3"
    cover = source / "cover.png"
    background = source / "background.png"
    mp3.write_bytes(b"audio")
    cover.write_bytes(b"cover")
    background.write_bytes(b"background")
    assets = SongAssets(source, mp3, cover, background)

    ffmpeg_root = tmp_path / "ffmpeg"
    (ffmpeg_root / "bin").mkdir(parents=True)
    (ffmpeg_root / "bin" / "ffmpeg.exe").write_bytes(b"tool")
    (ffmpeg_root / "bin" / "ffprobe.exe").write_bytes(b"tool")

    monkeypatch.setattr(runner, "discover_song", lambda *_args, **_kwargs: assets)
    monkeypatch.setattr(runner, "inspect_embedded_lyrics", lambda _path: _inventory())
    monkeypatch.setattr(runner, "extract_lyrics", lambda _path: ("เนื้อร้องยาวมากเกินเวลา",))
    monkeypatch.setattr(
        runner,
        "transcribe",
        lambda *_args, **_kwargs: (
            (TranscriptSegment(10.0, 10.6, "เนื้อร้อง"),),
            {"model": "fake"},
        ),
    )
    monkeypatch.setattr(
        runner,
        "propose_timing",
        lambda *_args, **_kwargs: (TimedLine(10.0, 10.6, "เนื้อร้องยาวมากเกินเวลา"),),
    )
    monkeypatch.setattr(runner, "MP3", lambda _path: SimpleNamespace(info=SimpleNamespace(length=60.0)))

    def fake_embed(source_path: Path, _cover_path: Path, destination: Path):
        destination.write_bytes(source_path.read_bytes())
        digest = runner.sha256_file(source_path)
        return {
            "source_audio_payload_sha256": digest,
            "output_audio_payload_sha256": digest,
            "cover_sha256": runner.sha256_file(cover),
        }

    monkeypatch.setattr(runner, "embed_cover", fake_embed)

    def unexpected_render(*_args, **_kwargs):
        raise AssertionError("blocked timing must not reach FFmpeg rendering")

    monkeypatch.setattr(runner, "run_ffmpeg_render", unexpected_render)

    result = runner.produce_song(
        source,
        tmp_path / "dest",
        ffmpeg_root=ffmpeg_root,
        accept_unreviewed_timing=True,
        openrouter_mode="off",
    )

    assert result.state == "BLOCKED_TIMING_VALIDATION"
    assert result.mp4_output is None
    assert not (result.target_dir / "karaoke.mp4").exists()
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["outputs"]["mp4"] is None
    assert manifest["state"] == "BLOCKED_TIMING_VALIDATION"


def test_human_locked_timing_bypasses_asr_and_publishes_mp4(
    tmp_path: Path, monkeypatch
):
    source = tmp_path / "source"
    source.mkdir()
    mp3 = source / "song.mp3"
    cover = source / "cover.png"
    background = source / "background.png"
    mp3.write_bytes(b"audio")
    cover.write_bytes(b"cover")
    background.write_bytes(b"background")
    assets = SongAssets(source, mp3, cover, background)
    lyrics = ("หนึ่ง สอง",)

    ffmpeg_root = tmp_path / "ffmpeg"
    (ffmpeg_root / "bin").mkdir(parents=True)
    (ffmpeg_root / "bin" / "ffmpeg.exe").write_bytes(b"tool")
    (ffmpeg_root / "bin" / "ffprobe.exe").write_bytes(b"tool")
    lock_path = tmp_path / "timing-lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "LOCKED",
                "render_mode": "SYLLABLE_PROGRESSIVE",
                "audio_sha256": sha256_file(mp3),
                "lyrics_sha256": lyrics_sha256(lyrics),
                "reviewer": "Sr Sound Engineer",
                "reviewed_at": "2026-11-09T12:00:00+07:00",
                "lines": [
                    {
                        "line_index": 0,
                        "text": "หนึ่ง สอง",
                        "start": 1.0,
                        "end": 3.0,
                        "highlight_spans": [
                            {
                                "text": "หนึ่ง ", "start": 1.0, "end": 2.0,
                                "unit": "THAI_SYLLABLE", "state": "LOCKED",
                            },
                            {
                                "text": "สอง", "start": 2.0, "end": 3.0,
                                "unit": "THAI_SYLLABLE", "state": "LOCKED",
                            },
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(runner, "discover_song", lambda *_args, **_kwargs: assets)
    monkeypatch.setattr(runner, "inspect_embedded_lyrics", lambda _path: _inventory())
    monkeypatch.setattr(runner, "extract_lyrics", lambda _path: lyrics)
    monkeypatch.setattr(
        runner,
        "transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("human lock must bypass ASR")
        ),
    )
    monkeypatch.setattr(
        runner, "MP3", lambda _path: SimpleNamespace(info=SimpleNamespace(length=60.0))
    )

    def fake_embed(source_path: Path, _cover_path: Path, destination: Path):
        destination.write_bytes(source_path.read_bytes())
        digest = runner.sha256_file(source_path)
        return {
            "source_audio_payload_sha256": digest,
            "output_audio_payload_sha256": digest,
            "cover_sha256": runner.sha256_file(cover),
        }

    monkeypatch.setattr(runner, "embed_cover", fake_embed)
    monkeypatch.setattr(runner, "video_canvas", lambda _path: (1920, 1080))

    def fake_render(*_args, destination: Path, **_kwargs):
        destination.write_bytes(b"mp4")
        return {"streams": []}

    monkeypatch.setattr(runner, "run_ffmpeg_render", fake_render)
    monkeypatch.setattr(runner, "extract_qc_frames", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(runner, "inspect_samples", lambda *_args, **_kwargs: {"status": "PASS"})
    monkeypatch.setattr(
        runner,
        "OpenRouterVisionConfig",
        SimpleNamespace(from_file=lambda _path: object()),
    )
    monkeypatch.setattr(runner, "_tool_version", lambda _path: "fake 1.0")

    result = runner.produce_song(
        source,
        tmp_path / "dest",
        ffmpeg_root=ffmpeg_root,
        timing_lock=lock_path,
        openrouter_mode="off",
    )

    assert result.state == "AWAITING_FINAL_LISTENING_QC"
    assert result.mp4_output is None
    assert not (result.target_dir / "karaoke.mp4").exists()
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["state"] == "AWAITING_FINAL_LISTENING_QC"
    candidate = result.target_dir / manifest["outputs"]["review_candidate"]["path"]
    candidate_hash = sha256_file(candidate)
    signoff = tmp_path / "signoff.json"
    signoff.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "SIGNED_OFF",
                "candidate_sha256": candidate_hash,
                "audio_sha256": sha256_file(mp3),
                "lyrics_sha256": lyrics_sha256(lyrics),
                "full_listening_completed": True,
                "signed_by": "Sr Sound Engineer",
                "signed_at": "2026-11-09T13:00:00+07:00",
            }
        ),
        encoding="utf-8",
    )

    release = release_reviewed_candidate(result.target_dir, signoff)

    assert release.state == "RELEASED_VERIFIED"
    assert release.mp4.read_bytes() == b"mp4"


def test_release_rejects_signoff_for_different_candidate(tmp_path: Path):
    target = tmp_path / "target"
    data = target / "production_data"
    data.mkdir(parents=True)
    candidate = data / "review_candidate.mp4"
    candidate.write_bytes(b"candidate")
    (data / "manifest.json").write_text(
        json.dumps(
            {
                "state": "AWAITING_FINAL_LISTENING_QC",
                "outputs": {
                    "review_candidate": {
                        "path": "production_data/review_candidate.mp4",
                        "sha256": sha256_file(candidate),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (data / "timing.json").write_text(
        json.dumps(
            {"human_lock": {"audio_sha256": "audio", "lyrics_sha256": "lyrics"}}
        ),
        encoding="utf-8",
    )
    (data / "qc_report.json").write_text(
        json.dumps({"mp4": {"decode_passed": True}, "source_immutable": True}),
        encoding="utf-8",
    )
    signoff = tmp_path / "signoff.json"
    signoff.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "SIGNED_OFF",
                "candidate_sha256": "different",
                "audio_sha256": "audio",
                "lyrics_sha256": "lyrics",
                "full_listening_completed": True,
                "signed_by": "Engineer",
                "signed_at": "now",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReleaseSignoffError, match="candidate_sha256"):
        release_reviewed_candidate(target, signoff)
