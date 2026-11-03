"""The overlay Op, called directly and compared pixel-exactly with hand-written expected arrays."""

import numpy as np
import pytest

from kiripix.ops import overlay

RED = [255, 0, 77, 255]
BLUE = [41, 173, 255, 255]
HALF = [0, 228, 54, 128]
CLEAR = [0, 0, 0, 0]


def image(rows: list[list[list[int]]]) -> np.ndarray:
    return np.array(rows, dtype=np.uint8)


def test_painted_pixels_replace_the_base_and_transparent_ones_leave_it() -> None:
    base = image([[RED, RED], [RED, CLEAR]])
    top = image([[BLUE, CLEAR], [HALF, BLUE]])

    result = overlay(base, top)

    assert result.tolist() == [[BLUE, RED], [HALF, BLUE]]
    assert base.tolist() == [[RED, RED], [RED, CLEAR]]  # the input is unchanged


def test_images_of_different_sizes_are_refused() -> None:
    with pytest.raises(ValueError, match="same size"):
        overlay(image([[RED]]), image([[RED, RED]]))
