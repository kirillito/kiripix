"""Golden tests for orphan pixel removal: a fixed image with islands of 1, 2, 4 and 6 pixels, at orphan sizes 0, 1, 4."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import remove_orphans

EXPECTED = Path(__file__).parent / "expected"

GROUND, RED, GREEN, BLUE, YELLOW = (41, 43, 83), (255, 0, 77), (0, 228, 54), (41, 173, 255), (255, 236, 39)


def islands() -> np.ndarray:
    """24 x 16 ground with: a 1 px red island, a 2 px green one, a 2x2 blue one, a 6 px yellow one, a 1 px red one on
    the corner, a 1 px hole of transparency, and a red pixel between a ground and a yellow region."""
    rgba = np.full((16, 24, 4), 255, dtype=np.uint8)
    rgba[..., :3] = GROUND
    rgba[3, 3, :3] = RED
    rgba[3, 8:10, :3] = GREEN
    rgba[2:4, 14:16, :3] = BLUE
    rgba[9:11, 3:6, :3] = YELLOW
    rgba[0, 0, :3] = RED
    rgba[8, 18] = (0, 0, 0, 0)
    rgba[12, 12, :3] = YELLOW
    rgba[12, 13, :3] = RED
    rgba[12, 14:17, :3] = YELLOW
    return rgba


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


@pytest.mark.parametrize("size", [0, 1, 4])
def test_orphan_removal(request: pytest.FixtureRequest, size: int) -> None:
    result = remove_orphans(islands(), size)

    assert_golden(request, result, f"orphans_{size}.png")


def test_size_0_changes_nothing_and_the_input_is_not_modified() -> None:
    image = islands()
    before = image.copy()

    assert (remove_orphans(image, 0) == before).all()
    remove_orphans(image, 4)
    assert (image == before).all()


def test_an_island_takes_its_most_common_neighbour_colour() -> None:
    image = np.full((3, 3, 4), 255, dtype=np.uint8)
    image[..., :3] = GROUND
    image[1, 1, :3] = RED
    image[0, 0:2, :3] = BLUE
    image[1, 0, :3] = BLUE
    image[0, 1, :3] = BLUE
    image[2, 1, :3] = BLUE  # up, left and down are blue, right is ground

    assert (remove_orphans(image, 1)[1, 1, :3] == BLUE).all()


def test_a_tie_goes_to_the_smaller_colour_whichever_side_it_is_on() -> None:
    image = np.full((3, 3, 4), 255, dtype=np.uint8)
    image[..., :3] = GROUND
    image[1, 1, :3] = RED
    image[0, 0:2, :3] = BLUE  # up and left blue, down and right ground
    image[1, 0, :3] = BLUE
    assert (remove_orphans(image, 1)[1, 1, :3] == GROUND).all()  # GROUND (41, 43, 83) < BLUE (41, 173, 255)

    mirrored = image[::-1, ::-1].copy()  # up and left ground, down and right blue
    assert (remove_orphans(mirrored, 1)[1, 1, :3] == GROUND).all()


def test_two_touching_orphans_do_not_swap_colours() -> None:
    image = np.full((5, 5, 4), 255, dtype=np.uint8)
    image[..., :3] = GROUND
    image[2, 2, :3] = RED
    image[2, 3, :3] = GREEN

    result = remove_orphans(image, 1)

    assert (result[..., :3] == GROUND).all()


def test_transparent_pixels_are_kept_and_not_counted() -> None:
    result = remove_orphans(islands(), 4)

    assert (result[8, 18] == (0, 0, 0, 0)).all()
    assert (result[..., 3] == islands()[..., 3]).all()
