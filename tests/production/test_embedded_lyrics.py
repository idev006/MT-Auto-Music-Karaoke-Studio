from pathlib import Path

import pytest
from mutagen.id3 import ID3, SYLT, USLT

from mt_engine.production.lyrics import (
    extract_lyrics,
    inspect_embedded_lyrics,
    resolve_canonical_lyrics,
)


def _tagged_file(path: Path, frames: list[object]) -> Path:
    tags = ID3()
    for frame in frames:
        tags.add(frame)
    tags.save(path)
    return path


def test_inventory_reports_uslt_and_sylt_without_treating_uslt_as_timing(tmp_path: Path):
    path = _tagged_file(
        tmp_path / "song.mp3",
        [
            USLT(encoding=3, lang="tha", desc="canonical", text="หนึ่ง\nสอง"),
            SYLT(
                encoding=3,
                lang="tha",
                format=2,
                type=1,
                desc="candidate",
                text=[("หนึ่ง", 1000), ("สอง", 2000)],
            ),
        ],
    )

    inventory = inspect_embedded_lyrics(path)

    assert inventory.uslt[0].line_count == 2
    assert inventory.uslt[0].timestamp_count == 0
    assert inventory.sylt[0].timestamp_count == 2
    assert extract_lyrics(path) == ("หนึ่ง", "สอง")


def test_conflicting_uslt_frames_fail_closed(tmp_path: Path):
    path = _tagged_file(
        tmp_path / "song.mp3",
        [
            USLT(encoding=3, lang="tha", desc="first", text="หนึ่ง\nสอง"),
            USLT(encoding=3, lang="eng", desc="other", text="different lyrics"),
        ],
    )

    with pytest.raises(ValueError, match="conflicting canonical lyrics"):
        inspect_embedded_lyrics(path)


def test_resolver_uses_single_uslt_sidecar_when_primary_has_no_lyrics(tmp_path: Path):
    primary = _tagged_file(tmp_path / "song.mp3", [])
    sidecar = _tagged_file(
        tmp_path / "canonical.mp3--",
        [USLT(encoding=3, lang="tha", desc="canonical", text="หนึ่ง\nสอง")],
    )

    resolved = resolve_canonical_lyrics(tmp_path, primary)

    assert resolved.lines == ("หนึ่ง", "สอง")
    assert resolved.source_path == sidecar
    assert resolved.source_kind == "SIDECAR_MP3_USLT"


def test_resolver_rejects_ambiguous_uslt_sidecars(tmp_path: Path):
    primary = _tagged_file(tmp_path / "song.mp3", [])
    _tagged_file(
        tmp_path / "first.mp3--",
        [USLT(encoding=3, lang="tha", desc="canonical", text="หนึ่ง")],
    )
    _tagged_file(
        tmp_path / "second.mp3--",
        [USLT(encoding=3, lang="tha", desc="canonical", text="สอง")],
    )

    with pytest.raises(ValueError, match="Multiple canonical lyric sidecars"):
        resolve_canonical_lyrics(tmp_path, primary)
