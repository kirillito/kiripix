"""Golden tests for the prop Ops (ticket 0050): the exact chroma key on a flat background, the fringe it can leave, and
alpha going to the target grid by majority vote. Small fixed inputs, pixel-exact expected PNGs (masks shown white on
black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import Grid, alpha_by_vote, chroma_key, key_fringe, sample_nearest

EXPECTED = Path(__file__).parent / "expected"

KEY = (0, 255, 0)
RED, BLUE, DARK_GREEN = (255, 0, 77), (41, 173, 255), (0, 90, 20)


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


def on_green() -> np.ndarray:
    """12 x 8 of the key colour with a 4 x 4 red block, a blue pixel and a dark green one inside the block's reach, a
    pixel one level off the key and an edge pixel of a light green that is no key."""
    rgba = np.full((8, 12, 4), 255, dtype=np.uint8)
    rgba[..., :3] = KEY
    rgba[2:6, 4:8, :3] = RED
    rgba[3, 5, :3] = BLUE  # inside the subject
    rgba[4, 6, :3] = DARK_GREEN  # green, but far from the key
    rgba[2, 3, :3] = (0, 254, 0)  # one level off the key, left of the block: an exact key keeps it
    rgba[5, 8, :3] = (20, 235, 20)  # a blend of subject and key on the right edge, close to the key
    rgba[3, 8, :3] = (30, 220, 30)  # a blend further from it
    rgba[0, 11] = (0, 0, 0, 0)  # already transparent
    return rgba


def test_chroma_key_clears_exactly_the_key_colour(request: pytest.FixtureRequest) -> None:
    source = on_green()

    keyed = chroma_key(source, KEY)

    assert (keyed[(source[..., :3] == KEY).all(axis=2)] == 0).all()
    assert keyed[2, 3].tolist() == [0, 254, 0, 255], "one level off is not the key"
    assert keyed[5, 8].tolist() == [20, 235, 20, 255]
    assert keyed[0, 11].tolist() == [0, 0, 0, 0]
    assert_golden(request, keyed, "chroma_key_flat.png")


def test_chroma_key_leaves_the_input_alone_and_keeps_partial_alpha() -> None:
    source = on_green()
    source[6, 1] = (255, 0, 77, 100)
    before = source.copy()

    keyed = chroma_key(source, KEY)

    assert (source == before).all()
    assert keyed[6, 1].tolist() == [255, 0, 77, 100], "partial alpha is a finding for a Check, never rounded here"


def test_chroma_key_with_a_key_that_is_absent_changes_nothing_but_transparent_pixels() -> None:
    source = on_green()

    keyed = chroma_key(source, (255, 0, 255))

    assert (keyed[~(source[..., 3] == 0)] == source[~(source[..., 3] == 0)]).all()


def test_the_fringe_is_the_near_key_pixels_that_touch_cleared_ones(request: pytest.FixtureRequest) -> None:
    keyed = chroma_key(on_green(), KEY)

    fringe = key_fringe(keyed, KEY, 0.06)

    assert fringe[2, 3] and fringe[5, 8], "off by one, and the blend, both touch cleared pixels"
    assert not fringe[3, 8], "a blend this far from the key is the subject's own edge"
    assert not fringe[4, 6], "dark green is far from the key"
    assert not fringe[3, 5], "blue is far from the key"
    assert_golden(request, fringe, "chroma_fringe.png")


def test_a_clean_key_has_no_fringe() -> None:
    source = on_green()
    source[2, 3, :3] = KEY
    source[5, 8, :3] = RED

    assert not key_fringe(chroma_key(source, KEY), KEY, 0.06).any()


def matte_source() -> np.ndarray:
    """8 x 8, as a matting Runner gives it: 2 x 2 cells with a soft edge. Even cells are sampled at their lower-right
    pixel."""
    rgba = np.zeros((8, 8, 4), dtype=np.uint8)
    rgba[..., :3] = RED
    rgba[..., 3] = 255
    rgba[:2, :2, 3] = 0  # cell (0, 0): clear
    rgba[:2, 2:4, 3] = np.array([[200, 90], [200, 90]], dtype=np.uint8)  # cell (0, 1): a tie, sampled pixel clear
    rgba[2:4, 2:4, :3] = BLUE
    rgba[2:4, 2:4, 3] = np.array([[255, 255], [255, 0]], dtype=np.uint8)  # cell (1, 1): 3 of 4, the sampled pixel clear
    rgba[4:6, 0:2, 3] = np.array([[0, 0], [0, 255]], dtype=np.uint8)  # cell (2, 0): 1 of 4, the sampled pixel opaque
    rgba[4:6, 2:4, 3] = np.array([[255, 0], [0, 255]], dtype=np.uint8)  # cell (2, 1): a tie is opaque
    rgba[6:, :, 3] = 127  # the last row of cells: just under the line, clear
    return rgba


def test_alpha_goes_to_the_target_grid_by_majority_vote(request: pytest.FixtureRequest) -> None:
    source = matte_source()
    grid = Grid.uniform(2, 0, 0, 8, 8)

    result = alpha_by_vote(sample_nearest(source, grid), source, grid)

    assert set(np.unique(result[..., 3])) <= {0, 255}
    assert (result[result[..., 3] == 0] == 0).all()
    assert result[0, 1].tolist() == [*RED, 255], "a tie is opaque, with the cell's colour"
    assert result[0, 0, 3] == 0 and result[1, 1, 3] == 255 and result[1, 1].tolist() == [*BLUE, 255], \
        "3 of 4 opaque wins over a clear sampled pixel, with the cell's colour"
    assert result[2, 0, 3] == 0, "1 of 4 opaque loses to an opaque sampled pixel"
    assert result[2, 1, 3] == 255, "a tie is opaque"
    assert (result[3, :, 3] == 0).all(), "alpha 127 is clear"
    assert_golden(request, result, "alpha_vote_grid.png")


def test_alpha_by_vote_agrees_with_the_cell_sizes_it_is_given() -> None:
    source = matte_source()

    with pytest.raises(ValueError, match="the fitted image"):
        alpha_by_vote(np.zeros((3, 3, 4), dtype=np.uint8), source, Grid.uniform(2, 0, 0, 8, 8))


def test_an_outline_is_one_4_adjacent_ring_clipped_at_the_canvas(request: pytest.FixtureRequest) -> None:
    """A 9 x 7 canvas: an L shape touching the left and bottom edges, and a lone pixel; the ring gets a diagonal-free
    border and nothing beyond the canvas."""
    from kiripix.ops import add_outline

    rgba = np.zeros((7, 9, 4), dtype=np.uint8)
    rgba[2:7, 0:2] = (*RED, 255)  # touches the left and the bottom
    rgba[5:7, 2:5] = (*RED, 255)
    rgba[1, 6] = (*BLUE, 255)  # a lone pixel: a plus-shaped ring
    before = rgba.copy()

    result = add_outline(rgba, DARK_GREEN)

    assert (rgba == before).all()
    assert (result[rgba[..., 3] == 255] == rgba[rgba[..., 3] == 255]).all()
    assert result[1, 5].tolist() == [*DARK_GREEN, 255] and result[0, 5, 3] == 0, "diagonals stay clear"
    assert result[1, 1, 3] == 255 and result[1, 0].tolist() == [*DARK_GREEN, 255]
    assert set(np.unique(result[..., 3])) == {0, 255}
    assert_golden(request, result, "add_outline.png")
