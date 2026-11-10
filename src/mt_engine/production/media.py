"""MP3 cover, ASS subtitle, FFmpeg render and media verification adapters."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

from mutagen.id3 import APIC, ID3
from PIL import Image

from .karaoke_presets import DEFAULT_PRESET_ID, KaraokeVisualPreset, get_karaoke_preset
from .lyrics import TimedLine

LANDSCAPE_CANVAS = (1920, 1080)
PORTRAIT_CANVAS = (1080, 1920)


def video_canvas(image: Path) -> tuple[int, int]:
    """Select the default output canvas from the source image orientation."""
    with Image.open(image) as opened:
        width, height = opened.size
    return PORTRAIT_CANVAS if height > width else LANDSCAPE_CANVAS


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mp3_audio_payload_hash(path: Path) -> str:
    data = path.read_bytes()
    offset = 0
    if data.startswith(b"ID3") and len(data) >= 10:
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        offset = 10 + size + (10 if data[5] & 0x10 else 0)
    end = len(data) - 128 if len(data) >= 128 and data[-128:-125] == b"TAG" else len(data)
    return hashlib.sha256(data[offset:end]).hexdigest()


def embed_cover(source_mp3: Path, image: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_mp3, destination)
    tags = ID3(destination)
    tags.delall("APIC")
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image.read_bytes()))
    tags.save(destination, v2_version=3)
    readback = ID3(destination).getall("APIC")
    return {
        "apic_count": len(readback),
        "cover_sha256": hashlib.sha256(readback[0].data).hexdigest() if readback else None,
        "source_audio_payload_sha256": mp3_audio_payload_hash(source_mp3),
        "output_audio_payload_sha256": mp3_audio_payload_hash(destination),
    }


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def _visible_character_count(text: str) -> int:
    return sum(not unicodedata.combining(character) and not character.isspace() for character in text)


def _layout_plain_text(
    text: str,
    preset: KaraokeVisualPreset,
    canvas: tuple[int, int],
) -> tuple[str, int]:
    """Create display-only wrapping/shrinking without mutating canonical text."""
    width, _height = canvas
    preferred_size = preset.font_size_for(canvas)
    safe_width = width * preset.safe_width_ratio

    def capacity(size: int) -> int:
        return max(1, int(safe_width / (size * 0.56)))

    visible_count = _visible_character_count(text)
    if visible_count <= capacity(preferred_size):
        return text, preferred_size

    if preset.maximum_lines >= 2:
        boundaries = [index for index, character in enumerate(text) if character.isspace()]
        if boundaries:
            midpoint = len(text) / 2
            for split in sorted(boundaries, key=lambda index: abs(index - midpoint)):
                left, right = text[:split].rstrip(), text[split + 1 :].lstrip()
                if left and right and max(
                    _visible_character_count(left), _visible_character_count(right)
                ) <= capacity(preferred_size):
                    return f"{left}\n{right}", preferred_size

    fitted_size = max(
        preset.minimum_font_size,
        int(safe_width / (max(1, visible_count) * 0.56)),
    )
    return text, min(preferred_size, fitted_size)


def write_ass(
    lines: tuple[TimedLine, ...],
    destination: Path,
    *,
    canvas: tuple[int, int] = LANDSCAPE_CANVAS,
    progressive: bool = True,
    visual_preset: str | KaraokeVisualPreset = DEFAULT_PRESET_ID,
) -> None:
    width, height = canvas
    selected_preset = (
        get_karaoke_preset(visual_preset)
        if isinstance(visual_preset, str)
        else visual_preset
    )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
{selected_preset.ass_style(canvas)}

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    for line in lines:
        if progressive and line.highlight_spans:
            text = "".join(
                f"{{\\kf{max(1, round((span.end - span.start) * 100))}}}"
                f"{_ass_escape(span.text)}"
                for span in line.highlight_spans
            )
        elif progressive:
            duration_cs = max(1, round((line.end - line.start) * 100))
            text = f"{{\\kf{duration_cs}}}{_ass_escape(line.text)}"
        else:
            display_text, display_font_size = _layout_plain_text(
                line.text, selected_preset, canvas
            )
            size_override = (
                f"{{\\fs{display_font_size}}}"
                if display_font_size != selected_preset.font_size_for(canvas)
                else ""
            )
            text = size_override + _ass_escape(display_text)
        events.append(
            f"Dialogue: 0,{_ass_time(line.start)},{_ass_time(line.end)},Karaoke,,0,0,0,,"
            f"{text}"
        )
    destination.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")


def run_ffmpeg_render(
    ffmpeg: Path,
    ffprobe: Path,
    *,
    image: Path,
    audio: Path,
    ass_path: Path,
    destination: Path,
    preset: str,
    canvas: tuple[int, int] | None = None,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = canvas or video_canvas(image)
    filtergraph = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,ass={ass_path.name}[v]"
    )
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(image),
        "-i",
        str(audio),
        "-filter_complex",
        filtergraph,
        "-map",
        "[v]",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    subprocess.run(command, cwd=ass_path.parent, check=True)
    subprocess.run(
        [str(ffmpeg), "-v", "error", "-i", str(destination), "-f", "null", "-"],
        check=True,
    )
    probe = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,pix_fmt",
            "-of",
            "json",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(probe.stdout)
