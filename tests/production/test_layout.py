import pytest

from mt_engine.production.layout import (
    CanvasLayoutContext,
    CollisionPolicy,
    ComposableBlockSpec,
    Insets,
    LayoutCoordinator,
    LayoutDirection,
    OverflowPolicy,
    VirtualBoxSpec,
)


def test_bottom_center_box_knows_canvas_and_margins():
    coordinator = LayoutCoordinator(CanvasLayoutContext(1080, 1920))

    placed = coordinator.place(
        (
            VirtualBoxSpec(
                "karaoke",
                width=None,
                height=460,
                margin_left=10,
                margin_right=10,
                margin_bottom=10,
            ),
        )
    )[0]

    assert (placed.left, placed.top, placed.width, placed.height) == (10, 1450, 1060, 460)


def test_boxes_in_same_collision_group_stack_without_overlap():
    coordinator = LayoutCoordinator(CanvasLayoutContext(1080, 1920))
    lower, upper = coordinator.place(
        (
            VirtualBoxSpec("current-line", 1000, 220, priority=100, collision_gap=12),
            VirtualBoxSpec("next-line", 1000, 180, priority=50, collision_gap=12),
        )
    )

    assert not lower.overlaps(upper)
    assert upper.bottom == lower.top - 12


def test_fail_policy_rejects_overlap():
    coordinator = LayoutCoordinator(CanvasLayoutContext(1080, 1920))

    with pytest.raises(ValueError, match="overlaps"):
        coordinator.place(
            (
                VirtualBoxSpec("first", 1000, 300, priority=100),
                VirtualBoxSpec(
                    "second",
                    1000,
                    300,
                    priority=50,
                    collision_policy=CollisionPolicy.FAIL,
                ),
            )
        )


def test_nested_blocks_resolve_local_and_absolute_coordinates():
    coordinator = LayoutCoordinator(CanvasLayoutContext(1080, 1920))
    region, current, next_line = coordinator.compose(
        (
            ComposableBlockSpec(
                "karaoke-region",
                None,
                1060,
                460,
                local_x=10,
                local_y=1450,
                padding=Insets(32, 32, 24, 24),
                layout_direction=LayoutDirection.VERTICAL,
                gap=12,
            ),
            ComposableBlockSpec("current", "karaoke-region", None, 180),
            ComposableBlockSpec("next", "karaoke-region", None, 160),
        )
    )

    assert (region.absolute_x, region.absolute_y) == (10, 1450)
    assert (current.absolute_x, current.absolute_y, current.width) == (42, 1474, 996)
    assert next_line.absolute_y == current.bottom + 12
    assert next_line.bottom <= region.absolute_y + region.height - region.padding.bottom


def test_nested_blocks_reject_parent_cycle():
    coordinator = LayoutCoordinator(CanvasLayoutContext(1080, 1920))

    with pytest.raises(ValueError, match="cycle"):
        coordinator.compose(
            (
                ComposableBlockSpec("a", "b", 100, 100),
                ComposableBlockSpec("b", "a", 100, 100),
            )
        )


def test_nested_blocks_fail_closed_on_parent_overflow():
    coordinator = LayoutCoordinator(CanvasLayoutContext(200, 200))

    with pytest.raises(ValueError, match="overflows"):
        coordinator.compose(
            (
                ComposableBlockSpec("parent", None, 100, 100),
                ComposableBlockSpec(
                    "child",
                    "parent",
                    120,
                    50,
                    overflow=OverflowPolicy.FAIL,
                ),
            )
        )
