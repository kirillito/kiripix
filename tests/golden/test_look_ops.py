"""The Look Ops (ticket 0130), called directly: registration of an edit that was rescaled and shifted, the region a
difference picks out, the drift outside a region and the regrade. Images are compared pixel-exactly with golden PNGs;
what is measured is asserted next to them."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import (
    Alignment,
    dilate,
    difference_map,
    difference_region,
    drift_boxes,
    mask_box,
    regrade,
    register,
    resize_nearest,
    srgb_to_oklab,
    warp_nearest,
)

EXPECTED = Path(__file__).parent / "expected"


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


def as_mask_image(*masks: np.ndarray) -> np.ndarray:
    """Masks side by side, separated by a grey column, as an opaque black and white image."""
    parts: list[np.ndarray] = []
    for mask in masks:
        if parts:
            parts.append(np.full((mask.shape[0], 1, 4), (90, 90, 90, 255), dtype=np.uint8))
        grey = np.where(mask, 255, 0).astype(np.uint8)
        parts.append(np.dstack([grey, grey, grey, np.full_like(grey, 255)]))
    return np.concatenate(parts, axis=1)


_TERMS = [(0.031, 0.047, 0.5, 1.3, 22), (0.052, 0.029, 2.1, 0.4, 18), (0.083, 0.071, 4.0, 2.2, 14),
          (0.027, 0.095, 1.1, 5.0, 16), (0.110, 0.043, 3.3, 0.9, 12), (0.064, 0.118, 5.2, 3.1, 10),
          (0.039, 0.036, 0.2, 2.8, 20), (0.097, 0.088, 2.7, 4.4, 9), (0.021, 0.074, 3.9, 1.7, 15),
          (0.071, 0.052, 1.5, 5.6, 11), (0.045, 0.101, 0.8, 0.2, 13), (0.089, 0.023, 4.6, 3.6, 8)]


def texture(scale: float, shift_x: float, shift_y: float, width: int = 384, height: int = 256) -> np.ndarray:
    """A smooth grey texture sampled where `edit_x = scale * room_x + shift_x`: scale 1 and shift 0 is the room itself.
    The texture is a fixed sum of sine waves, so any scale and shift is exact (no interpolation)."""
    x = (np.arange(width)[None, :] - shift_x) / scale
    y = (np.arange(height)[:, None] - shift_y) / scale
    value = np.full((height, width), 128.0)
    for fx, fy, px, py, amplitude in _TERMS:
        value += amplitude * np.sin(fx * x + px) * np.sin(fy * y + py)
    grey = np.round(np.clip(value, 0, 255)).astype(np.uint8)
    return np.dstack([grey, grey, grey, np.full_like(grey, 255)])


# register


def test_registration_recovers_a_one_percent_scale_and_a_three_pixel_shift(request: pytest.FixtureRequest) -> None:
    room = texture(1.0, 0, 0)
    edit = texture(1.01, 3.0, 2.0)

    alignment = register(room, edit, tile=64)

    assert alignment.tiles >= 20
    # the answer is judged where it matters: how far each pixel of the frame is from where the edit really has it
    for x in (0, 383):
        assert abs((alignment.scale_x - 1.01) * x + (alignment.shift_x - 3.0)) < 0.15
    for y in (0, 255):
        assert abs((alignment.scale_y - 1.01) * y + (alignment.shift_y - 2.0)) < 0.15
    aligned = warp_nearest(edit, alignment)
    assert np.abs(aligned[..., :3].astype(int) - room[..., :3]).mean() < 4  # was 9.4 sources of 255 unaligned
    assert_golden(request, aligned, "look_registered.png")


def test_registration_leaves_an_edit_that_is_the_room_itself_untouched() -> None:
    room = texture(1.0, 0, 0)
    alignment = register(room, texture(1.0, 0.02, -0.01), tile=64)

    assert alignment.tiles >= 20 and alignment.negligible(384, 256)
    edit = texture(1.0, 0.02, -0.01)
    assert warp_nearest(edit, alignment) is edit  # nothing moves by a quarter pixel: not resampled at all


def test_registration_ignores_tiles_the_edit_is_meant_to_change() -> None:
    room = texture(1.0, 0, 0)
    edit = texture(1.0, 0, 0)
    edit[:128, :192] = 255 - edit[:128, :192]  # redrawn: its tiles would say something else
    exclude = np.zeros(room.shape[:2], dtype=bool)
    exclude[:128, :192] = True

    alignment = register(room, edit, exclude, tile=64)

    assert alignment.negligible(384, 256) and alignment.tiles >= 12


def test_registration_gives_the_identity_when_there_is_too_little_texture() -> None:
    flat = np.full((256, 384, 4), 120, dtype=np.uint8)

    assert register(flat, flat, tile=64) == Alignment()


def test_registration_is_the_same_every_time() -> None:
    room, edit = texture(1.0, 0, 0), texture(0.995, -2.0, 1.0)

    assert register(room, edit, tile=64) == register(room, edit, tile=64)


def test_resizing_picks_pixels_and_never_blends() -> None:
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    image[0, 0] = (255, 0, 0, 255)
    image[1, 1] = (0, 0, 255, 255)

    bigger = resize_nearest(image, 4, 4)
    smaller = resize_nearest(bigger, 2, 2)

    assert (bigger[:2, :2] == image[0, 0]).all() and (bigger[2:, 2:] == image[1, 1]).all()
    assert (smaller == image).all()
    assert len({tuple(p) for p in bigger.reshape(-1, 4)}) == 3


# difference and drift


def room_image() -> np.ndarray:
    """40 x 24: a smooth gradient with a flat patch to redraw."""
    x = np.arange(40)[None, :]
    y = np.arange(24)[:, None]
    grey = (90 + 3 * x + 2 * y).astype(np.uint8)
    image = np.dstack([grey, grey, np.minimum(grey + 20, 255).astype(np.uint8), np.full_like(grey, 255)])
    return image


def noisy(image: np.ndarray, seed: int = 5) -> np.ndarray:
    """The model's re-render: every pixel nudged by a level or two."""
    rng = np.random.default_rng(seed)
    result = image.astype(np.int16)
    result[..., :3] += rng.integers(-2, 3, size=result[..., :3].shape)
    return np.clip(result, 0, 255).astype(np.uint8)


def test_a_difference_picks_out_a_changed_patch_and_not_the_noise_around_it(request: pytest.FixtureRequest) -> None:
    room = room_image()
    edit = noisy(room)
    edit[6:14, 10:20] = (200, 40, 40, 255)  # the redraw: a patch of 8 x 10
    edit[18, 34] = (255, 255, 255, 255)  # a speck

    region = difference_region(room, edit, (0, 0, 39, 23), tolerance=4.0, specks=4)

    assert region[8:12, 12:18].all(), "the heart of the patch is in"
    ys, xs = np.nonzero(region)
    assert ys.min() >= 5 and ys.max() <= 14 and xs.min() >= 9 and xs.max() <= 20, "no more than the 3x3 mean spreads"
    assert not region[18, 34], "a one pixel speck is dropped"
    assert not region[:4].any() and not region[:, 25:].any(), "the noise is below the tolerance"
    assert_golden(request, as_mask_image(region, difference_region(room, edit, (0, 0, 39, 23), 4.0, 0)),
                  "look_difference.png")


def test_a_difference_stays_inside_its_box() -> None:
    room = room_image()
    edit = room.copy()
    edit[6:14, 10:20] = (200, 40, 40, 255)

    region = difference_region(room, edit, (0, 0, 14, 23), tolerance=4.0, specks=0)

    assert region[:, :15].any() and not region[:, 15:].any()


def test_the_difference_of_two_equal_images_is_nothing_and_transparent_pixels_have_none() -> None:
    room = room_image()
    edit = room.copy()
    edit[0:3, 0:3] = (0, 0, 0, 0)

    assert not difference_map(room, room).any()
    assert not difference_map(room, edit).any()


def test_drift_lists_redraw_outside_the_region_largest_first() -> None:
    room = room_image()
    edit = room.copy()
    edit[6:14, 10:20] = (200, 40, 40, 255)  # inside the region
    edit[2:8, 28:36] = (40, 200, 40, 255)  # a larger redraw outside
    edit[18:21, 3:7] = (40, 40, 200, 255)  # a smaller one
    edit[22, 22] = (255, 255, 255, 255)  # a speck
    region = np.zeros(room.shape[:2], dtype=bool)
    region[4:16, 8:22] = True

    drift = drift_boxes(room, edit, region, tolerance=8.0, min_size=16)

    assert [d.pixels for d in drift] == sorted((d.pixels for d in drift), reverse=True)
    assert len(drift) == 2
    first, second = drift
    assert 27 <= first.x <= 28 and first.x + first.width >= 36 and first.y <= 2
    assert second.x <= 3 and second.y <= 18 and second.pixels < first.pixels


def test_noise_is_not_drift() -> None:
    room = room_image()

    assert drift_boxes(room, noisy(room), np.zeros(room.shape[:2], dtype=bool), tolerance=8.0, min_size=16) == []


def test_mask_box_and_dilate() -> None:
    mask = np.zeros((10, 12), dtype=bool)
    assert mask_box(mask) is None
    mask[3:5, 4:8] = True

    grown = dilate(mask, 2)

    assert mask_box(mask) == (4, 3, 4, 2)
    assert mask_box(grown) == (2, 1, 8, 6) and grown.sum() == 48


# regrade


def test_regrade_matches_the_edits_light_to_the_room_outside_the_region(request: pytest.FixtureRequest) -> None:
    room = room_image()
    darker = np.clip(room.astype(np.int16) * 0.85 - 4, 0, 255).astype(np.uint8)
    darker[..., 3] = 255
    exclude = np.zeros(room.shape[:2], dtype=bool)
    exclude[6:14, 10:20] = True
    darker[6:14, 10:20] = (200, 40, 40, 255)  # the Look itself, which the regrade must not undo

    graded = regrade(room, darker, exclude)

    def error(image: np.ndarray) -> float:
        delta = srgb_to_oklab(image[..., :3][~exclude]) - srgb_to_oklab(room[..., :3][~exclude])
        return float(np.sqrt((delta**2).sum(axis=-1)).mean() * 100)

    assert error(darker) > 4 and error(graded) < error(darker) / 3
    assert (graded[..., 3] == 255).all()
    patch = graded[6:14, 10:20].astype(int)
    assert (patch[..., 0] > patch[..., 1] + 100).all()  # still red, though the gain lifts it a little
    assert_golden(request, np.concatenate([darker, graded], axis=1), "look_regrade.png")


def test_regrade_with_nothing_to_fit_changes_nothing() -> None:
    room = room_image()
    everything = np.ones(room.shape[:2], dtype=bool)

    edit = noisy(room)

    assert regrade(room, edit, everything) is edit
    assert np.abs(regrade(room, room, None).astype(int) - room).max() <= 1  # the identity fit, through OKLab and back
