"""The frame Ops (ticket 0192), called directly: sway, shimmer and scroll frames compared pixel-exactly with golden PNGs.
Every output pixel exists in the input, frame 0 is the input, and each wave is periodic in its frames."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import scroll, scroll_period, shimmer, sway

EXPECTED = Path(__file__).parent / "expected"

PALETTE = np.array(
    [(16, 14, 24), (60, 58, 70), (30, 120, 60), (70, 180, 90), (60, 110, 180), (110, 170, 220), (190, 230, 250),
     (150, 100, 60)],
    dtype=np.uint8,
)


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


def strip(frames: np.ndarray) -> np.ndarray:
    parts: list[np.ndarray] = []
    for frame in frames:
        if parts:
            parts.append(np.zeros((frame.shape[0], 1, 4), dtype=np.uint8))
        parts.append(frame)
    return np.concatenate(parts, axis=1)


def opaque(rgb: np.ndarray) -> np.ndarray:
    return np.dstack([rgb, np.full(rgb.shape[:2], 255, dtype=np.uint8)])


def plant() -> np.ndarray:
    """A 9 x 12 Layer: a plant (stem and two leaves, in two greens) in a pot, transparent round it."""
    image = np.zeros((12, 9, 4), dtype=np.uint8)
    image[9:12, 2:7] = [*PALETTE[7], 255]  # the pot, at the bottom: the anchor row is 11
    image[2:9, 4] = [*PALETTE[2], 255]  # the stem
    image[1:3, 2:4] = [*PALETTE[3], 255]  # leaves at the top: the far end
    image[1:3, 5:7] = [*PALETTE[3], 255]
    image[5, 3] = [*PALETTE[3], 255]
    image[6, 5] = [*PALETTE[3], 255]
    return image


def puddle() -> tuple[np.ndarray, np.ndarray]:
    """16 x 10: night, a puddle region with bands of blue, and one blue pixel just outside it."""
    image = opaque(np.broadcast_to(PALETTE[0], (10, 16, 3)).copy())
    region = np.zeros((10, 16), dtype=bool)
    region[1:9, 2:14] = True
    for row in range(1, 9):
        image[row, 2:14, :3] = PALETTE[4 + (row % 3 == 0)]
    image[3, 5:8, :3] = PALETTE[6]
    image[4, 1, :3] = PALETTE[5]  # outside the region on the left: it never moves
    return image, region


def window() -> tuple[np.ndarray, np.ndarray]:
    """12 x 10: a window of blue panes and a bright streak, the rain's drops running down it."""
    image = opaque(np.broadcast_to(PALETTE[1], (10, 12, 3)).copy())
    region = np.zeros((10, 12), dtype=bool)
    region[1:9, 2:10] = True
    image[1:9, 2:10, :3] = PALETTE[4]
    for row, column in ((1, 3), (2, 3), (4, 6), (5, 6), (6, 6), (7, 8)):
        image[row, column, :3] = PALETTE[6]
    return image, region


def inputs_of(frames: np.ndarray, image: np.ndarray) -> None:
    packed = {tuple(p) for p in image.reshape(-1, 4).tolist()}
    assert {tuple(p) for p in frames.reshape(-1, 4).tolist()} <= packed | {(0, 0, 0, 0)}, "a pixel not in the input"
    assert (frames[0] == image).all(), "frame 0 is the input"
    assert set(np.unique(frames[..., 3]).tolist()) <= {0, 255}


def test_sway_shears_from_the_anchor_and_moves_the_alpha(request: pytest.FixtureRequest) -> None:
    image = plant()

    frames = sway(image, 11, 2, 4)

    assert frames.shape == (4, 12, 9, 4)
    inputs_of(frames, image)
    assert (frames[:, 11] == image[11]).all(), "the anchor row stays"
    assert (frames[2] == image).all(), "sin(pi) is zero: the half-way frame is at rest"
    assert (frames[1][1:3, 4:6] != image[1:3, 4:6]).any() and (frames[1][..., 3] != image[..., 3]).any()
    assert (frames[1][1, 4:6, 3] == 255).all() and (frames[1][1, 2:4, 3] == 0).all(), "the leaves moved 2 px right"
    assert (frames[3][1, 0:2, 3] == 255).all() and (frames[3][1, 5:7, 3] == 0).all(), "and 2 px left"
    assert_golden(request, strip(frames), "sway_plant.png")


def test_sway_at_its_defaults_is_periodic_and_moves_only_the_far_rows() -> None:
    image = plant()

    frames = sway(image, 11)

    assert frames.shape[0] == 4
    inputs_of(frames, image)
    assert (frames[0] == frames[2]).all()
    assert (frames[1] != image).any() and (frames[3] != image).any() and (frames[1] != frames[3]).any()


def test_sway_refuses_an_anchor_outside_the_image() -> None:
    with pytest.raises(ValueError):
        sway(plant(), 12)


def test_shimmer_moves_rows_inside_the_region_only(request: pytest.FixtureRequest) -> None:
    image, region = puddle()

    frames = shimmer(image, region, 1, 6, 6)

    assert frames.shape == (6, 10, 16, 4)
    inputs_of(frames, image)
    for frame in frames:
        assert (frame[~region] == image[~region]).all(), "outside the region nothing moves"
    inside = {tuple(p) for p in image[region].tolist()}
    assert {tuple(p) for p in frames[:, region].reshape(-1, 4).tolist()} <= inside, "taken from inside the region"
    assert (frames[1] != image).any()
    assert_golden(request, strip(frames), "shimmer_puddle.png")


def test_scroll_wraps_inside_the_regions_box_and_is_masked(request: pytest.FixtureRequest) -> None:
    image, region = window()

    frames = scroll(image, region, 0, 1)

    assert frames.shape == (8, 10, 12, 4), "the period of a wrap of 8 rows at one a frame is 8"
    inputs_of(frames, image)
    for frame in frames:
        assert (frame[~region] == image[~region]).all()
    assert (frames[1][2:9, 3] == image[1:8, 3]).all() and (frames[1][1, 3] == image[8, 3]).all()
    assert_golden(request, strip(frames), "scroll_window.png")


def test_scroll_period_is_the_lcm_of_the_wraps_and_frames_can_be_given() -> None:
    assert scroll_period(8, 8, 0, 1) == 8
    assert scroll_period(8, 6, 2, 3) == 4
    assert scroll_period(8, 6, 4, 2) == 6
    image, region = window()
    assert scroll(image, region, 1, 0, 3).shape[0] == 3
    with pytest.raises(ValueError):
        scroll_period(8, 8, 0, 0)
