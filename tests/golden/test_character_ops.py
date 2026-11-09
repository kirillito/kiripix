"""Golden tests for the character's palette subset and normal-map Ops (ticket 0107).

Small fixed inputs, expected PNGs compared pixel-exactly. `--update-golden` rewrites them; review by eye.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import encode_normals, palette_subset, quantise_normals, quantize

EXPECTED = Path(__file__).parent / "expected"

PALETTE = np.array(
    [
        [200, 40, 40],  # 0 red
        [120, 20, 20],  # 1 dark red
        [40, 40, 200],  # 2 blue
        [20, 20, 120],  # 3 dark blue
        [30, 200, 30],  # 4 green, unused by the frames
    ],
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


def frame(rows: list[list[int]], colours: dict[int, tuple[int, int, int]]) -> np.ndarray:
    """A frame from a grid of keys; key 0 is transparent."""
    out = np.zeros((len(rows), len(rows[0]), 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, key in enumerate(row):
            if key:
                out[y, x] = (*colours[key], 255)
    return out


def two_frames() -> tuple[np.ndarray, np.ndarray]:
    # Frame A is mostly red with a little dark red; frame B is mostly blue with a little dark blue. Left to
    # themselves, each would keep its own pair of palette colours (four in all) for two colours each.
    a = frame(
        [[1, 1, 1, 1, 0, 0], [1, 1, 1, 2, 2, 0], [1, 1, 2, 2, 2, 0], [0, 0, 0, 0, 0, 0]],
        {1: (205, 45, 40), 2: (110, 25, 20)},
    )
    b = frame(
        [[0, 0, 1, 1, 1, 1], [0, 1, 1, 1, 2, 2], [0, 1, 1, 2, 2, 2], [0, 0, 0, 0, 0, 0]],
        {1: (35, 45, 205), 2: (25, 20, 115)},
    )
    return a, b


def test_a_shared_subset_gives_every_frame_the_same_colours(request: pytest.FixtureRequest) -> None:
    a, b = two_frames()

    subset = palette_subset([a, b], PALETTE, 2)
    mapped = [quantize(f, subset) for f in (a, b)]

    # Each frame alone would take two colours of its own: A red and dark red, B blue and dark blue.
    alone_a, alone_b = palette_subset([a], PALETTE, 2), palette_subset([b], PALETTE, 2)
    assert alone_a.tolist() == PALETTE[[0, 1]].tolist()
    assert alone_b.tolist() == PALETTE[[2, 3]].tolist()
    # Together, both frames draw on one subset of two colours, in palette order, and nothing else appears.
    assert subset.tolist() == PALETTE[[0, 2]].tolist()
    for m in mapped:
        used = {tuple(p) for p in m[m[..., 3] == 255][:, :3].tolist()}
        assert used <= {tuple(c) for c in subset.tolist()}
    assert (quantize(a, alone_a) != mapped[0]).any()
    assert_golden(request, np.concatenate(mapped, axis=1), "character_subset_frames.png")


def test_the_subset_is_in_palette_order_and_ties_go_to_the_earlier_colour() -> None:
    # Two colours exactly between palette entries 0 and 1 (identical palette colours): the earlier one wins.
    palette = np.array([[10, 10, 10], [200, 200, 200], [10, 10, 10]], dtype=np.uint8)
    f = np.zeros((1, 2, 4), dtype=np.uint8)
    f[0, 0] = (10, 10, 10, 255)
    f[0, 1] = (200, 200, 200, 255)

    assert palette_subset([f], palette, 2).tolist() == [[10, 10, 10], [200, 200, 200]]
    assert palette_subset([f], palette, 9).tolist() == palette.tolist()


def test_only_opaque_pixels_count_and_an_empty_character_takes_the_first_colours() -> None:
    clear = np.zeros((2, 2, 4), dtype=np.uint8)
    clear[..., :3] = PALETTE[4]  # transparent, so it must not pull in the green
    a, _ = two_frames()

    assert palette_subset([clear], PALETTE, 2).tolist() == PALETTE[:2].tolist()
    assert 4 not in [PALETTE.tolist().index(c) for c in palette_subset([a, clear], PALETTE, 2).tolist()]
    with pytest.raises(ValueError):
        palette_subset([a], PALETTE, 0)


def normal_pass() -> np.ndarray:
    """A 4 x 4 pass: a dome-ish gradient, a back-facing normal, a flat one and two transparent pixels."""
    out = np.zeros((4, 4, 4), dtype=np.uint8)
    for y in range(4):
        for x in range(4):
            v = np.array([(x - 1.5) / 2.0, -(y - 1.5) / 2.0, 0.0])
            v[2] = np.sqrt(max(0.0, 1.0 - v[0] ** 2 - v[1] ** 2))
            v /= np.linalg.norm(v)
            out[y, x] = (*np.floor((v * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8), 255)
    out[0, 0] = (200, 128, 20, 255)  # facing away from the camera
    out[1, 1] = (128, 128, 255, 255)  # flat
    out[3, 3] = 0
    out[3, 0] = 0
    return out


@pytest.mark.parametrize(("levels", "name"), [(1, "normals_levels1.png"), (3, "normals_levels3.png"),
                                              (255, "normals_levels255.png")])
def test_quantise_normals(request: pytest.FixtureRequest, levels: int, name: str) -> None:
    source = normal_pass()

    result = quantise_normals(source, levels)

    assert_golden(request, result, name)
    clear = source[..., 3] == 0
    assert (result[clear] == 0).all()
    assert (result[~clear][:, 3] == 255).all()


def test_one_level_is_a_flat_map_and_more_levels_use_more_values() -> None:
    source = normal_pass()
    flat = quantise_normals(source, 1)
    opaque = source[..., 3] == 255

    assert {tuple(p) for p in flat[opaque].tolist()} == {(128, 128, 255, 255)}
    few = {tuple(p) for p in quantise_normals(source, 3)[opaque][:, :3].tolist()}
    many = {tuple(p) for p in quantise_normals(source, 255)[opaque][:, :3].tolist()}
    assert len(few) < len(many)


def test_quantised_normals_have_unit_length() -> None:
    source = normal_pass()
    out = quantise_normals(source, 3)
    vectors = out[..., :3].astype(np.float64) / 255 * 2 - 1
    length = np.sqrt((vectors**2).sum(axis=-1))[source[..., 3] == 255]

    assert np.abs(length - 1).max() < 0.02


def test_normals_refuse_partial_alpha() -> None:
    source = normal_pass()
    source[0, 1, 3] = 100
    with pytest.raises(ValueError):
        quantise_normals(source, 3)
    with pytest.raises(ValueError):
        encode_normals(source)


def test_encode_normals(request: pytest.FixtureRequest) -> None:
    source = normal_pass()

    result = encode_normals(source)

    assert_golden(request, result, "normals_encoded.png")
    assert (result[source[..., 3] == 0] == 0).all()
    assert tuple(result[1, 1]) == (128, 128, 255, 255)
    # The back-facing normal loses its Z (stored as 0.5 -> 128 would be wrong; it is clamped to 0, byte 128).
    assert result[0, 0, 2] == 128
    # Axes are not flipped: more red input stays more red.
    assert result[0, 0, 0] > 128
