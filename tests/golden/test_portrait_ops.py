"""Golden tests for the portrait's cutout Ops (ticket 0243): a chroma key with a tolerance, the key's spill and a light
sticker rim on the edge, a fast island removal, and a Mask taken to the target grid wide. Small fixed inputs, pixel-exact
expected PNGs (masks shown white on black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import (
    Grid,
    border_colour,
    chroma_key,
    chroma_key_tolerant,
    mask_touching_target,
    remove_key_spill,
    remove_light_rim,
    remove_small_islands,
    remove_small_pieces,
)

EXPECTED = Path(__file__).parent / "expected"
KEY = (30, 238, 24)
RED, WHITE, DARK = (200, 40, 60), (250, 250, 250), (50, 30, 30)


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    if actual.dtype == np.bool_:
        shown = np.zeros((*actual.shape, 4), dtype=np.uint8)
        shown[..., 3] = 255
        shown[actual, :3] = 255
        actual = shown
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def jpeg_figure() -> np.ndarray:
    """20 x 16 of a green that is a few levels off everywhere (a lossy codec's), a red figure in a dark outline with a light
    rim round it, a greenish blend pixel and a stray island of the figure's colour on the background."""
    rgba = np.full((16, 20, 4), 255, dtype=np.uint8)
    rng = np.random.default_rng(7)
    noise = rng.integers(-4, 5, size=(16, 20, 3))
    rgba[..., :3] = np.clip(np.array(KEY) + noise, 0, 255).astype(np.uint8)
    rgba[3:13, 4:16, :3] = WHITE  # the rim
    rgba[4:12, 5:15, :3] = DARK  # the outline
    rgba[5:11, 6:14, :3] = RED
    rgba[3, 3, :3] = (70, 160, 60)  # a blend of the green and the outline, outside the rim
    rgba[1, 17, :3] = RED  # a stray island of one pixel
    rgba[2:4, 1:3, :3] = RED  # and one of four
    return rgba


def test_the_border_colour_is_the_median_of_the_edges() -> None:
    image = jpeg_figure()

    key = border_colour(image, margin=2)

    assert all(abs(a - b) <= 2 for a, b in zip(key, KEY, strict=True))


def test_a_tolerance_clears_what_a_lossy_background_varies_and_an_exact_key_does_not(request: pytest.FixtureRequest) -> None:
    image = jpeg_figure()
    exact = chroma_key(image, KEY)

    cleared = chroma_key_tolerant(image, KEY, 0.06)

    assert (exact[..., 3] == 0).sum() < 20, "an exact key finds almost none of the noisy green"
    assert cleared[0, 0].tolist() == [0, 0, 0, 0]
    assert cleared[8, 10].tolist() == [*RED, 255], "the figure stays"
    assert cleared[8, 5].tolist() == [*DARK, 255]
    assert cleared[3, 3, 3] == 255, "a blend further from the key stays for the spill step"
    assert_golden(request, cleared[..., 3] == 0, "portrait_key_tolerant.png")


def test_a_tolerance_of_zero_is_the_exact_key_and_the_input_is_kept() -> None:
    image = jpeg_figure()
    before = image.copy()

    assert (chroma_key_tolerant(image, KEY, 0) == chroma_key(image, KEY)).all()
    chroma_key_tolerant(image, KEY, 0.1)
    assert (image == before).all()


def test_the_key_s_spill_goes_where_it_touches_the_cleared_background(request: pytest.FixtureRequest) -> None:
    keyed = chroma_key_tolerant(jpeg_figure(), KEY, 0.06)

    cleaned = remove_key_spill(keyed, KEY, reach=3, excess=20)

    assert cleaned[3, 3, 3] == 0, "the green-leaning blend touches the cleared background"
    assert cleaned[8, 10, 3] == 255 and cleaned[8, 4, 3] == 255
    assert (cleaned[..., 3] == 0).sum() == (keyed[..., 3] == 0).sum() + 1
    assert_golden(request, cleaned[..., 3] == 0, "portrait_key_spill.png")


def test_a_grey_key_has_no_spill_and_no_reach_changes_nothing() -> None:
    keyed = chroma_key_tolerant(jpeg_figure(), KEY, 0.06)

    assert (remove_key_spill(keyed, (128, 128, 128)) == keyed).all()
    assert (remove_key_spill(keyed, KEY, reach=0) == keyed).all()


def test_the_light_rim_goes_from_the_background_inward_only_as_far_as_it_reaches(request: pytest.FixtureRequest) -> None:
    keyed = remove_key_spill(chroma_key_tolerant(jpeg_figure(), KEY, 0.06), KEY)
    keyed[8, 10, :3] = WHITE  # the figure's own white, an eye's highlight, far from the background

    cleaned = remove_light_rim(keyed, reach=10)

    assert cleaned[3:13, 4:16, 3][0, :].max() == 0, "the rim row is gone"
    assert cleaned[8, 5, 3] == 255, "the dark outline stops it"
    assert cleaned[8, 10, 3] == 255, "a highlight inside the outline is not reached"
    assert_golden(request, cleaned[..., 3] == 0, "portrait_rim.png")


def test_a_rim_reach_of_one_takes_one_ring_of_the_rim() -> None:
    image = np.zeros((3, 8, 4), dtype=np.uint8)
    image[:, 3:, :3] = WHITE  # a rim three pixels wide, then the figure
    image[:, 6:, :3] = RED
    image[..., 3] = 255
    image[:, :3] = 0

    one = remove_light_rim(image, reach=1)
    three = remove_light_rim(image, reach=3)

    assert one[0, :, 3].tolist() == [0, 0, 0, 0, 255, 255, 255, 255]
    assert three[0, :, 3].tolist() == [0, 0, 0, 0, 0, 0, 255, 255]


def islands() -> np.ndarray:
    mask = np.zeros((14, 20), dtype=np.bool_)
    mask[2:10, 2:10] = True  # 64
    mask[12, 1] = True  # 1
    mask[1, 14:16] = True  # 2
    mask[4, 12] = True  # a pair that touch only on a diagonal
    mask[5, 13] = True
    mask[8:11, 14:17] = True  # 9
    mask[8:11, 17] = True  # joined to the 9: 12 together
    mask[0, 19] = True
    return mask


def test_islands_under_the_size_go_and_diagonal_pieces_join_as_in_remove_small_pieces(request: pytest.FixtureRequest) -> None:
    mask = islands()

    kept = remove_small_islands(mask, 3)

    assert kept[2:10, 2:10].all() and kept[8:11, 14:18].all()
    assert not kept[12, 1] and not kept[1, 14:16].any() and not kept[0, 19]
    assert not kept[4, 12] and not kept[5, 13], "a diagonal pair is two pixels: under 3"
    assert (kept == remove_small_pieces(mask, 3)).all()
    assert_golden(request, kept, "portrait_islands.png")


def test_four_connected_islands_split_a_diagonal_pair_where_eight_joins_it() -> None:
    mask = islands()

    assert remove_small_islands(mask, 3, eight=False)[8:11, 14:18].all()
    pair = np.zeros((6, 6), dtype=np.bool_)
    pair[1, 1] = pair[2, 2] = pair[3, 3] = True
    assert (remove_small_islands(pair, 3) == pair).all()
    assert not remove_small_islands(pair, 3, eight=False).any()


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_remove_small_islands_agrees_with_remove_small_pieces_on_noise(seed: int) -> None:
    rng = np.random.default_rng(seed)
    mask = rng.random((60, 80)) > 0.55

    for size in (0, 1, 2, 5, 40):
        assert (remove_small_islands(mask, size) == remove_small_pieces(mask, size)).all()


def test_remove_small_islands_leaves_the_input_alone() -> None:
    mask = islands()
    before = mask.copy()

    remove_small_islands(mask, 50)

    assert (mask == before).all()


def test_a_region_in_source_pixels_reaches_every_target_cell_it_grazes(request: pytest.FixtureRequest) -> None:
    grid = Grid.cover(24, 16, 6, 4)  # 4 source px per cell
    mask = np.zeros((16, 24), dtype=np.bool_)
    mask[5:7, 9:10] = True  # 2 of the 16 pixels of cell (1, 2)

    wide = mask_touching_target(mask, grid)

    assert wide.shape == (4, 6)
    assert wide[1, 2] and wide.sum() == 1
    assert_golden(request, wide, "portrait_touching.png")
