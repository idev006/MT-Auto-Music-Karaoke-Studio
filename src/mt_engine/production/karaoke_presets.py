"""Versioned built-in karaoke visual presets with no timing authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

DEFAULT_FONT_FILE = "THSarabun Bold.ttf"
DEFAULT_FONT_FAMILY = "TH SarabunPSK"


@dataclass(frozen=True, slots=True)
class KaraokeVisualPreset:
    preset_id: str
    group_id: str
    display_name: str
    font_family: str = DEFAULT_FONT_FAMILY
    font_asset_file: str = DEFAULT_FONT_FILE
    font_size: int = 56
    portrait_font_size: int = 108
    minimum_font_size: int = 68
    maximum_lines: int = 2
    safe_width_ratio: float = 0.86
    active_color: str = "&H00FFFFFF"
    inactive_color: str = "&H0000D7FF"
    outline_color: str = "&H00101010"
    background_color: str = "&H80000000"
    bold: bool = True
    italic: bool = False
    border_style: int = 1
    outline_width: float = 4.0
    shadow_depth: float = 1.0
    alignment: int = 2
    margin_left: int = 120
    margin_right: int = 120
    margin_vertical: int = 70
    portrait_margin_vertical: int = 125
    letter_spacing: float = 0.0
    schema_version: int = 1

    @property
    def content_sha256(self) -> str:
        payload = json.dumps(
            asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_primitive(self) -> dict[str, object]:
        return {**asdict(self), "content_sha256": self.content_sha256}

    def font_size_for(self, canvas: tuple[int, int]) -> int:
        return self.portrait_font_size if canvas[1] > canvas[0] else self.font_size

    def margin_vertical_for(self, canvas: tuple[int, int]) -> int:
        return (
            self.portrait_margin_vertical if canvas[1] > canvas[0]
            else self.margin_vertical
        )

    def ass_style(self, canvas: tuple[int, int] = (1920, 1080)) -> str:
        return (
            "Style: Karaoke,"
            f"{self.font_family},{self.font_size_for(canvas)},{self.active_color},"
            f"{self.inactive_color},{self.outline_color},{self.background_color},"
            f"{-1 if self.bold else 0},{-1 if self.italic else 0},0,0,100,100,"
            f"{self.letter_spacing},0,{self.border_style},{self.outline_width},"
            f"{self.shadow_depth},{self.alignment},{self.margin_left},"
            f"{self.margin_right},{self.margin_vertical_for(canvas)},1"
        )


_PRESETS = (
    KaraokeVisualPreset("classic-gold", "classic", "Classic Gold"),
    KaraokeVisualPreset(
        "classic-blue", "classic", "Classic Blue",
        active_color="&H00FFFFFF", inactive_color="&H00FFB060",
    ),
    KaraokeVisualPreset(
        "modern-minimal", "modern", "Modern Minimal", font_size=52,
        inactive_color="&H00D8D8D8", outline_width=2.0, shadow_depth=2.0,
        margin_vertical=92,
    ),
    KaraokeVisualPreset(
        "glass-caption", "modern", "Glass Caption", font_size=52,
        inactive_color="&H00F0F0F0", background_color="&H50000000",
        border_style=3, outline_width=8.0, shadow_depth=0.0, margin_vertical=88,
    ),
    KaraokeVisualPreset(
        "neon-pink", "neon", "Neon Pink", active_color="&H00FFFFFF",
        inactive_color="&H00FF66FF", outline_color="&H00600060",
        outline_width=5.0, shadow_depth=2.0,
    ),
    KaraokeVisualPreset(
        "neon-blue", "neon", "Neon Blue", active_color="&H00FFFFFF",
        inactive_color="&H00FFD060", outline_color="&H00603000",
        outline_width=5.0, shadow_depth=2.0,
    ),
    KaraokeVisualPreset(
        "romantic-rose", "romantic", "Romantic Rose", font_size=58,
        portrait_font_size=116, minimum_font_size=80,
        active_color="&H00FFFFFF", inactive_color="&H00B8A0FF",
        outline_color="&H00402050", outline_width=5.0, shadow_depth=3.0,
        portrait_margin_vertical=145,
    ),
    KaraokeVisualPreset(
        "sunset-love", "romantic", "Sunset Love", font_size=58,
        portrait_font_size=116, minimum_font_size=80,
        active_color="&H00FFFFFF", inactive_color="&H0060B8FF",
        outline_color="&H00302030", shadow_depth=2.0,
    ),
    KaraokeVisualPreset(
        "candy-pop", "fun", "Candy Pop", font_size=62,
        portrait_font_size=122, minimum_font_size=84,
        inactive_color="&H0080FFFF", outline_color="&H00802080",
        outline_width=5.0, letter_spacing=1.0,
    ),
    KaraokeVisualPreset(
        "festival-bold", "fun", "Festival Bold", font_size=66,
        portrait_font_size=128, minimum_font_size=88,
        inactive_color="&H0000FFFF", outline_color="&H00000000",
        outline_width=6.0, shadow_depth=3.0,
    ),
    KaraokeVisualPreset(
        "maximum-contrast", "accessible", "Maximum Contrast", font_size=68,
        portrait_font_size=128, minimum_font_size=90,
        inactive_color="&H0000FFFF", outline_color="&H00000000",
        outline_width=7.0, shadow_depth=0.0, margin_vertical=84,
    ),
    KaraokeVisualPreset(
        "dark-caption-bar", "accessible", "Dark Caption Bar", font_size=62,
        portrait_font_size=118, minimum_font_size=84,
        inactive_color="&H00FFFFFF", background_color="&H30000000",
        border_style=3, outline_width=12.0, shadow_depth=0.0, margin_vertical=78,
    ),
)

PRESET_CATALOG = {preset.preset_id: preset for preset in _PRESETS}
DEFAULT_PRESET_ID = "classic-gold"


def get_karaoke_preset(preset_id: str) -> KaraokeVisualPreset:
    try:
        return PRESET_CATALOG[preset_id]
    except KeyError as error:
        choices = ", ".join(PRESET_CATALOG)
        raise ValueError(f"Unknown karaoke preset {preset_id!r}; choose one of: {choices}") from error


def list_karaoke_presets() -> tuple[dict[str, object], ...]:
    return tuple(preset.to_primitive() for preset in _PRESETS)
