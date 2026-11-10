"""Deterministic canvas-aware placement for independent visual blocks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CollisionPolicy(StrEnum):
    STACK_VERTICAL = "STACK_VERTICAL"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class CanvasLayoutContext:
    width: int
    height: int
    safe_left: int = 0
    safe_right: int = 0
    safe_top: int = 0
    safe_bottom: int = 0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Canvas dimensions must be positive")
        if self.safe_left + self.safe_right >= self.width:
            raise ValueError("Horizontal safe margins consume the canvas")
        if self.safe_top + self.safe_bottom >= self.height:
            raise ValueError("Vertical safe margins consume the canvas")


@dataclass(frozen=True, slots=True)
class VirtualBoxSpec:
    box_id: str
    width: int | None
    height: int
    margin_left: int = 0
    margin_right: int = 0
    margin_top: int = 0
    margin_bottom: int = 0
    anchor: str = "bottom-center"
    collision_group: str = "default"
    collision_policy: CollisionPolicy = CollisionPolicy.STACK_VERTICAL
    collision_gap: int = 10
    priority: int = 0


@dataclass(frozen=True, slots=True)
class PlacedVirtualBox:
    box_id: str
    left: int
    top: int
    width: int
    height: int
    collision_group: str

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def overlaps(self, other: PlacedVirtualBox) -> bool:
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )


class LayoutCoordinator:
    """Place all blocks from one immutable canvas snapshot."""

    def __init__(self, context: CanvasLayoutContext) -> None:
        self.context = context

    def place(self, specs: tuple[VirtualBoxSpec, ...]) -> tuple[PlacedVirtualBox, ...]:
        if len({spec.box_id for spec in specs}) != len(specs):
            raise ValueError("Virtual box IDs must be unique")
        ordered = sorted(specs, key=lambda item: (-item.priority, item.box_id))
        placed: list[PlacedVirtualBox] = []
        for spec in ordered:
            candidate = self._initial_placement(spec)
            blockers = [
                other
                for other in placed
                if other.collision_group == spec.collision_group
                and candidate.overlaps(other)
            ]
            if blockers and spec.collision_policy == CollisionPolicy.FAIL:
                raise ValueError(f"Virtual box {spec.box_id!r} overlaps another block")
            while blockers:
                new_bottom = min(other.top for other in blockers) - spec.collision_gap
                candidate = PlacedVirtualBox(
                    candidate.box_id,
                    candidate.left,
                    new_bottom - candidate.height,
                    candidate.width,
                    candidate.height,
                    candidate.collision_group,
                )
                if candidate.top < self.context.safe_top + spec.margin_top:
                    raise ValueError(
                        f"Virtual box {spec.box_id!r} cannot be stacked inside the safe area"
                    )
                blockers = [
                    other
                    for other in placed
                    if other.collision_group == spec.collision_group
                    and candidate.overlaps(other)
                ]
            placed.append(candidate)
        by_id = {item.box_id: item for item in placed}
        return tuple(by_id[spec.box_id] for spec in specs)

    def _initial_placement(self, spec: VirtualBoxSpec) -> PlacedVirtualBox:
        if spec.anchor != "bottom-center":
            raise ValueError(f"Unsupported virtual box anchor: {spec.anchor!r}")
        available_width = (
            self.context.width
            - self.context.safe_left
            - self.context.safe_right
            - spec.margin_left
            - spec.margin_right
        )
        available_height = (
            self.context.height
            - self.context.safe_top
            - self.context.safe_bottom
            - spec.margin_top
            - spec.margin_bottom
        )
        if available_width <= 0 or available_height <= 0:
            raise ValueError(f"Virtual box {spec.box_id!r} has no available canvas area")
        width = min(spec.width or available_width, available_width)
        height = min(spec.height, available_height)
        left_bound = self.context.safe_left + spec.margin_left
        left = left_bound + (available_width - width) // 2
        bottom = self.context.height - self.context.safe_bottom - spec.margin_bottom
        return PlacedVirtualBox(
            spec.box_id,
            left,
            bottom - height,
            width,
            height,
            spec.collision_group,
        )
