"""Versioned built-in karaoke visual presets with no timing authority."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from .layout import (
    CanvasLayoutContext,
    ComposableBlockSpec,
    Insets,
    LayoutCoordinator,
    ResolvedBlock,
    VirtualBoxSpec,
)

DEFAULT_FONT_FILE = "THSarabun Bold.ttf"
DEFAULT_FONT_FAMILY = "TH SarabunPSK"


class LineFontMode(StrEnum):
    UNIFORM = "UNIFORM"
    INDEPENDENT = "INDEPENDENT"


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
    maximum_font_size: int = 260
    portrait_maximum_font_size: int = 512
    maximum_lines: int = 2
    line_font_mode: LineFontMode = LineFontMode.UNIFORM
    virtual_box_width_pixels: int | None = None
    virtual_box_height_pixels: int = 260
    portrait_virtual_box_height_pixels: int = 460
    virtual_box_margin_left_pixels: int = 10
    virtual_box_margin_right_pixels: int = 10
    virtual_box_margin_top_pixels: int = 0
    virtual_box_margin_bottom_pixels: int = 10
    virtual_box_padding_left_pixels: int = 32
    virtual_box_padding_right_pixels: int = 32
    virtual_box_padding_top_pixels: int = 24
    virtual_box_padding_bottom_pixels: int = 24
    support_box_color: str = "#18120A"
    support_box_opacity: float = 0.68
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
    schema_version: int = 3

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

    def maximum_font_size_for(self, canvas: tuple[int, int]) -> int:
        return (
            self.portrait_maximum_font_size
            if canvas[1] > canvas[0]
            else self.maximum_font_size
        )

    def virtual_box_for(self, canvas: tuple[int, int]) -> tuple[int, int, int, int]:
        """Place the box through the shared canvas coordinator."""
        canvas_width, canvas_height = canvas
        requested_height = (
            self.portrait_virtual_box_height_pixels
            if canvas_height > canvas_width
            else self.virtual_box_height_pixels
        )
        placed = LayoutCoordinator(CanvasLayoutContext(*canvas)).place(
            (
                VirtualBoxSpec(
                    box_id="karaoke-primary",
                    width=self.virtual_box_width_pixels,
                    height=requested_height,
                    margin_left=self.virtual_box_margin_left_pixels,
                    margin_right=self.virtual_box_margin_right_pixels,
                    margin_top=self.virtual_box_margin_top_pixels,
                    margin_bottom=self.virtual_box_margin_bottom_pixels,
                    collision_group="bottom-captions",
                    priority=100,
                ),
            )
        )
        box = placed[0]
        return box.left, box.top, box.width, box.height

    def block_tree_for(self, canvas: tuple[int, int]) -> tuple[ResolvedBlock, ResolvedBlock]:
        """Resolve the karaoke region and its text-content child block."""
        left, top, width, height = self.virtual_box_for(canvas)
        content_height = (
            height
            - self.virtual_box_padding_top_pixels
            - self.virtual_box_padding_bottom_pixels
        )
        coordinator = LayoutCoordinator(CanvasLayoutContext(*canvas))
        region, content = coordinator.compose(
            (
                ComposableBlockSpec(
                    "karaoke-region",
                    None,
                    width,
                    height,
                    local_x=left,
                    local_y=top,
                    padding=Insets(
                        self.virtual_box_padding_left_pixels,
                        self.virtual_box_padding_right_pixels,
                        self.virtual_box_padding_top_pixels,
                        self.virtual_box_padding_bottom_pixels,
                    ),
                ),
                ComposableBlockSpec(
                    "karaoke-text-content",
                    "karaoke-region",
                    None,
                    content_height,
                ),
            )
        )
        return region, content

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
        support_box_color="#0B2038",
    ),
    KaraokeVisualPreset(
        "modern-minimal", "modern", "Modern Minimal", font_size=52,
        line_font_mode=LineFontMode.INDEPENDENT,
        inactive_color="&H00D8D8D8", outline_width=2.0, shadow_depth=2.0,
        margin_vertical=92,
        support_box_color="#111827", support_box_opacity=0.48,
    ),
    KaraokeVisualPreset(
        "glass-caption", "modern", "Glass Caption", font_size=52,
        inactive_color="&H00F0F0F0", background_color="&H50000000",
        border_style=1, outline_width=3.0, shadow_depth=0.0, margin_vertical=88,
        support_box_color="#18202A", support_box_opacity=0.42,
    ),
    KaraokeVisualPreset(
        "neon-pink", "neon", "Neon Pink", active_color="&H00FFFFFF",
        inactive_color="&H00FF66FF", outline_color="&H00600060",
        outline_width=5.0, shadow_depth=2.0,
        support_box_color="#220D2B", support_box_opacity=0.72,
    ),
    KaraokeVisualPreset(
        "neon-blue", "neon", "Neon Blue", active_color="&H00FFFFFF",
        inactive_color="&H00FFD060", outline_color="&H00603000",
        outline_width=5.0, shadow_depth=2.0,
        support_box_color="#071D35", support_box_opacity=0.72,
    ),
    KaraokeVisualPreset(
        "romantic-rose", "romantic", "Romantic Rose", font_size=58,
        portrait_font_size=116, minimum_font_size=80,
        active_color="&H00FFFFFF", inactive_color="&H00B8A0FF",
        outline_color="&H00402050", outline_width=5.0, shadow_depth=3.0,
        portrait_margin_vertical=145,
        support_box_color="#301B38", support_box_opacity=0.66,
    ),
    KaraokeVisualPreset(
        "sunset-love", "romantic", "Sunset Love", font_size=58,
        portrait_font_size=116, minimum_font_size=80,
        active_color="&H00FFFFFF", inactive_color="&H0060B8FF",
        outline_color="&H00302030", shadow_depth=2.0,
        support_box_color="#402018", support_box_opacity=0.62,
    ),
    KaraokeVisualPreset(
        "candy-pop", "fun", "Candy Pop", font_size=62,
        portrait_font_size=122, minimum_font_size=84,
        inactive_color="&H0080FFFF", outline_color="&H00802080",
        outline_width=5.0, letter_spacing=1.0,
        support_box_color="#35113C", support_box_opacity=0.64,
    ),
    KaraokeVisualPreset(
        "festival-bold", "fun", "Festival Bold", font_size=66,
        portrait_font_size=128, minimum_font_size=88,
        inactive_color="&H0000FFFF", outline_color="&H00000000",
        outline_width=6.0, shadow_depth=3.0,
        support_box_color="#211300", support_box_opacity=0.70,
    ),
    KaraokeVisualPreset(
        "maximum-contrast", "accessible", "Maximum Contrast", font_size=68,
        portrait_font_size=128, minimum_font_size=90,
        inactive_color="&H0000FFFF", outline_color="&H00000000",
        outline_width=7.0, shadow_depth=0.0, margin_vertical=84,
        support_box_color="#000000", support_box_opacity=0.88,
    ),
    KaraokeVisualPreset(
        "dark-caption-bar", "accessible", "Dark Caption Bar", font_size=62,
        portrait_font_size=118, minimum_font_size=84,
        inactive_color="&H00FFFFFF", background_color="&H30000000",
        border_style=1, outline_width=4.0, shadow_depth=0.0, margin_vertical=78,
        support_box_color="#000000", support_box_opacity=0.82,
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
