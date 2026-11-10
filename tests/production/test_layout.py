import pytest

from mt_engine.production.layout import (
    CanvasLayoutContext,
    CollisionPolicy,
    LayoutCoordinator,
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
