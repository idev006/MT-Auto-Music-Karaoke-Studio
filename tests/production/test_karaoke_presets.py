import json
import re
from pathlib import Path

import pytest

from mt_engine.cli import main
from mt_engine.production.karaoke_presets import (
    DEFAULT_PRESET_ID,
    PRESET_CATALOG,
    get_karaoke_preset,
    list_karaoke_presets,
)
from mt_engine.production.lyrics import TimedLine
from mt_engine.production.media import PORTRAIT_CANVAS, write_ass


def test_builtin_catalog_has_multiple_groups_and_presets():
    presets = list_karaoke_presets()

    assert len(presets) == 12
    assert len({item["group_id"] for item in presets}) == 6
    assert len({item["preset_id"] for item in presets}) == len(presets)
    assert len({item["content_sha256"] for item in presets}) == len(presets)
    assert DEFAULT_PRESET_ID in PRESET_CATALOG
    assert all(item["font_asset_file"] == "THSarabun Bold.ttf" for item in presets)
    assert all(item["font_family"] == "TH SarabunPSK" for item in presets)
    assert all(str(item["support_box_color"]).startswith("#") for item in presets)
    assert all(0.35 <= float(item["support_box_opacity"]) <= 0.92 for item in presets)


def test_unknown_preset_fails_with_available_choices():
    with pytest.raises(ValueError, match="Unknown karaoke preset"):
        get_karaoke_preset("does-not-exist")


def test_visual_preset_changes_style_without_changing_timing_or_lyrics(tmp_path: Path):
    line = TimedLine(12.34, 17.89, "เนื้อเพลงเดิม")
    classic = tmp_path / "classic.ass"
    romantic = tmp_path / "romantic.ass"

    write_ass((line,), classic, visual_preset="classic-gold", progressive=False)
    write_ass((line,), romantic, visual_preset="romantic-rose", progressive=False)

    classic_text = classic.read_text(encoding="utf-8-sig")
    romantic_text = romantic.read_text(encoding="utf-8-sig")
    classic_event = next(row for row in classic_text.splitlines() if row.startswith("Dialogue: 1,"))
    romantic_event = next(row for row in romantic_text.splitlines() if row.startswith("Dialogue: 1,"))
    assert classic_event == romantic_event
    assert "เนื้อเพลงเดิม" in classic_event
    assert "0:00:12.34,0:00:17.89" in classic_event
    assert classic_text != romantic_text


def test_list_presets_cli_outputs_catalog(capsys):
    assert main(["list-presets"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 12
    assert payload[0]["preset_id"] == "classic-gold"


def test_portrait_romantic_preset_is_large_and_wraps_long_thai_line(tmp_path: Path):
    destination = tmp_path / "portrait.ass"
    line = TimedLine(1.0, 5.0, "ไม่เคยทำให้ฉัน ต้องทุกข์ร้อนใจ")

    write_ass(
        (line,),
        destination,
        canvas=PORTRAIT_CANVAS,
        progressive=False,
        visual_preset="romantic-rose",
    )

    content = destination.read_text(encoding="utf-8-sig")
    assert "Style: Karaoke,TH SarabunPSK,116," in content
    event_size = int(re.search(r"\\fs(\d+)", content).group(1))
    assert 140 < event_size <= 512
    assert "ไม่เคยทำให้ฉัน\\Nต้องทุกข์ร้อนใจ" in content
    assert ",145,1" in content


def test_each_lyric_event_gets_an_independent_maximum_fitting_font_size(tmp_path: Path):
    destination = tmp_path / "independent.ass"
    lines = (
        TimedLine(1.0, 3.0, "รักเธอ"),
        TimedLine(3.0, 6.0, "เนื้อเพลงยาวพอสมควร ต้องลดขนาด"),
    )

    write_ass(
        lines,
        destination,
        canvas=PORTRAIT_CANVAS,
        progressive=False,
        visual_preset="romantic-rose",
    )

    events = [
        row for row in destination.read_text(encoding="utf-8-sig").splitlines()
        if row.startswith("Dialogue: 1,")
    ]
    sizes = [int(re.search(r"\\fs(\d+)", event).group(1)) for event in events]
    assert sizes[0] <= 512
    assert sizes[1] < sizes[0]


def test_each_lyric_event_has_a_synchronized_support_box(tmp_path: Path):
    destination = tmp_path / "support-box.ass"
    evidence = write_ass(
        (TimedLine(1.25, 4.5, "ข้อความคาราโอเกะ"),),
        destination,
        canvas=PORTRAIT_CANVAS,
        progressive=False,
    )

    events = [
        row for row in destination.read_text(encoding="utf-8-sig").splitlines()
        if row.startswith("Dialogue:")
    ]
    assert len(events) == 2
    assert events[0].startswith("Dialogue: 0,0:00:01.25,0:00:04.50")
    assert events[1].startswith("Dialogue: 1,0:00:01.25,0:00:04.50")
    assert "\\p1" in events[0]
    assert evidence[0]["box_width_pixels"] > evidence[0]["text_width_pixels"]
    assert evidence[0]["box_height_pixels"] > evidence[0]["text_height_pixels"]


def test_virtual_box_uses_configurable_pixel_margins_and_padding(tmp_path: Path):
    destination = tmp_path / "virtual-box.ass"
    preset = get_karaoke_preset("classic-gold")

    evidence = write_ass(
        (TimedLine(1.0, 3.0, "ข้อความ"),),
        destination,
        canvas=PORTRAIT_CANVAS,
        progressive=False,
        visual_preset=preset,
    )[0]

    virtual_box = evidence["virtual_box"]
    assert virtual_box["left_pixels"] == 10
    assert virtual_box["width_pixels"] == 1060
    assert virtual_box["height_pixels"] == 460
    assert virtual_box["top_pixels"] == 1450
    assert evidence["safe_width_pixels"] == 996
    assert evidence["safe_height_pixels"] == 412


def test_each_message_selects_its_own_largest_fitting_font(tmp_path: Path):
    destination = tmp_path / "per-message-fit.ass"
    evidence = write_ass(
        (
            TimedLine(1.0, 2.0, "รัก"),
            TimedLine(2.0, 3.0, "เนื้อเพลงที่มีความยาวมากกว่า จึงต้องคำนวณใหม่ทุกครั้ง"),
        ),
        destination,
        canvas=PORTRAIT_CANVAS,
        progressive=False,
    )

    assert evidence[0]["font_size"] <= 512
    assert evidence[1]["font_size"] < evidence[0]["font_size"]
    assert evidence[1]["text_width_pixels"] <= evidence[1]["safe_width_pixels"]
    assert evidence[1]["text_height_pixels"] <= evidence[1]["safe_height_pixels"]


def test_line_measurement_excludes_thai_combining_marks_from_baseline_count(
    tmp_path: Path,
):
    destination = tmp_path / "baseline-count.ass"
    evidence = write_ass(
        (TimedLine(1.0, 2.0, "กิ้ กู"),),
        destination,
        canvas=PORTRAIT_CANVAS,
        progressive=False,
    )[0]

    measurement = evidence["line_measurements"][0]
    assert measurement["baseline_character_count"] == 2
    assert measurement["combining_mark_count"] == 3
    assert measurement["space_count"] == 1
    assert measurement["representative_character"] == "ฒ"
