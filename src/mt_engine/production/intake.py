"""Strict song-folder discovery for the first end-to-end vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class IntakeError(ValueError):
    """Input assets are missing or ambiguous."""


@dataclass(frozen=True, slots=True)
class SongAssets:
    source_dir: Path
    mp3: Path
    image: Path


def discover_song(source_dir: Path, *, single_image_for_both: bool) -> SongAssets:
    source_dir = source_dir.resolve()
    if not source_dir.is_dir():
        raise IntakeError(f"Source directory does not exist: {source_dir}")
    mp3_files = sorted(source_dir.glob("*.mp3"))
    image_files = sorted(
        path
        for suffix in ("*.png", "*.jpg", "*.jpeg", "*.webp")
        for path in source_dir.glob(suffix)
    )
    if len(mp3_files) != 1:
        raise IntakeError(f"Expected exactly 1 MP3, found {len(mp3_files)}")
    if len(image_files) != 1:
        raise IntakeError(f"Expected exactly 1 image, found {len(image_files)}")
    if not single_image_for_both:
        raise IntakeError(
            "One image cannot be assigned to cover and video background without explicit mapping"
        )
    return SongAssets(source_dir, mp3_files[0].resolve(), image_files[0].resolve())
