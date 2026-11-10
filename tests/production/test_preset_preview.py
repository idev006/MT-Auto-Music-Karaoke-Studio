from pathlib import Path

from PIL import Image

from mt_engine.production import preset_preview


def test_preview_generator_creates_manifest_and_contact_sheet(tmp_path: Path, monkeypatch):
    background = tmp_path / "bg.png"
    Image.new("RGB", (540, 960), "navy").save(background)
    ffmpeg_root = tmp_path / "ffmpeg"
    (ffmpeg_root / "bin").mkdir(parents=True)
    (ffmpeg_root / "bin" / "ffmpeg.exe").write_bytes(b"tool")
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    (fonts / "THSarabun Bold.ttf").write_bytes(b"font")

    def fake_write_ass(_lines, destination, **_kwargs):
        destination.write_text("ASS", encoding="utf-8")
        return ({"font_size": 100, "display_line_count": 2},)

    def fake_render(_ffmpeg, *, image, ass_path, destination, canvas, fonts_dir):
        assert image == background.resolve()
        assert canvas == (1080, 1920)
        assert fonts_dir == fonts.resolve()
        assert ass_path.is_file()
        Image.new("RGB", canvas, "navy").save(destination)

    monkeypatch.setattr(preset_preview, "render_ass_preview", fake_render)
    monkeypatch.setattr(preset_preview, "write_ass", fake_write_ass)

    result = preset_preview.generate_preset_previews(
        background=background,
        output_dir=tmp_path / "preview",
        ffmpeg_root=ffmpeg_root,
        fonts_dir=fonts,
        text="ทดสอบ การแบ่งบรรทัด",
        preset_ids=("classic-gold", "romantic-rose"),
    )

    assert result["preset_count"] == 2
    assert Path(str(result["manifest"])).is_file()
    assert Path(str(result["contact_sheet"])).is_file()
    assert result["previews"][0]["layout"]["font_size"] == 100
