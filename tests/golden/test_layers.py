"""Golden tests for the Layer Ops: small fixed inputs, pixel-exact expected PNGs (masks are shown white on black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import (
    Grid,
    connected_regions,
    cut_by_alpha,
    grow_where_partial,
    mask_from_difference,
    partial_cells,
    recompose,
)

EXPECTED = Path(__file__).parent / "expected"

GROUND, RED, GREEN, BLUE, YELLOW = (41, 43, 83), (255, 0, 77), (0, 228, 54), (41, 173, 255), (255, 236, 39)


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


def picture() -> np.ndarray:
    """12 x 8 opaque ground with a 4x3 red block, a green pixel, a transparent pixel and a blue stripe."""
    rgba = np.full((8, 12, 4), 255, dtype=np.uint8)
    rgba[..., :3] = GROUND
    rgba[2:5, 3:7, :3] = RED
    rgba[1, 9, :3] = GREEN
    rgba[6, 1:11, :3] = BLUE
    rgba[7, 11] = (0, 0, 0, 0)
    return rgba


def seed_and_band() -> tuple[np.ndarray, np.ndarray]:
    """A 3x3 seed Mask on a 14 x 9 canvas, a partial band two pixels wide to its right and a stray partial pixel."""
    alpha = np.zeros((9, 14), dtype=bool)
    alpha[3:6, 2:5] = True
    partial = np.zeros_like(alpha)
    partial[2:7, 5:7] = True
    partial[0, 12] = True
    return alpha, partial


# grow_where_partial


@pytest.mark.parametrize("pixels", [0, 1, 2, 5])
def test_grow_where_partial(request: pytest.FixtureRequest, pixels: int) -> None:
    alpha, partial = seed_and_band()

    grown = grow_where_partial(alpha, partial, pixels)

    assert_golden(request, grown, f"layers_grow_{pixels}.png")


def test_grow_by_0_changes_nothing_and_the_inputs_are_not_modified() -> None:
    alpha, partial = seed_and_band()
    before = alpha.copy(), partial.copy()

    assert (grow_where_partial(alpha, partial, 0) == alpha).all()
    grow_where_partial(alpha, partial, 3)
    assert (alpha == before[0]).all() and (partial == before[1]).all()


def test_grow_with_no_partial_pixels_or_an_empty_mask_changes_nothing() -> None:
    alpha, partial = seed_and_band()

    assert (grow_where_partial(alpha, np.zeros_like(partial), 4) == alpha).all()
    assert not grow_where_partial(np.zeros_like(alpha), partial, 4).any()


# partial_cells


def test_partial_cells(request: pytest.FixtureRequest) -> None:
    """A 4x3 grid of 3-pixel cells at offset (1, 1) over a 14 x 11 Source: a full cell, a third, two thirds, one
    pixel, and set pixels in the margin outside the grid."""
    grid = Grid.uniform(3, 1, 1, 14, 11)
    source = np.zeros((11, 14), dtype=bool)
    source[1:4, 1:4] = True  # cell (0, 0) all set
    source[1:4, 7:8] = True  # cell (2, 0) a third set
    source[4:7, 4:6] = True  # cell (1, 1) two thirds set
    source[9, 10] = True  # cell (3, 2) one pixel
    source[0, :] = True  # the margin, outside every cell
    source[:, 13] = True

    partial = partial_cells(source, grid)

    assert partial.shape == (grid.height, grid.width)
    assert_golden(request, partial, "layers_partial_cells.png")


def test_partial_cells_of_an_empty_and_a_full_mask_are_clear() -> None:
    grid = Grid.uniform(2, 0, 0, 6, 4)

    assert not partial_cells(np.zeros((4, 6), dtype=bool), grid).any()
    assert not partial_cells(np.ones((4, 6), dtype=bool), grid).any()


# mask_from_difference


def test_mask_from_difference(request: pytest.FixtureRequest) -> None:
    plate = picture()
    full = plate.copy()
    full[2:4, 3:5, :3] = YELLOW  # a big change
    full[6, 1, :3] = (41, 173, 254)  # a change under the threshold
    full[0, 0] = (0, 0, 0, 0)  # transparent in one image only
    plate[7, 11, :3] = (9, 9, 9)  # transparent in both, colours differ: not different
    full[0, 11] = (1, 2, 3, 0)
    plate[0, 11] = (200, 100, 50, 0)

    mask = mask_from_difference(full, plate, 0.05)

    assert_golden(request, mask, "layers_difference.png")


def test_a_threshold_of_0_finds_any_colour_difference_and_identical_images_none() -> None:
    plate = picture()
    full = plate.copy()
    full[6, 1, :3] = (41, 173, 254)

    assert mask_from_difference(full, full, 0.0).sum() == 0
    assert mask_from_difference(full, plate, 0.0).sum() == 1
    assert mask_from_difference(full, plate, 0.05).sum() == 0


def test_a_difference_of_images_of_different_sizes_is_refused() -> None:
    with pytest.raises(ValueError, match="one size"):
        mask_from_difference(picture(), picture()[:, :5], 0.1)


# cut_by_alpha and recompose


def layer_alphas() -> tuple[np.ndarray, np.ndarray]:
    """Two Mask regions that overlap on four pixels."""
    first = np.zeros((8, 12), dtype=bool)
    first[1:5, 2:7] = True
    second = np.zeros((8, 12), dtype=bool)
    second[3:7, 5:11] = True
    return first, second


def test_cut_by_alpha(request: pytest.FixtureRequest) -> None:
    first, _ = layer_alphas()

    cut = cut_by_alpha(picture(), first)

    assert_golden(request, cut, "layers_cut.png")
    assert (cut[~first] == 0).all()


def test_cutting_with_an_empty_and_a_full_mask() -> None:
    image = picture()

    assert not cut_by_alpha(image, np.zeros((8, 12), dtype=bool)).any()
    assert (cut_by_alpha(image, np.ones((8, 12), dtype=bool)) == image).all()


def test_recompose_of_the_cuts_returns_the_original_exactly(request: pytest.FixtureRequest) -> None:
    image = picture()
    first, second = layer_alphas()
    plate = cut_by_alpha(image, ~(first | second))
    layers = [cut_by_alpha(image, first), cut_by_alpha(image, second)]  # they overlap, cut from one image

    result = recompose(plate, layers)

    assert_golden(request, result, "layers_recomposed.png")
    assert (result == image).all()


def test_overlapping_layers_stack_in_order(request: pytest.FixtureRequest) -> None:
    first, second = layer_alphas()
    red, blue = np.zeros((8, 12, 4), dtype=np.uint8), np.zeros((8, 12, 4), dtype=np.uint8)
    red[first] = (*RED, 255)
    blue[second] = (*BLUE, 255)
    plate = np.full((8, 12, 4), 255, dtype=np.uint8)
    plate[..., :3] = GROUND

    result = recompose(plate, [red, blue])

    assert_golden(request, result, "layers_overlap.png")
    assert (recompose(plate, [blue, red])[first & second] == (*RED, 255)).all()
    assert (result[first & second] == (*BLUE, 255)).all()


def test_recompose_with_no_layers_or_empty_layers_is_the_plate() -> None:
    plate = picture()

    assert (recompose(plate, []) == plate).all()
    assert (recompose(plate, [np.zeros_like(plate)]) == plate).all()


# connected_regions


def test_connected_regions_are_4_connected_and_in_raster_order(request: pytest.FixtureRequest) -> None:
    mask = np.zeros((7, 10), dtype=bool)
    mask[0, 5] = True  # a lone pixel on the top row, found first
    mask[1:3, 0:3] = True  # a block
    mask[3, 3] = True  # touches the block only diagonally: its own region
    mask[4:7, 6] = True  # a column
    mask[5, 7:9] = True  # joined to the column
    mask[6, 0] = True  # a lone pixel in a corner

    regions = connected_regions(mask)

    assert [len(r) for r in regions] == [1, 6, 1, 5, 1]
    assert regions[0].tolist() == [[0, 5]]
    assert regions[1][0].tolist() == [1, 0] and regions[3][0].tolist() == [4, 6]
    labels = np.zeros((7, 10, 4), dtype=np.uint8)
    labels[..., 3] = 255
    colours = [(255, 0, 77), (0, 228, 54), (41, 173, 255), (255, 236, 39), (255, 119, 168)]
    for region, colour in zip(regions, colours, strict=True):
        labels[region[:, 0], region[:, 1], :3] = colour
    assert_golden(request, labels, "layers_regions.png")


def test_connected_regions_of_an_empty_mask_and_the_same_order_every_time() -> None:
    assert connected_regions(np.zeros((3, 3), dtype=bool)) == []
    mask = np.random.default_rng(7).random((20, 20)) > 0.6

    first, second = connected_regions(mask), connected_regions(mask)

    assert all((a == b).all() for a, b in zip(first, second, strict=True))
    assert sum(len(r) for r in first) == mask.sum()
