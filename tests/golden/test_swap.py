"""Golden test for the ramp swap Op (ticket 0337): a 12 x 6 frame with two Parts, skin and hair, and a fixed colour."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import swap_ramps

EXPECTED = Path(__file__).parent / "expected"
SKIN = [(120, 70, 50), (200, 140, 110), (250, 210, 180)]
HAIR = [(30, 20, 10), (90, 60, 30), (160, 110, 60)]
NEW_HAIR = [(10, 10, 60), (40, 40, 150), (120, 120, 240)]
FIXED = (20, 160, 40)


def frame() -> np.ndarray:
    image = np.zeros((6, 12, 4), dtype=np.uint8)
    for step in range(3):
        image[0:3, step * 2: step * 2 + 2] = (*SKIN[step], 255)  # skin, three steps
        image[3:6, step * 2: step * 2 + 2] = (*HAIR[step], 255)  # hair, three steps
    image[0:3, 8:12] = (*FIXED, 255)  # a colour no ramp holds
    image[3:6, 8:10] = (*HAIR[1], 128)  # a hair colour at half alpha: still swapped, alpha kept
    return image


def test_a_ramp_is_swapped_step_for_step_and_nothing_else_changes(request: pytest.FixtureRequest) -> None:
    before = frame()

    out = swap_ramps(before, [(HAIR, NEW_HAIR)])

    path = EXPECTED / "swap_ramps.png"
    if request.config.getoption("--update-golden"):
        Image.fromarray(out, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert out.shape == expected.shape and not (out != expected).any()
    assert (out[3:6, 0:2] == (*NEW_HAIR[0], 255)).all() and (out[3:6, 4:6] == (*NEW_HAIR[2], 255)).all()
    assert (out[3:6, 8:10] == (*NEW_HAIR[1], 128)).all()
    assert (out[0:3] == before[0:3]).all(), "the skin and the fixed colour are not touched"
    assert (before == frame()).all(), "the input is not modified"


def test_swaps_apply_to_the_input_colours_not_to_each_others_results() -> None:
    image = frame()

    out = swap_ramps(image, [(HAIR, SKIN), (SKIN, HAIR)])  # exchange the two Parts

    assert (out[0, 0, :3] == HAIR[0]).all() and (out[3, 0, :3] == SKIN[0]).all()


def test_a_ramp_of_another_length_is_refused() -> None:
    with pytest.raises(ValueError):
        swap_ramps(frame(), [(HAIR, NEW_HAIR[:2])])
