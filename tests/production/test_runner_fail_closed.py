import json
from pathlib import Path
from types import SimpleNamespace

from mt_engine.production import runner
from mt_engine.production.intake import SongAssets
from mt_engine.production.lyrics import TimedLine, TranscriptSegment


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
    )

    assert result.state == "BLOCKED_TIMING_VALIDATION"
    assert result.mp4_output is None
    assert not (result.target_dir / "karaoke.mp4").exists()
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["outputs"]["mp4"] is None
    assert manifest["state"] == "BLOCKED_TIMING_VALIDATION"
