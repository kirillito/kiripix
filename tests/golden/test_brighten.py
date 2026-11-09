"""Golden test for the `brighten` Op, which `preview --brighten` uses (ticket 0086)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops.preview import brighten

EXPECTED = Path(__file__).parent / "expected"


def dark_ramp() -> np.ndarray:
    """A 16 x 4 image whose red goes 0..150 in steps of 10, with green and blue at other levels, and a ramp of alpha."""
    image = np.zeros((4, 16, 4), dtype=np.uint8)
    image[..., 0] = np.arange(16, dtype=np.uint8) * 10
    image[..., 1] = np.arange(16, dtype=np.uint8)[::-1] * 5
    image[..., 2] = 40
    image[..., 3] = np.array([255, 200, 100, 0], dtype=np.uint8)[:, None]
    return image


def test_brighten_matches_the_golden_image_and_clips(request: pytest.FixtureRequest) -> None:
    image = dark_ramp()

    actual = brighten(image, 1.8)

    path = EXPECTED / "brighten_1_8.png"
    if request.config.getoption("--update-golden"):
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as expected_image:
        expected = np.asarray(expected_image.convert("RGBA"), dtype=np.uint8)
    assert (actual == expected).all()
    assert actual[0, 15, 0] == 255, "150 * 1.8 = 270 is clipped"
    assert (actual[..., 3] == image[..., 3]).all(), "alpha is untouched"


def test_a_factor_of_one_returns_the_image_unchanged_and_the_input_is_not_modified() -> None:
    image = dark_ramp()
    before = image.copy()

    result = brighten(image, 1)

    assert (result == image).all() and result is not image
    assert (image == before).all()
    assert (brighten(image, 2.5) != image).any() and (image == before).all()


def test_a_factor_above_one_never_darkens_and_one_below_never_brightens() -> None:
    image = dark_ramp()

    assert (brighten(image, 1.5)[..., :3] >= image[..., :3]).all()
    assert (brighten(image, 0.5)[..., :3] <= image[..., :3]).all()


def test_a_factor_of_zero_or_less_is_refused() -> None:
    with pytest.raises(ValueError):
        brighten(dark_ramp(), 0)
