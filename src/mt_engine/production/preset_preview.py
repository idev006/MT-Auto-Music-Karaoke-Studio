"""Fast PNG previews for the production karaoke preset renderer."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .karaoke_presets import PRESET_CATALOG, get_karaoke_preset
from .lyrics import TimedLine
from .media import render_ass_preview, sha256_file, video_canvas, write_ass


def generate_preset_previews(
    *,
    background: Path,
    output_dir: Path,
    ffmpeg_root: Path,
    fonts_dir: Path,
    text: str,
    preset_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    background = background.resolve()
    fonts_dir = fonts_dir.resolve()
    ffmpeg = (ffmpeg_root / "bin" / "ffmpeg.exe").resolve()
    if not background.is_file():
        raise FileNotFoundError(f"Preview background was not found: {background}")
    if not ffmpeg.is_file():
        raise FileNotFoundError(f"FFmpeg was not found: {ffmpeg}")
    selected_ids = preset_ids or tuple(PRESET_CATALOG)
    selected = tuple(get_karaoke_preset(preset_id) for preset_id in selected_ids)
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas = video_canvas(background)
    entries = []
    for preset in selected:
        ass_path = output_dir / f"{preset.preset_id}.ass"
        png_path = output_dir / f"{preset.preset_id}.png"
        font_asset = fonts_dir / preset.font_asset_file
        layout = write_ass(
            (TimedLine(0.0, 10.0, text),),
            ass_path,
            canvas=canvas,
            progressive=False,
            visual_preset=preset,
            font_path=font_asset,
        )
        render_ass_preview(
            ffmpeg,
            image=background,
            ass_path=ass_path,
            destination=png_path,
            canvas=canvas,
            fonts_dir=fonts_dir,
        )
        entries.append(
            {
                "preset_id": preset.preset_id,
                "group_id": preset.group_id,
                "display_name": preset.display_name,
                "preset_sha256": preset.content_sha256,
                "font_asset": preset.font_asset_file,
                "font_sha256": sha256_file(font_asset),
                "ass": ass_path.name,
                "png": png_path.name,
                "png_sha256": sha256_file(png_path),
                "layout": layout[0],
            }
        )
    contact_sheet = _contact_sheet(output_dir, entries, canvas)
    manifest = {
        "schema_version": 1,
        "background": str(background),
        "background_sha256": sha256_file(background),
        "canvas": list(canvas),
        "text": text,
        "preset_count": len(entries),
        "previews": entries,
        "contact_sheet": contact_sheet.name,
        "contact_sheet_sha256": sha256_file(contact_sheet),
    }
    manifest_path = output_dir / "preview_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {**manifest, "manifest": str(manifest_path), "contact_sheet": str(contact_sheet)}


def _contact_sheet(
    output_dir: Path,
    entries: list[dict[str, object]],
    canvas: tuple[int, int],
) -> Path:
    columns = 3
    thumb_width = 270
    thumb_height = round(thumb_width * canvas[1] / canvas[0])
    label_height = 34
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "#111111")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default(size=16)
    for index, entry in enumerate(entries):
        with Image.open(output_dir / str(entry["png"])) as preview:
            thumbnail = preview.convert("RGB").resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(thumbnail, (x, y))
        draw.text((x + 8, y + thumb_height + 7), str(entry["preset_id"]), fill="white", font=label_font)
    destination = output_dir / "contact-sheet.png"
    sheet.save(destination)
    return destination
