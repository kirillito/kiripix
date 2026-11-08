"""The resample Ops, called directly: grid detection, sampling and mode-filter downscale (pixel-exact against golden
PNGs), and mapping points and Masks through a Grid transform."""

from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import (
    Grid,
    detect_grid,
    downscale,
    mask_to_source,
    mask_to_target,
    point_to_target,
    sample_nearest,
    target_centre,
    upscale,
)

EXPECTED = Path(__file__).parent / "expected"

PALETTE = np.array([[0, 0, 0], [255, 0, 77], [41, 173, 255], [0, 228, 54], [255, 236, 39]], dtype=np.uint8)
FILL = (131, 118, 156, 255)


def art() -> np.ndarray:
    """A 12x8 piece of pixel art with no two equal neighbours along a row or a column."""
    y, x = np.mgrid[0:8, 0:12]
    index = (x * 2 + y * 3 + (x * y) % 5) % 5
    rgba = np.full((8, 12, 4), 255, dtype=np.uint8)
    rgba[..., :3] = PALETTE[index]
    rgba[0, 0] = 0  # one transparent pixel
    return rgba


def padded(image: np.ndarray, before: tuple[int, int], after: tuple[int, int]) -> np.ndarray:
    """`image` with a border of FILL: (x, y) pixels before and after."""
    result = np.empty((image.shape[0] + before[1] + after[1], image.shape[1] + before[0] + after[0], 4), np.uint8)
    result[:] = FILL
    result[before[1]:before[1] + image.shape[0], before[0]:before[0] + image.shape[1]] = image
    return result


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


# grid detection


@pytest.mark.parametrize(("scale", "offset"), [(2, (0, 0)), (3, (0, 0)), (4, (0, 0)), (2, (1, 0)), (3, (2, 1)),
                                               (4, (3, 2)), (4, (1, 3))])
def test_detect_grid_finds_the_scale_and_offset_of_upscaled_pixel_art(
        request: pytest.FixtureRequest, scale: int, offset: tuple[int, int]) -> None:
    source = padded(upscale(art(), scale), offset, (scale - 1, 1))

    grid = detect_grid(source)

    assert (grid.scale_x, grid.scale_y) == (scale, scale)
    assert (grid.offset_x, grid.offset_y) == offset
    assert (grid.width, grid.height) == (12, 8)
    if offset == (0, 0):
        assert_golden(request, sample_nearest(source, grid), "grid_sampled_art.png")


def test_sampling_a_detected_grid_gives_the_art_back() -> None:
    for scale, offset in [(2, (1, 1)), (3, (2, 0)), (4, (0, 3))]:
        source = padded(upscale(art(), scale), offset, (0, 0))

        grid = detect_grid(source)

        assert grid == Grid.uniform(scale, offset[0], offset[1], source.shape[1], source.shape[0])
        assert (sample_nearest(source, grid) == art()).all()


def test_detection_tolerates_a_few_stray_pixels() -> None:
    source = upscale(art(), 4)
    source[5, 6] = source[5, 7] = (1, 2, 3, 255)  # a stray pair inside one cell
    source[21, 30] = (9, 9, 9, 255)

    grid = detect_grid(source)

    assert grid.scale_x == 4 and grid.scale_y == 4


def test_an_image_without_a_grid_gets_the_1x_grid() -> None:
    noise = np.random.default_rng(1).integers(0, 256, size=(40, 40, 4), dtype=np.uint8)
    flat = np.full((10, 10, 4), 255, dtype=np.uint8)

    for image in (noise, flat):
        grid = detect_grid(image)
        assert (grid.scale_x, grid.scale_y, grid.width, grid.height) == (1, 1, image.shape[1], image.shape[0])


def test_grid_transform_round_trips_through_json() -> None:
    uniform = Grid.uniform(4, 3, 2, 1923, 1090)
    ratio = Grid.to_size(1920, 1088, 480, 272)
    fractional = Grid.to_size(10, 7, 4, 3)

    assert uniform.to_json() == {"scale_x": 4, "scale_y": 4, "offset_x": 3, "offset_y": 2, "width": 480, "height": 272}
    assert ratio.to_json()["scale_x"] == 4
    assert fractional.to_json()["scale_x"] == "5/2" and fractional.to_json()["scale_y"] == "7/3"
    assert all(Grid.from_json(g.to_json()) == g for g in (uniform, ratio, fractional))


# downscale


def test_downscaling_uniform_cells_gives_the_colours_back(request: pytest.FixtureRequest) -> None:
    source = upscale(art(), 4)

    result = downscale(source, Grid.to_size(48, 32, 12, 8))

    assert (result == art()).all()
    assert_golden(request, result, "downscale_art.png")


def test_downscale_by_a_ratio_partitions_the_source_exactly(request: pytest.FixtureRequest) -> None:
    source = art()[:, :10].copy()
    source[0, 0] = (255, 0, 77, 255)

    result = downscale(source, Grid.to_size(10, 8, 4, 3))

    assert result.shape == (3, 4, 4)
    assert_golden(request, result, "downscale_ratio.png")


def test_a_cell_of_two_clearly_different_colours_takes_the_darker_when_it_covers_enough() -> None:
    red, blue = (255, 0, 77, 255), (41, 173, 255, 255)
    cell = np.array([[red, blue], [blue, red]], dtype=np.uint8)

    assert downscale(cell, Grid.to_size(2, 2, 1, 1)).tolist() == [[list(red)]]  # red is the darker, at 50 % of the cell
    assert downscale(cell[::-1], Grid.to_size(2, 2, 1, 1)).tolist() == [[list(red)]]


def painted_wall(width: int, height: int) -> np.ndarray:
    """A soft-shaded wall with a little deterministic noise, as a painted Source has."""
    rng = np.random.default_rng(11)
    x = np.arange(width)[None, :, None] * np.ones((height, 1, 3))
    base = np.array([96, 128, 132]) + (x * 0.6).astype(np.int64) * np.array([1, 1, 1])
    wall = np.full((height, width, 4), 255, dtype=np.uint8)
    wall[..., :3] = np.clip(base + rng.integers(-3, 4, size=(height, width, 3)), 0, 255)
    return wall


def test_a_thin_dark_line_straddling_cells_stays_one_continuous_pixel_line(request: pytest.FixtureRequest) -> None:
    source = painted_wall(30, 30)
    source[:, 5:7] = (20, 30, 35, 255)  # a 2 px vertical line across the cells [4, 6) and [6, 8): half of each
    source[22:24, 10:] = (20, 30, 35, 255)  # and a horizontal one across the rows [21, 23) and [23, 25), clear of it

    result = downscale(source, Grid.to_size(30, 30, 14, 14))

    dark = result[..., :3].sum(axis=2) < 150
    columns = np.nonzero(dark[0])[0]
    rows = np.nonzero(dark[:, 13])[0]
    assert columns.tolist() == [3] and rows.tolist() == [11]  # one pixel wide each, on the cell with the larger share
    assert dark[:, 3].all() and dark[11, 5:].all()  # unbroken along their length
    assert dark.sum() == 14 + 9  # and nothing else is dark
    assert_golden(request, result, "downscale_thin_line.png")


def test_a_flat_soft_shaded_area_stays_even(request: pytest.FixtureRequest) -> None:
    source = painted_wall(45, 30)

    result = downscale(source, Grid.to_size(45, 30, 21, 14))

    mean = np.stack([np.add.reduceat(np.add.reduceat(source[..., c].astype(float), Grid.to_size(45, 30, 21, 14).edges_y()[:-1],
                                                     axis=0), Grid.to_size(45, 30, 21, 14).edges_x()[:-1], axis=1)
                     for c in range(3)], axis=-1)
    sizes = np.outer(np.diff(Grid.to_size(45, 30, 21, 14).edges_y()), np.diff(Grid.to_size(45, 30, 21, 14).edges_x()))
    assert np.abs(result[..., :3] - mean / sizes[..., None]).max() <= 3  # within the noise of the plain mean
    assert_golden(request, result, "downscale_soft_shade.png")


def test_alpha_is_binarised_by_majority_vote(request: pytest.FixtureRequest) -> None:
    red = (255, 0, 77, 255)
    source = np.zeros((4, 8, 4), dtype=np.uint8)
    source[:, :4] = red
    source[:2, :2] = (0, 0, 0, 0)  # cells are 2x2: the first is wholly transparent
    source[0, 4:6] = (0, 228, 54, 200)  # the third: two pixels opaque from 128, two not: a tie, so opaque
    source[1, 4:6] = (0, 228, 54, 100)
    source[2:, 4:8] = (0, 228, 54, 90)  # the last two: all below 128, so transparent

    result = downscale(source, Grid.to_size(8, 4, 4, 2))

    assert set(np.unique(result[..., 3])) <= {0, 255}
    assert (result[result[..., 3] == 0] == 0).all()
    assert_golden(request, result, "downscale_alpha_vote.png")


def test_sampling_binarises_alpha_too() -> None:
    source = np.array([[[10, 20, 30, 127], [10, 20, 30, 128]]], dtype=np.uint8)

    assert sample_nearest(source, Grid.uniform(1, 0, 0, 2, 1)).tolist() == [[[0, 0, 0, 0], [10, 20, 30, 255]]]


def test_a_grid_past_the_image_is_refused() -> None:
    with pytest.raises(ValueError, match="past the"):
        sample_nearest(np.zeros((4, 4, 4), dtype=np.uint8), Grid.uniform(2, 0, 0, 8, 8))


def test_upscale_repeats_whole_pixels() -> None:
    assert upscale(np.array([[1, 2]], dtype=np.uint8), 2).tolist() == [[1, 1, 2, 2], [1, 1, 2, 2]]
    with pytest.raises(ValueError, match="whole"):
        upscale(np.zeros((1, 1), dtype=np.uint8), 0)


# points and Masks


def test_a_point_maps_to_the_target_pixel_and_a_pixel_to_its_centre() -> None:
    grid = Grid.uniform(4, 3, 2, 1923, 1090)

    assert point_to_target(grid, 3, 2) == (0, 0)
    assert point_to_target(grid, 6.9, 5.9) == (0, 0)
    assert point_to_target(grid, 7, 6) == (1, 1)
    assert point_to_target(grid, 1.0, 1.0) == (0, 0)  # before the grid: the nearest cell
    assert point_to_target(grid, 5000, 5000) == (479, 271)
    assert target_centre(grid, 0, 0) == (5.0, 4.0)
    assert target_centre(grid, 2, 3) == (13.0, 16.0)
    assert point_to_target(grid, *target_centre(grid, 17, 9)) == (17, 9)


def test_a_point_maps_through_a_ratio_grid_exactly() -> None:
    grid = Grid.to_size(10, 7, 4, 3)  # cells start at 0, 2, 5, 7 and end at 10

    assert [point_to_target(grid, x, 0)[0] for x in (0, 1.999, 2, 4.99, 5, 7, 9.5)] == [0, 0, 1, 1, 2, 3, 3]
    assert grid.scale_x == Fraction(5, 2)
    assert target_centre(grid, 1, 0)[0] == 3.5


def test_masks_map_by_majority_and_back_to_the_source() -> None:
    grid = Grid.uniform(2, 1, 0, 6, 4)  # a 2x2 grid of 2x2 cells, from column 1
    source = np.zeros((4, 6), dtype=bool)
    source[0:2, 1:3] = True  # cell (0, 0) full
    source[0, 3] = source[1, 3] = True  # cell (1, 0): half, set on a tie
    source[2, 1] = True  # cell (0, 1): a quarter, clear

    target = mask_to_target(source, grid)

    assert target.tolist() == [[True, True], [False, False]]
    back = mask_to_source(target, grid, 6, 4)
    assert back.dtype == np.bool_
    assert back.astype(int).tolist() == [[0, 1, 1, 1, 1, 0], [0, 1, 1, 1, 1, 0], [0] * 6, [0] * 6]
    assert not back[:, 0].any() and not back[:, 5].any()  # outside the grid


def test_masks_must_be_boolean() -> None:
    with pytest.raises(ValueError, match="Mask"):
        mask_to_target(np.zeros((4, 4), dtype=np.uint8), Grid.uniform(2, 0, 0, 4, 4))
