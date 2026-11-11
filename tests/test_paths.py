from pathlib import Path

import pytest

from mt_engine.paths import PathManager


def test_portable_relocation(tmp_path: Path):
    root = tmp_path / "โครงการ เพลง 01"
    root.mkdir()
    (root / "portable.flag").touch()
    original = PathManager.detect(source_root=root)
    assert original.portable
    assert original.data("jobs", "a.json") == root / "data" / "jobs" / "a.json"
    assert original.bundle("assets", "Fonts") == root / "assets" / "Fonts"

    relocated = tmp_path / "moved folder"
    root.rename(relocated)
    moved = PathManager.detect(source_root=relocated)
    assert moved.data("jobs", "a.json") == relocated / "data" / "jobs" / "a.json"


def test_external_data_mode(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    manager = PathManager.detect(source_root=root, local_appdata=tmp_path / "user")
    assert manager.data("jobs.db") == tmp_path / "user" / "MT" / "MediaStudio" / "jobs.db"


def test_model_cache_is_owned_by_application_root(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    manager = PathManager.detect(source_root=root, local_appdata=tmp_path / "user")

    assert manager.model_cache("faster-whisper") == root / "models" / "faster-whisper"


@pytest.mark.parametrize("part", ["../secret", "/root/override", "x/../../secret"])
def test_path_traversal_rejected(tmp_path: Path, part: str):
    root = tmp_path / "app"
    root.mkdir()
    (root / "portable.flag").touch()
    manager = PathManager.detect(source_root=root)
    with pytest.raises(ValueError):
        manager.data(part)


def test_path_manager_validates_external_runtime_roots(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    ffmpeg = tmp_path / "ffmpeg" / "bin"
    ffmpeg.mkdir(parents=True)
    (ffmpeg / "ffmpeg.exe").touch()
    (ffmpeg / "ffprobe.exe").touch()

    assert PathManager.source_folder(source) == source.resolve()
    assert PathManager.output_root(tmp_path / "output").is_dir()
    assert PathManager.ffmpeg_root(ffmpeg.parent) == ffmpeg.parent.resolve()
