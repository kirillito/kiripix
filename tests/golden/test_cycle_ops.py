"""The colour cycle Ops (ticket 0188), called directly: rotate and pulse frames compared pixel-exactly with golden PNGs,
and the timing, flash and seam measures checked by what they say."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import (
    cycle_index,
    cycle_pulse,
    cycle_rotate,
    cycle_seam_ratio,
    even_sequence,
    flash_count,
    flicker_sequence,
    ramps,
    seam_ratio,
)

EXPECTED = Path(__file__).parent / "expected"

PALETTE = np.array(
    [
        (16, 14, 24),  # 0 night
        (60, 58, 70),  # 1 grey
        (150, 148, 160),  # 2 light grey
        (120, 30, 40),  # 3 red, dark
        (190, 60, 50),  # 4 red
        (235, 120, 70),  # 5 orange
        (250, 200, 120),  # 6 light orange
        (30, 60, 120),  # 7 blue, dark
        (60, 110, 180),  # 8 blue
        (110, 170, 220),  # 9 light blue
        (190, 230, 250),  # 10 pale blue
    ],
    dtype=np.uint8,
)
TUBE = PALETTE[[3, 4, 5, 6]]


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
    """Frames side by side, a transparent column between them."""
    parts: list[np.ndarray] = []
    for frame in frames:
        if parts:
            parts.append(np.zeros((frame.shape[0], 1, 4), dtype=np.uint8))
        parts.append(frame)
    return np.concatenate(parts, axis=1)


def rgba(rgb: np.ndarray) -> np.ndarray:
    return np.dstack([rgb, np.full(rgb.shape[:2], 255, dtype=np.uint8)])


def neon_tube() -> tuple[np.ndarray, np.ndarray]:
    """16 x 5: a night wall, and a tube of 12 pixels whose colours run red to light orange, three of each."""
    image = rgba(np.broadcast_to(PALETTE[0], (5, 16, 3)).copy())
    for x in range(12):
        image[2, 2 + x, :3] = TUBE[x // 3]
    image[1, 2:14, :3] = PALETTE[1]
    image[3, 2:14, :3] = PALETTE[1]  # the tube's casing
    image[4, 0:3, :3] = TUBE[0]  # a red pixel outside the region: it must not move
    region = np.zeros((5, 16), dtype=bool)
    region[1:4, 2:14] = True
    return image, region


def puddle() -> tuple[np.ndarray, np.ndarray]:
    """12 x 6: a puddle of three blues over night, one pale pixel at the top of its ramp, grey at its rim."""
    image = rgba(np.broadcast_to(PALETTE[0], (6, 12, 3)).copy())
    region = np.zeros((6, 12), dtype=bool)
    region[1:5, 1:11] = True
    image[1:5, 1:11, :3] = PALETTE[7]
    image[2:4, 3:9, :3] = PALETTE[8]
    image[3, 5:7, :3] = PALETTE[9]
    image[1, 10, :3] = PALETTE[10]
    image[4, 1, :3] = PALETTE[2]  # a grey in the region: its own ramp, greys, lighter than any blue
    return image, region


def assert_palette_only(frames: np.ndarray) -> None:
    packed = {tuple(c) for c in PALETTE.tolist()}
    assert {tuple(p) for p in frames[..., :3].reshape(-1, 3).tolist()} <= packed
    assert set(np.unique(frames[..., 3]).tolist()) <= {0, 255}


# cycle_index and cycle_rotate


def test_index_counts_from_one_and_is_zero_outside_the_region_and_off_the_list() -> None:
    image, region = neon_tube()

    index = cycle_index(image, region, TUBE)

    assert index.dtype == np.uint8
    assert index[2, 2] == 1 and index[2, 5] == 2 and index[2, 8] == 3 and index[2, 13] == 4
    assert index[4, 0] == 0, "red, but outside the region"
    assert index[1, 5] == 0, "in the region, not on the list"
    assert index.sum() == 3 * (1 + 2 + 3 + 4)


def test_rotate_steps_each_pixel_one_place_per_frame_and_wraps(request: pytest.FixtureRequest) -> None:
    image, region = neon_tube()
    index = cycle_index(image, region, TUBE)

    frames = cycle_rotate(image, index, TUBE)

    assert frames.shape == (4, 5, 16, 4)
    assert (frames[0] == image).all()
    assert (frames[1, 2, 2, :3] == TUBE[1]).all() and (frames[1, 2, 13, :3] == TUBE[0]).all()
    assert (frames[3, 2, 2, :3] == TUBE[3]).all()
    assert (frames[:, 4, 0] == image[4, 0]).all()
    assert (frames[:, 1] == image[1]).all()
    assert_palette_only(frames)
    assert_golden(request, strip(frames), "cycle_neon_rotate.png")


def test_rotate_takes_the_number_of_frames_asked_for() -> None:
    image, region = neon_tube()
    index = cycle_index(image, region, TUBE)

    frames = cycle_rotate(image, index, TUBE, steps=6)

    assert len(frames) == 6 and (frames[4] == frames[0]).all() and (frames[5] != frames[0]).any()
    assert (frames[4, 2, 2, :3] == TUBE[0]).all() and (frames[5, 2, 2, :3] == TUBE[1]).all()


# ramps and pulse


def test_ramps_group_by_hue_and_order_by_lightness() -> None:
    result = ramps(PALETTE)

    assert result[1] == result[2] == result[0] == (0, 1, 2)
    assert result[3] == result[5] == (3, 4, 5, 6)
    assert result[8] == (7, 8, 9, 10)
    assert result == ramps(PALETTE), "stable for a given palette"
    assert len(result) == len(PALETTE)


def test_pulse_moves_up_the_ramp_and_back_and_stays_at_the_end(request: pytest.FixtureRequest) -> None:
    image, region = puddle()

    frames = cycle_pulse(image, region, PALETTE, depth=2, steps=4)

    assert frames.shape == (4, 6, 12, 4)
    assert (frames[0] == image).all()
    assert (frames[1, 1, 1, :3] == PALETTE[8]).all() and (frames[2, 1, 1, :3] == PALETTE[9]).all()
    assert (frames[3] == frames[1]).all(), "back down the way it came"
    assert (frames[2, 3, 5, :3] == PALETTE[10]).all(), "stops at the end of the ramp"
    assert (frames[:, 1, 10, :3] == PALETTE[10]).all(), "the pale pixel is at the end already"
    assert (frames[2, 4, 1, :3] == PALETTE[2]).all(), "the lightest grey is its ramp's end"
    assert (frames[:, 0] == image[0]).all(), "outside the region"
    assert_palette_only(frames)
    assert_golden(request, strip(frames), "cycle_puddle_pulse.png")


def test_pulse_with_depth_zero_does_not_move() -> None:
    image, region = puddle()

    assert (cycle_pulse(image, region, PALETTE, depth=0, steps=3) == image[None]).all()


# sequences


def test_flicker_is_the_same_every_time_and_sums_to_the_length() -> None:
    first = flicker_sequence(7, [0, 1, 2], mean_ticks=6, spread=0.6, length_ticks=600)

    assert first == flicker_sequence(7, [0, 1, 2], mean_ticks=6, spread=0.6, length_ticks=600)
    assert first != flicker_sequence(8, [0, 1, 2], mean_ticks=6, spread=0.6, length_ticks=600)
    assert sum(t for _, t in first) == 600
    assert first[0][0] == 0
    assert all(a[0] != b[0] for a, b in zip(first, first[1:], strict=False)), "every change is to another frame"
    assert all(3 <= t <= 9 for _, t in first[:-1])
    assert {f for f, _ in first} == {0, 1, 2}


def test_flicker_is_pinned_for_a_seed() -> None:
    """Pinned: a change here means the sequence differs between platforms or versions, and rooms already built differ."""
    assert flicker_sequence(1, [0, 1], 6, 0.5, 40) == [(0, 6), (1, 6), (0, 8), (1, 9), (0, 3), (1, 4), (0, 4)]


def test_flicker_over_one_frame_is_holds_of_that_frame() -> None:
    sequence = flicker_sequence(3, [4], length_ticks=50)

    assert {f for f, _ in sequence} == {4} and sum(t for _, t in sequence) == 50


def test_even_sequence_plain_and_pingpong() -> None:
    assert even_sequence([0, 1, 2], 8) == [(0, 8), (1, 8), (2, 8)]
    assert [f for f, _ in even_sequence([0, 1, 2, 3], 5, pingpong=True)] == [0, 1, 2, 3, 2, 1]
    assert [f for f, _ in even_sequence([0, 1], 5, pingpong=True)] == [0, 1]
    assert even_sequence([0], 5, pingpong=True) == [(0, 5)]


# flash_count


def flashing(frames_per_second_ticks: int, side: int) -> tuple[np.ndarray, list[tuple[int, int]], int]:
    """Two frames, black and white over `side` x `side` of a 64 x 36 image, held `ticks` each."""
    frames = np.zeros((2, 36, 64, 4), dtype=np.uint8)
    frames[..., 3] = 255
    frames[1, :side, :side, :3] = 255
    return frames, [(0, frames_per_second_ticks), (1, frames_per_second_ticks)], side * side


def test_flashing_five_times_a_second_over_a_quarter_of_the_screen_is_counted_and_two_is_not_tripped() -> None:
    frames, sequence, area = flashing(6, 32)  # 10 changes a second: 5 flashes, 1024 of 2304 px
    assert flash_count(frames, sequence, area, 64 * 36) == 5

    frames, sequence, area = flashing(15, 32)  # 4 changes a second: 2 flashes
    assert flash_count(frames, sequence, area, 64 * 36) == 2


def test_a_small_flash_is_not_counted() -> None:
    frames, sequence, area = flashing(6, 6)  # 36 px of 2304: under 2.8 %

    assert flash_count(frames, sequence, area, 64 * 36) == 0


def test_a_change_of_less_than_a_tenth_or_into_bright_light_is_not_a_flash() -> None:
    frames, sequence, area = flashing(6, 32)
    bright = frames.copy()
    bright[0, :32, :32, :3] = 245
    bright[1, :32, :32, :3] = 255  # both above 0.80 relative luminance
    assert flash_count(bright, sequence, area, 64 * 36) == 0
    close = frames.copy()
    close[0, :32, :32, :3] = 120
    close[1, :32, :32, :3] = 125
    assert flash_count(close, sequence, area, 64 * 36) == 0


# seam_ratio


def ramp_frames() -> np.ndarray:
    """Four frames of a 4 x 8 image, each lighting two more columns than the one before."""
    frames = np.zeros((4, 4, 8, 4), dtype=np.uint8)
    frames[..., 3] = 255
    for k in range(4):
        frames[k, :, : 2 * k, :3] = 200
    return frames


def test_a_pingpong_of_smooth_frames_has_a_seam_ratio_of_one() -> None:
    frames = ramp_frames()

    assert seam_ratio(frames, even_sequence([0, 1, 2, 3], 8, pingpong=True)) == 1.0


def test_a_plain_loop_of_smooth_frames_pops_at_the_seam() -> None:
    frames = ramp_frames()

    assert seam_ratio(frames, even_sequence([0, 1, 2, 3], 8)) == 3.0


def test_cycle_seam_is_the_largest_step_over_the_median() -> None:
    ring = PALETTE[[7, 8, 9, 8]]
    jumpy = PALETTE[[7, 8, 9, 10, 3]]

    assert cycle_seam_ratio(jumpy, pingpong=True) == 1.0
    assert cycle_seam_ratio(jumpy) > 2.5
    assert cycle_seam_ratio(ring) < 1.5
