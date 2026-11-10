"""MP3 cover, ASS subtitle, FFmpeg render and media verification adapters."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import unicodedata
from pathlib import Path
from typing import Any

from mutagen.id3 import APIC, ID3
from PIL import Image, ImageFont

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
    return sum(
        not unicodedata.category(character).startswith("M")
        and not character.isspace()
        for character in text
    )


def _baseline_line_measurement(
    text: str,
    font_path: Path | None,
    font_size: int,
    preset: KaraokeVisualPreset,
) -> dict[str, object]:
    """Expose the ฒ-based estimate without using it as final fit authority."""
    baseline_count = _visible_character_count(text)
    combining_count = sum(
        unicodedata.category(character).startswith("M") for character in text
    )
    space_count = sum(character.isspace() for character in text)
    if font_path is None:
        representative_width = font_size * 0.56
        space_width = font_size * 0.25
        actual_width = baseline_count * font_size * 0.56 + space_count * space_width
        measurement = "fallback_estimate"
    else:
        font = ImageFont.truetype(str(font_path), font_size)
        representative_width = float(font.getlength("ฒ"))
        space_width = float(font.getlength(" "))
        actual_width = float(font.getlength(text))
        _left, actual_top, _right, actual_bottom = font.getbbox(text, anchor="ls")
        _base_left, base_top, _base_right, base_bottom = font.getbbox(
            "ฒ", anchor="ls"
        )
        measurement = "freetype_glyph_advance"
    result = {
        "text": text,
        "baseline_character_count": baseline_count,
        "combining_mark_count": combining_count,
        "space_count": space_count,
        "representative_character": "ฒ",
        "representative_width_pixels": round(representative_width, 2),
        "estimated_width_pixels": round(
            baseline_count * representative_width + space_count * space_width, 2
        ),
        "actual_shaped_width_pixels": round(actual_width, 2),
        "measurement": measurement,
    }
    if font_path is not None:
        upper_extent = max(0, base_top - actual_top)
        base_body_height = base_bottom - base_top
        lower_extent = max(0, actual_bottom - base_bottom)
        decoration_extent = 2 * preset.outline_width + preset.shadow_depth
        result["vertical_zones"] = {
            "baseline_y": 0,
            "actual_top_from_baseline_pixels": actual_top,
            "actual_bottom_from_baseline_pixels": actual_bottom,
            "upper_mark_extent_pixels": upper_extent,
            "base_body_height_pixels": base_body_height,
            "lower_mark_extent_pixels": lower_extent,
            "ink_height_pixels": actual_bottom - actual_top,
            "decoration_extent_pixels": decoration_extent,
            "rendered_height_pixels": actual_bottom - actual_top + decoration_extent,
        }
    return result


def _progressive_text(
    line: TimedLine,
    display_text: str,
    display_font_size: int,
) -> str:
    """Preserve timing tags while applying the selected visual line break."""
    split_index = None
    if "\n" in display_text:
        first_display_line = display_text.split("\n", 1)[0]
        split_index = len(first_display_line)
    position = 0
    rendered_spans = []
    for span in line.highlight_spans:
        characters = []
        for character in span.text:
            if split_index is not None and position == split_index and character.isspace():
                characters.append(r"\N")
            else:
                characters.append(_ass_escape(character))
            position += 1
        rendered_spans.append(
            f"{{\\kf{max(1, round((span.end - span.start) * 100))}}}"
            + "".join(characters)
        )
    return f"{{\\fs{display_font_size}}}" + "".join(rendered_spans)


def _layout_plain_text(
    text: str,
    preset: KaraokeVisualPreset,
    canvas: tuple[int, int],
    font_path: Path | None = None,
) -> tuple[str, int, float, float]:
    """Maximize each lyric event independently using shaped font measurements."""
    _region, content_block = preset.block_tree_for(canvas)
    safe_width = content_block.width
    allowed_height = content_block.height
    boundaries = [index for index, character in enumerate(text) if character.isspace()]

    def metrics(value: str, size: int) -> tuple[float, float]:
        decoration = 2 * preset.outline_width + preset.shadow_depth
        if font_path is not None:
            font = ImageFont.truetype(str(font_path), size)
            left, top, right, bottom = font.getbbox(value, anchor="ls")
            ink_height = max(1, bottom - top)
            ink_width = max(font.getlength(value), right - left)
            return float(ink_width + decoration), float(ink_height + decoration)
        return (
            _visible_character_count(value) * size * 0.56 + decoration,
            size * 1.15 + decoration,
        )

    maximum_size = preset.maximum_font_size_for(canvas)
    for size in range(maximum_size, preset.minimum_font_size - 1, -1):
        one_width, one_height = metrics(text, size)
        if one_width <= safe_width and one_height <= allowed_height:
            return text, size, one_width, one_height
        if preset.maximum_lines < 2:
            continue
        candidates: list[tuple[float, str, float, float]] = []
        for split in boundaries:
            left, right = text[:split].rstrip(), text[split + 1 :].lstrip()
            if not left or not right:
                continue
            left_width, line_height = metrics(left, size)
            right_width, right_height = metrics(right, size)
            total_height = (
                line_height + right_height + size * preset.inter_line_spacing_ratio
            )
            widest = max(left_width, right_width)
            if widest <= safe_width and total_height <= allowed_height:
                candidates.append(
                    (abs(left_width - right_width), f"{left}\n{right}", widest, total_height)
                )
        if candidates:
            _imbalance, display, widest, total_height = min(candidates)
            return display, size, widest, total_height
    raise ValueError(
        f"Lyric text cannot fit preset {preset.preset_id!r} above minimum font size "
        f"{preset.minimum_font_size}: {text!r}"
    )


def write_ass(
    lines: tuple[TimedLine, ...],
    destination: Path,
    *,
    canvas: tuple[int, int] = LANDSCAPE_CANVAS,
    progressive: bool = True,
    visual_preset: str | KaraokeVisualPreset = DEFAULT_PRESET_ID,
    font_path: Path | None = None,
) -> tuple[dict[str, object], ...]:
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
    layout_evidence = []
    for line_index, line in enumerate(lines):
        display_text, display_font_size, text_width, text_height = _layout_plain_text(
            line.text, selected_preset, canvas, font_path
        )
        if progressive and line.highlight_spans:
            text = _progressive_text(line, display_text, display_font_size)
        elif progressive:
            duration_cs = max(1, round((line.end - line.start) * 100))
            text = (
                f"{{\\fs{display_font_size}}}{{\\kf{duration_cs}}}"
                f"{_ass_escape(display_text)}"
            )
        else:
            size_override = (
                f"{{\\fs{display_font_size}}}"
            )
            text = size_override + _ass_escape(display_text)
        region_block, content_block = selected_preset.block_tree_for(canvas)
        virtual_left = region_block.absolute_x
        virtual_top = region_block.absolute_y
        virtual_width = region_block.width
        virtual_height = region_block.height
        content_width = content_block.width
        content_height = content_block.height
        box_width = min(
            text_width
            + selected_preset.virtual_box_padding_left_pixels
            + selected_preset.virtual_box_padding_right_pixels,
            virtual_width,
        )
        box_height = min(
            text_height
            + selected_preset.virtual_box_padding_top_pixels
            + selected_preset.virtual_box_padding_bottom_pixels,
            virtual_height,
        )
        box_left = virtual_left + (virtual_width - box_width) / 2
        box_top = virtual_top + virtual_height - box_height
        text_anchor_x = virtual_left + virtual_width / 2
        text_anchor_y = (
            virtual_top + virtual_height - selected_preset.virtual_box_padding_bottom_pixels
        )
        text = (
            f"{{\\an2\\pos({text_anchor_x:.1f},{text_anchor_y:.1f})}}" + text
        )
        red = selected_preset.support_box_color[1:3]
        green = selected_preset.support_box_color[3:5]
        blue = selected_preset.support_box_color[5:7]
        ass_box_color = f"&H{blue}{green}{red}&"
        ass_box_alpha = round((1 - selected_preset.support_box_opacity) * 255)
        box_drawing = (
            f"{{\\an7\\pos({box_left:.1f},{box_top:.1f})\\p1\\bord0\\shad0"
            f"\\1c{ass_box_color}\\1a&H{ass_box_alpha:02X}&}}"
            f"m 0 0 l {round(box_width)} 0 l {round(box_width)} {round(box_height)} "
            f"l 0 {round(box_height)}{{\\p0}}"
        )
        layout_evidence.append(
            {
                "line_index": line_index,
                "canonical_text": line.text,
                "display_text": display_text,
                "font_size": display_font_size,
                "display_line_count": display_text.count("\n") + 1,
                "canvas": list(canvas),
                "safe_width_pixels": round(content_width, 2),
                "safe_height_pixels": round(content_height, 2),
                "measurement": "freetype_glyph_advance" if font_path else "fallback_estimate",
                "text_width_pixels": round(text_width, 2),
                "text_height_pixels": round(text_height, 2),
                "box_width_pixels": round(box_width, 2),
                "box_height_pixels": round(box_height, 2),
                "box_left_pixels": round(box_left, 2),
                "box_top_pixels": round(box_top, 2),
                "box_color": selected_preset.support_box_color,
                "box_opacity": selected_preset.support_box_opacity,
                "line_measurements": [
                    _baseline_line_measurement(
                        display_line, font_path, display_font_size, selected_preset
                    )
                    for display_line in display_text.split("\n")
                ],
                "virtual_box": {
                    "left_pixels": virtual_left,
                    "top_pixels": virtual_top,
                    "width_pixels": virtual_width,
                    "height_pixels": virtual_height,
                    "margin_left_pixels": selected_preset.virtual_box_margin_left_pixels,
                    "margin_right_pixels": selected_preset.virtual_box_margin_right_pixels,
                    "margin_bottom_pixels": selected_preset.virtual_box_margin_bottom_pixels,
                    "padding_left_pixels": selected_preset.virtual_box_padding_left_pixels,
                    "padding_right_pixels": selected_preset.virtual_box_padding_right_pixels,
                    "padding_top_pixels": selected_preset.virtual_box_padding_top_pixels,
                    "padding_bottom_pixels": selected_preset.virtual_box_padding_bottom_pixels,
                    "layout_tree": {
                        "region_block_id": region_block.block_id,
                        "content_block_id": content_block.block_id,
                        "content_local_x_pixels": content_block.local_x,
                        "content_local_y_pixels": content_block.local_y,
                        "content_absolute_x_pixels": content_block.absolute_x,
                        "content_absolute_y_pixels": content_block.absolute_y,
                    },
                },
            }
        )
        events.append(
            f"Dialogue: 0,{_ass_time(line.start)},{_ass_time(line.end)},Karaoke,,0,0,0,,"
            f"{box_drawing}"
        )
        events.append(
            f"Dialogue: 1,{_ass_time(line.start)},{_ass_time(line.end)},Karaoke,,0,0,0,,"
            f"{text}"
        )
    destination.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return tuple(layout_evidence)


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
    fonts_dir: Path | None = None,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = canvas or video_canvas(image)
    ass_filter = f"ass={ass_path.name}"
    if fonts_dir is not None:
        resolved_fonts = fonts_dir.resolve()
        if not resolved_fonts.is_dir():
            raise FileNotFoundError(f"ASS fonts directory was not found: {resolved_fonts}")
        relative_fonts = Path(
            os.path.relpath(resolved_fonts, ass_path.parent.resolve())
        ).as_posix()
        ass_filter += f":fontsdir='{relative_fonts}'"
    filtergraph = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,{ass_filter}[v]"
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


def render_ass_preview(
    ffmpeg: Path,
    *,
    image: Path,
    ass_path: Path,
    destination: Path,
    canvas: tuple[int, int],
    fonts_dir: Path,
) -> None:
    """Render one representative PNG through the production libass path."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    width, height = canvas
    resolved_fonts = fonts_dir.resolve()
    if not resolved_fonts.is_dir():
        raise FileNotFoundError(f"ASS fonts directory was not found: {resolved_fonts}")
    relative_fonts = Path(
        os.path.relpath(resolved_fonts, ass_path.parent.resolve())
    ).as_posix()
    filtergraph = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"ass={ass_path.name}:fontsdir='{relative_fonts}'"
    )
    subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image.resolve()),
            "-vf",
            filtergraph,
            "-frames:v",
            "1",
            str(destination.resolve()),
        ],
        cwd=ass_path.parent,
        check=True,
    )
