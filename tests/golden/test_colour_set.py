"""Golden and unit tests for the set-colours Ops: one set of colours chosen over several images, then mapped."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import map_set, set_colours, set_report

EXPECTED = Path(__file__).parent / "expected"


def gradient(shift: int = 0) -> np.ndarray:
    """A 48 x 8 RGBA gradient from deep blue to warm orange, sampled `shift` columns along a longer ramp."""
    x = (np.arange(48) + shift) / 48.0
    ramp = np.stack([30 + 200 * x, 40 + 120 * x * (1 - x) * 4 + 40 * x, 160 - 120 * x], axis=1)
    rgb = np.clip(np.round(ramp), 0, 255).astype(np.uint8)
    out = np.zeros((8, 48, 4), dtype=np.uint8)
    out[..., :3] = rgb[None, :, :]
    out[..., 3] = 255
    out[0, :4] = 0  # a transparent notch
    return out


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    assert (actual == expected).all(), f"{name} differs"


def test_shifted_gradients_map_alike(request: pytest.FixtureRequest) -> None:
    a, b = gradient(0), gradient(1)
    palette = set_colours([a, b], None, 12)
    ma, mb = map_set([a, b], palette)

    # b's column x is a's column x + 1 (the ramp is the same), so matching pixels map to the same colour.
    assert (ma[1:, 1:] == mb[1:, :-1]).all()
    for mapped in (ma, mb):
        assert {tuple(c) for c in mapped[mapped[..., 3] == 255][:, :3]} <= {tuple(c) for c in palette}
    assert_golden(request, np.concatenate([ma, mb], axis=0), "colour_set_shifted.png")


def test_more_colours_lower_the_error() -> None:
    images = [gradient(0), gradient(1)]
    errors = []
    for n in (8, 32):
        palette = set_colours(images, None, n)
        reports = set_report(images, map_set(images, palette))
        errors.append((max(r.mean_error for r in reports), max(r.p95_error for r in reports)))
    assert errors[1][0] < errors[0][0]
    assert errors[1][1] < errors[0][1]


def test_keep_colours_are_in_the_result_first() -> None:
    keep = [(10, 10, 10), (250, 250, 250)]
    palette = set_colours([gradient(0)], None, 6, keep)
    assert len(palette) == 6
    assert [tuple(c) for c in palette[:2]] == keep


def test_order_of_images_changes_nothing() -> None:
    images = [gradient(0), gradient(1), gradient(7)[:, ::-1].copy()]
    first = set_colours(images, None, 10)
    second = set_colours(images[::-1], None, 10)
    assert np.array_equal(first, second)
    assert np.array_equal(first, set_colours(images, None, 10))


def test_every_output_pixel_is_a_set_colour_with_dither() -> None:
    image = gradient(0)
    palette = set_colours([image], None, 4)
    for dither in (0, 2, 4):
        (out,) = map_set([image], palette, dither)  # type: ignore[arg-type]
        opaque = out[..., 3] == 255
        assert {tuple(c) for c in out[opaque][:, :3]} <= {tuple(c) for c in palette}
        assert (out[~opaque] == 0).all()


def test_images_count_equally() -> None:
    big = np.zeros((20, 20, 4), dtype=np.uint8)
    big[..., 3] = 255
    big[..., :3] = (200, 30, 30)
    small = np.zeros((2, 2, 4), dtype=np.uint8)
    small[..., 3] = 255
    small[..., :3] = (30, 30, 200)
    palette = set_colours([big, small], None, 2)
    assert {tuple(c) for c in palette} == {(200, 30, 30), (30, 30, 200)}


def test_partial_alpha_is_refused() -> None:
    image = gradient(0)
    image[3, 3, 3] = 100
    with pytest.raises(ValueError):
        set_colours([image], None, 4)
    with pytest.raises(ValueError):
        map_set([image], np.array([[0, 0, 0]], dtype=np.uint8))


def test_returns_exactly_n_when_centres_collide() -> None:
    # Two heavy near-identical colours and a keep colour that one cluster mean rounds onto.
    image = np.zeros((4, 4, 4), dtype=np.uint8)
    image[..., 3] = 255
    image[..., :3] = (100, 100, 100)
    image[0, 0, :3] = (101, 100, 100)
    image[1, 0, :3] = (250, 20, 20)
    image[2, 0, :3] = (20, 20, 250)
    palette = set_colours([image], None, 4, [(100, 100, 100)])
    assert len(palette) == 4
    assert len({tuple(c) for c in palette}) == 4
    assert tuple(palette[0]) == (100, 100, 100)


def test_fewer_colours_than_n_when_the_images_have_fewer() -> None:
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    image[..., 3] = 255
    image[0, 0, :3] = (9, 9, 9)
    palette = set_colours([image], None, 5)
    assert len(palette) == 2
