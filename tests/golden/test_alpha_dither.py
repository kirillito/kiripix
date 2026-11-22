"""Golden tests for `dither_alpha` (ticket 0363): partial alpha becomes a fixed ordered pattern of 0 and 255. The input is
three 8 x 8 blocks of one colour at alpha 51, 102 and 204 (20 %, 40 % and 80 %); the golden is the Bayer 4 result, enlarged
x6 by nearest neighbour so each pixel is a visible 6 x 6 block (left to right: alpha 51, 102, 204)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import Grid, alpha_coverage, dither_alpha, upscale

EXPECTED = Path(__file__).parent / "expected"
SCALE = 6
ALPHAS = (51, 102, 204)


def blocks() -> np.ndarray:
    image = np.zeros((8, 24, 4), dtype=np.uint8)
    for i, alpha in enumerate(ALPHAS):
        image[:, i * 8:(i + 1) * 8] = (80, 200, 255, alpha)
    return image


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def test_partial_alpha_becomes_a_bayer_pattern_of_about_its_density(request: pytest.FixtureRequest) -> None:
    source = blocks()
    before = source.copy()

    result = dither_alpha(source, 4)

    assert (source == before).all(), "the input is not modified"
    assert set(np.unique(result[..., 3])) == {0, 255}
    assert (result[..., :3] == source[..., :3]).all(), "RGB is copied unchanged"
    opaque = [int((result[:, i * 8:(i + 1) * 8, 3] == 255).sum()) for i in range(3)]
    assert opaque == [12, 24, 52], "3, 6 and 13 of every 16 pixels: the density rounded to the matrix steps"
    assert_golden(request, upscale(result, SCALE), "alpha_dither_bayer4.png")


def test_alpha_0_and_255_never_change_and_the_pattern_repeats_by_position() -> None:
    image = np.zeros((16, 16, 4), dtype=np.uint8)
    image[:8, :, 3] = 255
    image[8:, :8, 3] = 100
    image[8:, 8:, 3] = 100

    for size in (2, 4, 8):
        result = dither_alpha(image, size)
        assert (result[:8, :, 3] == 255).all() and (result[:8] == dither_alpha(image, size)[:8]).all()
        assert (result[8:, :8, 3] == result[8:, 8:, 3]).all(), "the same alpha gives the same pattern anywhere a period apart"
        clear = dither_alpha(np.zeros((8, 8, 4), dtype=np.uint8), size)
        assert (clear[..., 3] == 0).all()


def test_density_follows_alpha_for_every_pattern() -> None:
    for size in (2, 4, 8):
        counts = []
        for alpha in range(0, 256, 15):
            tile = np.zeros((8, 8, 4), dtype=np.uint8)
            tile[..., 3] = alpha
            counts.append(int((dither_alpha(tile, size)[..., 3] == 255).sum()))
        assert counts == sorted(counts) and counts[0] == 0 and counts[-1] == 64


def test_a_pattern_that_is_no_bayer_size_is_refused() -> None:
    with pytest.raises(ValueError, match="2, 4 or 8"):
        dither_alpha(blocks(), 3)
    with pytest.raises(ValueError, match="RGBA"):
        dither_alpha(np.zeros((4, 4, 3), dtype=np.uint8), 4)


def test_alpha_coverage_is_the_cells_mean_alpha() -> None:
    source = np.zeros((4, 4, 4), dtype=np.uint8)
    source[:2, :2, 3] = 255
    source[:2, 2:, 3] = [[100, 101], [100, 101]]
    source[2:, :2, 3] = [[255, 255], [255, 0]]

    coverage = alpha_coverage(source, Grid.uniform(2, 0, 0, 4, 4))

    assert coverage.tolist() == [[255, 101], [191, 0]], "100.5 rounds up; 3 of 4 opaque is 191"
