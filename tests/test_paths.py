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

    relocated = tmp_path / "moved folder"
    root.rename(relocated)
    moved = PathManager.detect(source_root=relocated)
    assert moved.data("jobs", "a.json") == relocated / "data" / "jobs" / "a.json"


def test_external_data_mode(tmp_path: Path):
    root = tmp_path / "app"
    root.mkdir()
    manager = PathManager.detect(source_root=root, local_appdata=tmp_path / "user")
    assert manager.data("jobs.db") == tmp_path / "user" / "MT" / "MediaStudio" / "jobs.db"


@pytest.mark.parametrize("part", ["../secret", "/root/override", "x/../../secret"])
def test_path_traversal_rejected(tmp_path: Path, part: str):
    root = tmp_path / "app"
    root.mkdir()
    (root / "portable.flag").touch()
    manager = PathManager.detect(source_root=root)
    with pytest.raises(ValueError):
        manager.data(part)
