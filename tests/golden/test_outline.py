"""Golden tests for the outline Ops (ticket 0109): the line Mask of a silhouette, outside it or on its edge pixels,
and painted in one colour. Small fixed inputs, pixel-exact expected PNGs (masks shown white on black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import add_outline, outline_mask, paint_outline

EXPECTED = Path(__file__).parent / "expected"
INK, RED = (0, 90, 20), (255, 0, 77)


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    if actual.dtype == np.bool_:
        shown = np.zeros((*actual.shape, 4), dtype=np.uint8)
        shown[..., 3] = 255
        shown[actual, :3] = 255
        actual = shown
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def square() -> np.ndarray:
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 2:6] = True
    return mask


def at_the_edge() -> np.ndarray:
    mask = np.zeros((8, 8), dtype=bool)
    mask[3:8, 0:3] = True  # touches the left and the bottom
    return mask


def test_outside_a_square_is_a_4_adjacent_ring(request: pytest.FixtureRequest) -> None:
    mask = square()
    line = outline_mask(mask)
    assert line.sum() == 16 and not (line & mask).any() and not line[1, 1], "no corners"
    assert_golden(request, line, "outline_square_outside.png")


def test_on_the_edge_a_square_keeps_its_size(request: pytest.FixtureRequest) -> None:
    mask = square()
    line = outline_mask(mask, "edge")
    assert line.sum() == 12 and (line <= mask).all() and not line[3:5, 3:5].any()
    assert_golden(request, line, "outline_square_edge.png")


def test_a_shape_touching_the_frame_is_clipped_outside_and_closed_on_the_edge(request: pytest.FixtureRequest) -> None:
    mask = at_the_edge()
    outside, edge = outline_mask(mask), outline_mask(mask, "edge")
    assert outside.shape == mask.shape and outside[2, 0] and outside.sum() == 8, "clipped: 3 above, 5 right"
    assert edge[7, 1] and edge[4, 0], "the frame's edge counts as empty"
    assert_golden(request, outside, "outline_frame_edge_outside.png")
    assert_golden(request, edge, "outline_frame_edge_edge.png")


@pytest.mark.parametrize("placement", ["outside", "edge"])
def test_a_still_part_has_the_same_outline_in_two_frames(request: pytest.FixtureRequest, placement: str) -> None:
    """A still 3 x 3 block on the left and a 2 x 2 arm that moves on the right: the block's line, away from the arm,
    is the same in both frames."""
    frames = []
    for arm_y in (1, 4):
        mask = np.zeros((8, 12), dtype=bool)
        mask[2:5, 1:4] = True
        mask[arm_y:arm_y + 2, 8:10] = True
        frames.append(mask)
    lines = [outline_mask(frame, placement) for frame in frames]  # type: ignore[arg-type]
    assert (lines[0][:, :6] == lines[1][:, :6]).all()
    assert not (lines[0] == lines[1]).all()
    assert_golden(request, np.concatenate(lines, axis=1), f"outline_two_frames_{placement}.png")


def test_painting_changes_only_the_line_pixels_and_keeps_alpha_binary(request: pytest.FixtureRequest) -> None:
    rgba = np.zeros((8, 8, 4), dtype=np.uint8)
    rgba[square()] = (*RED, 255)
    before = rgba.copy()
    outside = paint_outline(rgba, outline_mask(square()), INK)
    edge = paint_outline(rgba, outline_mask(square(), "edge"), INK)
    assert (rgba == before).all()
    assert outside[1, 2].tolist() == [*INK, 255] and outside[2, 2].tolist() == [*RED, 255]
    assert edge[2, 2].tolist() == [*INK, 255] and edge[3, 3].tolist() == [*RED, 255] and edge[1, 2, 3] == 0
    assert set(np.unique(outside[..., 3])) == {0, 255}
    assert (add_outline(rgba, INK) == outside).all() and (add_outline(rgba, INK, "edge") == edge).all()
    assert_golden(request, outside, "outline_painted_outside.png")
    assert_golden(request, edge, "outline_painted_edge.png")


def test_wrong_shapes_and_placements_are_refused() -> None:
    with pytest.raises(ValueError, match="placement"):
        outline_mask(square(), "inside")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Mask"):
        outline_mask(np.zeros((2, 2, 2), dtype=bool))
    with pytest.raises(ValueError, match="line Mask"):
        paint_outline(np.zeros((4, 4, 4), dtype=np.uint8), np.zeros((3, 3), dtype=bool), INK)
