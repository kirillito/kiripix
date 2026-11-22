"""Golden tests for the style measures (ticket 0333): exact numbers on small fixed figures. The measures return numbers,
so the expected values are written here and not as PNGs."""

import numpy as np

from kiripix.ops import OutlineMeasure, ScaleMeasure, outline_density, pixel_scale

INK = (0, 0, 0)
RED, GREEN = (200, 30, 30), (30, 200, 30)


def figure(outlined: bool) -> np.ndarray:
    """A 6 x 6 figure on an 8 x 8 canvas: a ring (the outline, or the fill's colour) round a 4 x 4 fill of two colours."""
    image = np.zeros((8, 8, 4), dtype=np.uint8)
    image[1:7, 1:7] = (*(INK if outlined else RED), 255)
    image[2:6, 2:4] = (*RED, 255)
    image[2:6, 4:6] = (*GREEN, 255)
    return image


def test_outlined_figure_has_the_outline_on_its_whole_edge() -> None:
    assert outline_density(figure(True), INK) == OutlineMeasure(outline_px=20, edge_px=20, density=1.0)


def test_figure_without_its_outline_has_density_zero() -> None:
    assert outline_density(figure(False), INK) == OutlineMeasure(outline_px=0, edge_px=20, density=0.0)


def test_half_outlined_edge_and_an_empty_image() -> None:
    image = figure(True)
    image[1, 1:7] = (*RED, 255)  # the top row of the ring
    assert outline_density(image, INK) == OutlineMeasure(outline_px=14, edge_px=20, density=0.7)
    assert outline_density(np.zeros((4, 4, 4), dtype=np.uint8), INK) == OutlineMeasure(0, 0, 0.0)


def test_image_border_counts_as_an_edge() -> None:
    image = np.full((3, 3, 4), 255, dtype=np.uint8)
    assert outline_density(image, (255, 255, 255)) == OutlineMeasure(outline_px=9, edge_px=8, density=9 / 8)


def pattern() -> np.ndarray:
    """3 x 3 pixels, no two neighbours alike, so every run is 1 long."""
    image = np.zeros((3, 3, 4), dtype=np.uint8)
    image[..., 3] = 255
    for y in range(3):
        for x in range(3):
            image[y, x, :3] = (10 + 20 * ((x + y) % 2), 30 * y, 40 * x)
    return image


def test_unscaled_figure_has_gcd_one() -> None:
    assert pixel_scale(pattern()) == ScaleMeasure(runs=18, gcd=1, median=1.0, run1_share=1.0)


def test_figure_scaled_2x_has_gcd_two() -> None:
    image = np.repeat(np.repeat(pattern(), 2, 0), 2, 1)
    assert pixel_scale(image) == ScaleMeasure(runs=36, gcd=2, median=2.0, run1_share=0.0)


def test_figure_scaled_3x_has_gcd_three() -> None:
    image = np.repeat(np.repeat(pattern(), 3, 0), 3, 1)
    assert pixel_scale(image).gcd == 3


def test_transparent_pixels_end_a_run_and_make_none() -> None:
    image = np.zeros((1, 5, 4), dtype=np.uint8)
    image[0, 0:2] = (*RED, 255)
    image[0, 3:5] = (*RED, 255)
    assert pixel_scale(image) == ScaleMeasure(runs=6, gcd=1, median=1.0, run1_share=4 / 6)  # two runs of 2 along the row, four of 1 down the columns
    assert pixel_scale(np.zeros((4, 4, 4), dtype=np.uint8)) == ScaleMeasure(0, 0, 0.0, 0.0)


def naive_runs(image: np.ndarray) -> list[int]:
    found: list[int] = []
    for grid in (image, image.transpose(1, 0, 2)):
        for line in grid:
            length = 0
            for i in range(len(line)):
                if line[i, 3] == 0:
                    length = 0
                    continue
                length = length + 1 if i and line[i - 1, 3] and (line[i, :3] == line[i - 1, :3]).all() else 1
                if i + 1 == len(line) or not line[i + 1, 3] or (line[i + 1, :3] != line[i, :3]).any():
                    found.append(length)
    return found


def test_runs_match_a_plain_loop_on_random_images() -> None:
    rng = np.random.default_rng(7)
    for _ in range(20):
        image = rng.integers(0, 2, size=(9, 11, 4), dtype=np.uint8) * 200
        image[..., 3] = rng.integers(0, 4, size=(9, 11)) > 0
        image[..., 3] *= 255
        runs = naive_runs(image)
        expected = ScaleMeasure(len(runs), int(np.gcd.reduce(runs)) if runs else 0,
                                float(np.median(runs)) if runs else 0.0, float((np.array(runs) == 1).mean()) if runs else 0.0)
        assert pixel_scale(image) == expected
