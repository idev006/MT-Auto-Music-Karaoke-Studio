"""Deterministic canvas-aware placement for independent visual blocks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CollisionPolicy(StrEnum):
    STACK_VERTICAL = "STACK_VERTICAL"
    FAIL = "FAIL"


class LayoutDirection(StrEnum):
    ABSOLUTE = "ABSOLUTE"
    VERTICAL = "VERTICAL"
    HORIZONTAL = "HORIZONTAL"


class OverflowPolicy(StrEnum):
    FAIL = "FAIL"
    VISIBLE = "VISIBLE"


@dataclass(frozen=True, slots=True)
class Insets:
    left: int = 0
    right: int = 0
    top: int = 0
    bottom: int = 0

    def __post_init__(self) -> None:
        if min(self.left, self.right, self.top, self.bottom) < 0:
            raise ValueError("Insets cannot be negative")


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


@dataclass(frozen=True, slots=True)
class ComposableBlockSpec:
    """A glyph-like block that can also contain child blocks."""

    block_id: str
    parent_id: str | None
    width: int | None
    height: int
    local_x: int = 0
    local_y: int = 0
    margin: Insets = Insets()
    padding: Insets = Insets()
    layout_direction: LayoutDirection = LayoutDirection.ABSOLUTE
    gap: int = 0
    order: int = 0
    overflow: OverflowPolicy = OverflowPolicy.FAIL

    def __post_init__(self) -> None:
        if self.width is not None and self.width <= 0:
            raise ValueError("Block width must be positive or None")
        if self.height <= 0:
            raise ValueError("Block height must be positive")
        if self.gap < 0:
            raise ValueError("Block gap cannot be negative")


@dataclass(frozen=True, slots=True)
class ResolvedBlock:
    block_id: str
    parent_id: str | None
    local_x: int
    local_y: int
    absolute_x: int
    absolute_y: int
    width: int
    height: int
    padding: Insets

    @property
    def right(self) -> int:
        return self.absolute_x + self.width

    @property
    def bottom(self) -> int:
        return self.absolute_y + self.height

    @property
    def content_left(self) -> int:
        return self.absolute_x + self.padding.left

    @property
    def content_top(self) -> int:
        return self.absolute_y + self.padding.top

    @property
    def content_width(self) -> int:
        return self.width - self.padding.left - self.padding.right

    @property
    def content_height(self) -> int:
        return self.height - self.padding.top - self.padding.bottom


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

    def compose(
        self, specs: tuple[ComposableBlockSpec, ...]
    ) -> tuple[ResolvedBlock, ...]:
        """Resolve a nested block tree against the same canvas snapshot."""
        return _BlockTreeResolver(self.context, specs).resolve()

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


class _BlockTreeResolver:
    def __init__(
        self,
        context: CanvasLayoutContext,
        specs: tuple[ComposableBlockSpec, ...],
    ) -> None:
        self.context = context
        self.specs = specs
        self.by_id = {spec.block_id: spec for spec in specs}
        self.children: dict[str | None, list[ComposableBlockSpec]] = {}

    def resolve(self) -> tuple[ResolvedBlock, ...]:
        self._validate_tree()
        for spec in self.specs:
            self.children.setdefault(spec.parent_id, []).append(spec)
        for child_specs in self.children.values():
            child_specs.sort(key=lambda item: (item.order, item.block_id))
        canvas = ResolvedBlock(
            "__canvas__",
            None,
            0,
            0,
            self.context.safe_left,
            self.context.safe_top,
            self.context.width - self.context.safe_left - self.context.safe_right,
            self.context.height - self.context.safe_top - self.context.safe_bottom,
            Insets(),
        )
        resolved: list[ResolvedBlock] = []
        self._resolve_children(None, canvas, resolved)
        by_id = {item.block_id: item for item in resolved}
        return tuple(by_id[spec.block_id] for spec in self.specs)

    def _validate_tree(self) -> None:
        if len(self.by_id) != len(self.specs):
            raise ValueError("Composable block IDs must be unique")
        for spec in self.specs:
            if spec.parent_id is not None and spec.parent_id not in self.by_id:
                raise ValueError(
                    f"Composable block {spec.block_id!r} has missing parent {spec.parent_id!r}"
                )
            if spec.parent_id == spec.block_id:
                raise ValueError(f"Composable block {spec.block_id!r} cannot parent itself")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(block_id: str) -> None:
            if block_id in visiting:
                raise ValueError("Composable block tree contains a parent cycle")
            if block_id in visited:
                return
            visiting.add(block_id)
            parent_id = self.by_id[block_id].parent_id
            if parent_id is not None:
                visit(parent_id)
            visiting.remove(block_id)
            visited.add(block_id)

        for block_id in self.by_id:
            visit(block_id)

    def _resolve_children(
        self,
        parent_id: str | None,
        parent: ResolvedBlock,
        output: list[ResolvedBlock],
    ) -> None:
        parent_spec = self.by_id.get(parent_id) if parent_id is not None else None
        direction = (
            parent_spec.layout_direction
            if parent_spec is not None
            else LayoutDirection.ABSOLUTE
        )
        gap = parent_spec.gap if parent_spec is not None else 0
        cursor_x = parent.content_left
        cursor_y = parent.content_top
        for spec in self.children.get(parent_id, []):
            width = spec.width or (
                parent.content_width - spec.margin.left - spec.margin.right
            )
            if direction == LayoutDirection.VERTICAL:
                absolute_x = parent.content_left + spec.margin.left
                absolute_y = cursor_y + spec.margin.top
                cursor_y = absolute_y + spec.height + spec.margin.bottom + gap
            elif direction == LayoutDirection.HORIZONTAL:
                absolute_x = cursor_x + spec.margin.left
                absolute_y = parent.content_top + spec.margin.top
                cursor_x = absolute_x + width + spec.margin.right + gap
            else:
                absolute_x = parent.content_left + spec.local_x + spec.margin.left
                absolute_y = parent.content_top + spec.local_y + spec.margin.top
            local_x = absolute_x - parent.absolute_x
            local_y = absolute_y - parent.absolute_y
            block = ResolvedBlock(
                spec.block_id,
                spec.parent_id,
                local_x,
                local_y,
                absolute_x,
                absolute_y,
                width,
                spec.height,
                spec.padding,
            )
            if block.content_width <= 0 or block.content_height <= 0:
                raise ValueError(f"Composable block {spec.block_id!r} padding consumes its area")
            if spec.overflow == OverflowPolicy.FAIL and (
                block.absolute_x < parent.content_left
                or block.absolute_y < parent.content_top
                or block.right > parent.content_left + parent.content_width
                or block.bottom > parent.content_top + parent.content_height
            ):
                raise ValueError(
                    f"Composable block {spec.block_id!r} overflows parent content area"
                )
            output.append(block)
            self._resolve_children(spec.block_id, block, output)
