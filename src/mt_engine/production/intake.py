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
    cover: Path
    background: Path


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
    if len(image_files) == 1:
        if not single_image_for_both:
            raise IntakeError(
                "One image cannot be assigned to cover and video background without explicit mapping"
            )
        cover = background = image_files[0]
    elif len(image_files) == 2:
        cover_candidates = [path for path in image_files if path.stem.casefold() == "cover"]
        if len(cover_candidates) != 1:
            raise IntakeError(
                "Two-image input requires exactly one file named cover.<extension>"
            )
        cover = cover_candidates[0]
        background = next(path for path in image_files if path != cover)
    else:
        raise IntakeError(f"Expected 1 or 2 images, found {len(image_files)}")
    return SongAssets(
        source_dir,
        mp3_files[0].resolve(),
        cover.resolve(),
        background.resolve(),
    )
