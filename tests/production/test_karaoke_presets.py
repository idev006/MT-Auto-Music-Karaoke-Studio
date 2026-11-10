import json
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
    classic_event = next(row for row in classic_text.splitlines() if row.startswith("Dialogue:"))
    romantic_event = next(row for row in romantic_text.splitlines() if row.startswith("Dialogue:"))
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
    assert "Style: Karaoke,Tahoma,92," in content
    assert "ไม่เคยทำให้ฉัน\\Nต้องทุกข์ร้อนใจ" in content
    assert ",145,1" in content
