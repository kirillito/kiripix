"""Golden tests for the stacking Ops (ticket 0294): a body and two Wearables on 12 x 8 frames, stacked by order and by depth."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import stack_by_depth, stack_by_order, stack_difference

EXPECTED = Path(__file__).parent / "expected"
FAR = 65535
BODY, PACK, COAT = (200, 160, 120), (40, 90, 200), (180, 30, 60)


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    if actual.dtype == np.bool_:
        shown = np.zeros((*actual.shape, 4), dtype=np.uint8)
        shown[..., 3] = 255
        shown[actual, :3] = 255
        actual = shown
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    assert not (actual != expected).any(), f"{int((actual != expected).any(axis=2).sum())} pixels differ from {name}"


def block(colour: tuple[int, int, int], x0: int, x1: int, y0: int, y1: int, depth: int) -> tuple[np.ndarray, np.ndarray]:
    frame = np.zeros((8, 12, 4), dtype=np.uint8)
    frame[y0:y1, x0:x1] = (*colour, 255)
    z = np.full((8, 12), FAR, dtype=np.uint16)
    z[y0:y1, x0:x1] = depth
    return frame, z


def parts() -> tuple[list[np.ndarray], list[np.ndarray]]:
    """The body (a block at depth 100), a pack that is behind the body on its left and in front of it on its right (the
    interleaving a fixed order cannot get right), and a coat in front of the body, tied with the pack at one column."""
    body, body_z = block(BODY, 3, 9, 1, 7, 100)
    pack, pack_z = block(PACK, 1, 7, 2, 6, 150)
    pack_z[:, 5:7] = 50  # the pack's right edge is in front of the body
    coat, coat_z = block(COAT, 6, 11, 3, 8, 80)
    coat_z[:, 6] = 50  # ties with the pack at depth 50 in column 6: the later frame wins
    return [body, pack, coat], [body_z, pack_z, coat_z]


def test_by_order_pastes_each_frame_over_the_last(request: pytest.FixtureRequest) -> None:
    frames, _ = parts()

    out = stack_by_order(frames)

    assert_golden(request, out, "stack_by_order.png")
    assert (out[3, 4, :3] == PACK).all(), "the pack is above the body wherever it has pixels, even where it is behind it"


def test_by_depth_lets_the_nearest_frame_win_and_the_later_one_a_tie(request: pytest.FixtureRequest) -> None:
    frames, depths = parts()

    out = stack_by_depth(frames, depths)

    assert_golden(request, out, "stack_by_depth.png")
    assert (out[3, 4, :3] == BODY).all(), "the body is nearer than the pack on the pack's left"
    assert (out[3, 5, :3] == PACK).all() and (out[3, 6, :3] == COAT).all(), "the pack's edge is nearer; a tie goes to the coat"


def test_the_difference_marks_pixels_where_alpha_or_colour_differ(request: pytest.FixtureRequest) -> None:
    frames, depths = parts()

    diff = stack_difference(stack_by_order(frames), stack_by_depth(frames, depths))

    assert_golden(request, diff, "stack_difference.png")
    assert diff.sum() > 0 and not stack_difference(frames[0], frames[0]).any()


def test_the_input_is_not_modified_and_bad_input_is_refused() -> None:
    frames, depths = parts()
    before = [f.copy() for f in frames]

    stack_by_order(frames)
    stack_by_depth(frames, depths)

    assert all((a == b).all() for a, b in zip(frames, before, strict=True))
    with pytest.raises(ValueError):
        stack_by_depth(frames, depths[:2])
    with pytest.raises(ValueError):
        stack_by_order([])
