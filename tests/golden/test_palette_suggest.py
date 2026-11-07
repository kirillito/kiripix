"""`suggest_palette`: new colours for a palette from an image, the same every run, compared pixel-exactly with a golden
swatch strip (the palette's colours, a black gap, then the suggested ones, each swatch 4 x 4 pixels)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import srgb_to_oklab, suggest_palette

EXPECTED = Path(__file__).parent / "expected"

PALETTE = np.array([(20, 20, 30), (240, 240, 230), (120, 80, 50)], dtype=np.uint8)
RED, BLUE, GREEN = (200, 30, 40), (40, 70, 200), (60, 170, 70)
MIN_DISTANCE = 0.05


def fixture_image() -> np.ndarray:
    """24 x 16: the palette's colours, big areas of red, blue and (fewer) green, JPEG-like noise on the red, and
    a transparent corner."""
    image = np.zeros((16, 24, 4), dtype=np.uint8)
    image[..., 3] = 255
    image[:, :6, :3] = PALETTE[0]
    image[:, 6:10, :3] = PALETTE[1]
    image[:, 10:13, :3] = PALETTE[2]
    image[:, 13:18, :3] = RED
    image[:, 18:22, :3] = BLUE
    image[:3, 22:, :3] = GREEN
    image[3:, 22:] = 0
    image[::4, 13:18, :3] = (201, 31, 39)  # noise, a hair off the red
    image[1::5, 13:18, :3] = (199, 29, 41)
    return image


def strip(palette: np.ndarray, added: np.ndarray) -> np.ndarray:
    colours = [*palette.tolist(), None, *added.tolist()]
    swatches = [np.dstack([np.full((4, 4), v, dtype=np.uint8) for v in (0, 0, 0, 255)]) if c is None
                else np.dstack([np.full((4, 4), v, dtype=np.uint8) for v in (*c, 255)]) for c in colours]
    return np.concatenate(swatches, axis=1)


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


def test_the_suggestion_matches_the_golden_strip(request: pytest.FixtureRequest) -> None:
    suggestion = suggest_palette(fixture_image(), PALETTE, 6, MIN_DISTANCE)

    assert_golden(request, strip(PALETTE, suggestion.colours), "palette_suggest.png")


def test_the_same_input_gives_the_same_colours() -> None:
    first = suggest_palette(fixture_image(), PALETTE, 6, MIN_DISTANCE)
    second = suggest_palette(fixture_image(), PALETTE, 6, MIN_DISTANCE)

    assert first.colours.tolist() == second.colours.tolist()
    assert first.error_before == second.error_before and first.error_after == second.error_after


def test_no_colour_is_within_the_minimum_distance_of_another_or_of_the_palette() -> None:
    suggestion = suggest_palette(fixture_image(), PALETTE, 6, MIN_DISTANCE)

    lab = srgb_to_oklab(np.concatenate([PALETTE, suggestion.colours]))
    distance = np.sqrt(((lab[:, None] - lab[None]) ** 2).sum(axis=2))
    np.fill_diagonal(distance, np.inf)
    assert len(suggestion.colours) >= 3  # red, blue and green are missing
    assert distance.min() >= MIN_DISTANCE


def test_the_new_colours_lower_the_error() -> None:
    suggestion = suggest_palette(fixture_image(), PALETTE, 6, MIN_DISTANCE)

    assert suggestion.error_after < suggestion.error_before


def test_a_palette_that_fits_adds_nothing() -> None:
    image = fixture_image()
    image[..., :3] = PALETTE[np.arange(image.shape[1]) % 3][None]

    suggestion = suggest_palette(image, PALETTE, 6, MIN_DISTANCE)

    assert len(suggestion.colours) == 0
    assert suggestion.error_before == suggestion.error_after == 0.0


def test_transparent_pixels_are_ignored() -> None:
    image = fixture_image()
    image[..., 3] = 0
    image[:, :6, 3] = 255  # only the palette's own dark colour is opaque
    image[5, 20, :3] = (250, 0, 250)

    suggestion = suggest_palette(image, PALETTE, 4, MIN_DISTANCE)

    assert len(suggestion.colours) == 0 or not (suggestion.colours == (250, 0, 250)).all(axis=1).any()


def test_a_transparent_image_adds_nothing() -> None:
    image = np.zeros((4, 4, 4), dtype=np.uint8)

    assert len(suggest_palette(image, PALETTE, 4, MIN_DISTANCE).colours) == 0


def test_the_count_is_an_upper_bound() -> None:
    assert len(suggest_palette(fixture_image(), PALETTE, 1, MIN_DISTANCE).colours) <= 1
    assert len(suggest_palette(fixture_image(), PALETTE, 0, MIN_DISTANCE).colours) == 0
