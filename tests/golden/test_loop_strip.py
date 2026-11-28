"""A frame Loop's strip keeps only what differs from frame 0 (ticket 0403), `clear_unchanged` called directly: a small
patterned room with a few moving pixels, compared pixel-exactly with a golden PNG."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import clear_unchanged

EXPECTED = Path(__file__).parent / "expected"
PALETTE = [(16, 14, 24), (60, 58, 70), (190, 230, 250), (150, 100, 60)]


def room() -> np.ndarray:
    """A 6 x 5 room in a checker of two colours."""
    image = np.zeros((5, 6, 4), dtype=np.uint8)
    for y in range(5):
        for x in range(6):
            image[y, x] = (*PALETTE[(x + y) % 2], 255)
    return image


def frames() -> np.ndarray:
    """Four frames: a pixel rises over the room, one leaves its colour and returns, one is a room colour by chance."""
    base = room()
    out = np.stack([base] * 4)
    out[1, 3, 2] = (*PALETTE[2], 255)
    out[2, 2, 2] = (*PALETTE[2], 255)
    out[3, 1, 2] = (*PALETTE[2], 255)
    out[1, 0, 5] = (*PALETTE[3], 255)
    out[3, 0, 5] = (*PALETTE[3], 255)  # away on frame 1, back to the room's colour on 2, away again on 3
    out[2, 4, 1] = (*base[4, 1][:3], 0)  # alpha differs at the same RGB: it draws nothing, so it is clear too
    out[1, 4, 3] = base[4, 3]  # explicitly the room's own pixel: clear
    return out


def test_a_strip_is_clear_wherever_a_frame_equals_frame_0(request: pytest.FixtureRequest) -> None:
    source = frames()
    cleared = clear_unchanged(source)
    clear = (source == source[0]).all(axis=3) | (source[..., 3] == 0)
    assert (cleared[clear] == 0).all() and (cleared[~clear] == source[~clear]).all(), "clear is one value, (0, 0, 0, 0)"
    assert (cleared[0] == 0).all(), "frame 0 is the room, which every strip leaves to the Plate"
    assert (source == frames()).all(), "the input is untouched"
    strip = np.concatenate([np.pad(f, ((0, 0), (0, 1), (0, 0))) for f in cleared], axis=1)
    path = EXPECTED / "loop_strip_changed_only.png"
    if request.config.getoption("--update-golden"):
        Image.fromarray(strip, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert strip.shape == expected.shape
    assert (strip == expected).all()
