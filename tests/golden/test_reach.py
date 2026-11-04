"""The reach Ops, called directly: walkable from `solid` and the Body's footprint, compared pixel-exactly with golden
PNGs (a walkable pixel is white, the rest black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import walkable

EXPECTED = Path(__file__).parent / "expected"


def as_image(mask: np.ndarray) -> np.ndarray:
    grey = np.where(mask, 255, 0).astype(np.uint8)
    return np.dstack([grey, grey, grey, np.full_like(grey, 255)])


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def corner() -> np.ndarray:
    """48 x 32: a solid block filling the room's top right, so the floor turns a corner around it."""
    solid = np.zeros((32, 48), dtype=np.bool_)
    solid[:16, 24:] = True
    return solid


def gap(width: int) -> np.ndarray:
    """48 x 32: a solid wall across the room at x 20 to 23, with a gap `width` pixels wide from y 12."""
    solid = np.zeros((32, 48), dtype=np.bool_)
    solid[:, 20:24] = True
    solid[12:12 + width, 20:24] = False
    return solid


def test_walkable_for_a_12_by_8_footprint_around_a_corner(request: pytest.FixtureRequest) -> None:
    assert_golden(request, as_image(walkable(corner(), (12, 8))), "walkable_corner.png")


def test_walkable_through_a_gap_narrower_than_the_footprint(request: pytest.FixtureRequest) -> None:
    # A 12 x 8 footprint needs 8 rows free to cross the wall, and the gap has 7: the two sides stay apart.
    assert_golden(request, as_image(walkable(gap(7), (12, 8))), "walkable_narrow_gap.png")


def test_the_footprint_is_centred_with_the_extra_pixel_up_and_left_of_the_spot() -> None:
    # Worked by hand: a 12 x 8 footprint at spot (x, y) covers x - 6 to x + 5 and y - 4 to y + 3.
    result = walkable(np.zeros((32, 48), dtype=np.bool_), (12, 8))

    assert result[4, 6] and result[28, 42]
    assert not result[3, 6] and not result[4, 5]  # the footprint would cross the top or left edge
    assert not result[29, 42] and not result[28, 43]  # or the bottom or right edge


def test_a_single_solid_pixel_blocks_exactly_the_spots_whose_footprint_covers_it() -> None:
    solid = np.zeros((9, 9), dtype=np.bool_)
    solid[4, 4] = True

    result = walkable(solid, (3, 3))

    expected = np.zeros((9, 9), dtype=np.bool_)
    expected[1:8, 1:8] = True  # a 3 x 3 footprint fits from 1 to 7
    expected[3:6, 3:6] = False  # and touches the pixel from 3 to 5
    assert (result == expected).all()


def test_a_gap_exactly_as_wide_as_the_footprint_is_walkable_one_row_narrower_is_not() -> None:
    wide, narrow = walkable(gap(8), (12, 8)), walkable(gap(7), (12, 8))

    assert wide[:, 21].any()
    assert not narrow[:, 21].any()


def test_a_footprint_larger_than_the_room_fits_nowhere() -> None:
    assert not walkable(np.zeros((4, 4), dtype=np.bool_), (5, 2)).any()


def test_the_input_is_not_modified_and_bad_input_is_refused() -> None:
    solid = corner()
    before = solid.copy()
    walkable(solid, (12, 8))
    assert (solid == before).all()

    with pytest.raises(ValueError, match="footprint"):
        walkable(solid, (0, 8))
    with pytest.raises(ValueError, match="Mask"):
        walkable(np.zeros((4, 4), dtype=np.uint8), (2, 2))
