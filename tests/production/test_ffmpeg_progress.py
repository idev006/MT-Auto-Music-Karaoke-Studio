import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from mt_engine.production import media


class FakeProcess:
    def __init__(self, output: str) -> None:
        self.stdout = io.StringIO(output)
        self.stderr = io.StringIO("")
        self.terminated = False
        self.killed = False
        self._finished = False

    def wait(self, timeout=None):
        self._finished = True
        return 0

    def poll(self):
        return 0 if self._finished else None

    def terminate(self):
        self.terminated = True
        self._finished = True

    def kill(self):
        self.killed = True
        self._finished = True


def test_ffmpeg_machine_progress_is_forwarded_as_fraction(tmp_path: Path, monkeypatch):
    process = FakeProcess(
        "frame=75\nfps=30.00\nspeed=1.25x\nout_time=00:00:02.500000\n"
        "progress=continue\nframe=300\nfps=30.00\nspeed=1.50x\n"
        "out_time=00:00:10.000000\nprogress=end\n"
    )
    run_calls = 0

    def fake_run(command, **kwargs):
        nonlocal run_calls
        run_calls += 1
        if "default=noprint_wrappers=1:nokey=1" in command:
            return SimpleNamespace(stdout="10.0\n")
        if "json" in command:
            return SimpleNamespace(stdout='{"streams": [], "format": {}}')
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    monkeypatch.setattr(media.subprocess, "Popen", lambda *args, **kwargs: process)
    progress: list[tuple[float, str, dict[str, str]]] = []

    result = media.run_ffmpeg_render(
        tmp_path / "ffmpeg.exe",
        tmp_path / "ffprobe.exe",
        image=tmp_path / "background.png",
        audio=tmp_path / "song.mp3",
        ass_path=tmp_path / "karaoke.ass",
        destination=tmp_path / "karaoke.mp4",
        preset="veryfast",
        canvas=(1920, 1080),
        progress_callback=lambda fraction, detail, metrics: progress.append(
            (fraction, detail, dict(metrics))
        ),
    )

    assert result == {"streams": [], "format": {}}
    assert [item[:2] for item in progress] == [
        (0.25, "FFmpeg render 25%"),
        (1.0, "FFmpeg render 100%"),
    ]
    assert progress[0][2]["frame"] == "75"
    assert progress[0][2]["fps"] == "30.00"
    assert progress[1][2]["speed"] == "1.50x"
    assert progress[1][2]["progress"] == "end"
    assert run_calls == 3


def test_ffmpeg_is_terminated_when_progress_consumer_cancels(tmp_path: Path, monkeypatch):
    process = FakeProcess("out_time=00:00:01.000000\nprogress=continue\n")
    monkeypatch.setattr(
        media.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="10.0\n"),
    )
    monkeypatch.setattr(media.subprocess, "Popen", lambda *args, **kwargs: process)

    with pytest.raises(RuntimeError, match="cancel"):
        media.run_ffmpeg_render(
            tmp_path / "ffmpeg.exe",
            tmp_path / "ffprobe.exe",
            image=tmp_path / "background.png",
            audio=tmp_path / "song.mp3",
            ass_path=tmp_path / "karaoke.ass",
            destination=tmp_path / "karaoke.mp4",
            preset="veryfast",
            canvas=(1920, 1080),
            progress_callback=lambda *_args: (_ for _ in ()).throw(RuntimeError("cancel")),
        )

    assert process.terminated
    assert not process.killed


def test_ffmpeg_non_timestamp_final_progress_does_not_fail(tmp_path: Path, monkeypatch):
    process = FakeProcess(
        "frame=75\nout_time=00:00:02.500000\nprogress=continue\n"
        "frame=300\nout_time=N/A\nprogress=end\n"
    )

    def fake_run(command, **kwargs):
        if "default=noprint_wrappers=1:nokey=1" in command:
            return SimpleNamespace(stdout="10.0\n")
        if "json" in command:
            return SimpleNamespace(stdout='{"streams": [], "format": {}}')
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(media.subprocess, "run", fake_run)
    monkeypatch.setattr(media.subprocess, "Popen", lambda *args, **kwargs: process)
    fractions: list[float] = []

    media.run_ffmpeg_render(
        tmp_path / "ffmpeg.exe",
        tmp_path / "ffprobe.exe",
        image=tmp_path / "background.png",
        audio=tmp_path / "song.mp3",
        ass_path=tmp_path / "karaoke.ass",
        destination=tmp_path / "karaoke.mp4",
        preset="veryfast",
        canvas=(1920, 1080),
        progress_callback=lambda fraction, *_args: fractions.append(fraction),
    )

    assert fractions == [0.25, 1.0]
