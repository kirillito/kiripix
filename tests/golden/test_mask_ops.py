"""The mask Ops, called directly: flood fill, brush strokes, splitting a painted image and the cell snap, compared
pixel-exactly with golden PNGs (a set pixel is white, a clear one black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import flood_region, paint_stroke, snap_cell, split_painted

EXPECTED = Path(__file__).parent / "expected"

RED, YELLOW, CYAN = (255, 0, 0), (255, 255, 0), (0, 255, 255)
GREY, BLUE = (90, 90, 90, 255), (40, 60, 200, 255)


def as_image(*masks: np.ndarray) -> np.ndarray:
    """Masks side by side, separated by a grey column, as an opaque black and white image."""
    height = masks[0].shape[0]
    parts: list[np.ndarray] = []
    for mask in masks:
        if parts:
            parts.append(np.full((height, 1, 4), GREY, dtype=np.uint8))
        grey = np.where(mask, 255, 0).astype(np.uint8)
        parts.append(np.dstack([grey, grey, grey, np.full_like(grey, 255)]))
    return np.concatenate(parts, axis=1)


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


def plate() -> np.ndarray:
    """16 x 10: a blue wall with a ring, a hole in it, and a floor split by a diagonal-touching pixel."""
    image = np.full((10, 16, 4), (200, 190, 170, 255), dtype=np.uint8)
    image[:, :5] = BLUE
    image[2:7, 7:13] = BLUE
    image[3:6, 8:12] = (200, 190, 170, 255)  # a floor inside the ring
    image[4, 9] = BLUE  # a region of its own, inside the floor
    image[8, 14] = (0, 0, 0, 0)  # a transparent pixel
    image[9, 15] = (9, 9, 9, 0)  # another one: transparent is a single colour
    return image


# flood


def test_flood_takes_the_four_connected_region_of_equal_colour(request: pytest.FixtureRequest) -> None:
    image = plate()

    wall = flood_region(image, 0, 0)
    floor = flood_region(image, 6, 9)
    inside = flood_region(image, 8, 3)
    corner = flood_region(image, 15, 9)

    assert wall.sum() == 50 and not wall[:, 5:].any()
    assert not (wall & floor).any() and floor[0, 5] and not floor[3, 8]
    assert inside.sum() == 3 * 4 - 1 and not inside[4, 9] and not inside[0, 5]
    assert corner.sum() == 1 and corner[9, 15]
    assert_golden(request, as_image(wall, floor, inside, flood_region(image, 9, 4)), "mask_flood.png")


def test_flood_is_not_connected_through_a_diagonal() -> None:
    image = plate()

    assert flood_region(image, 15, 9).sum() == 1 and flood_region(image, 14, 8).sum() == 1


def test_flood_outside_the_image_is_refused() -> None:
    with pytest.raises(ValueError, match="outside"):
        flood_region(plate(), 16, 0)


def test_flood_does_not_change_its_input() -> None:
    image = plate()
    before = image.copy()

    flood_region(image, 0, 0)

    assert (image == before).all()


# brush


def test_a_brush_stroke_and_an_erase(request: pytest.FixtureRequest) -> None:
    empty = np.zeros((12, 20), dtype=np.bool_)

    stroke = paint_stroke(empty, [(2, 2), (10, 2), (16, 9)], radius=1)
    erased = paint_stroke(stroke, [(0, 2), (19, 2)], radius=0, erase=True)
    dot = paint_stroke(empty, [(19, 11)], radius=2)

    assert not empty.any()  # the input is not changed
    assert stroke[2, 2] and stroke[3, 10] and stroke[9, 16] and not stroke[11, 2]
    assert not erased[2, 2] and not erased[2, 10] and erased[3, 10] and erased[1, 10]
    assert dot[11, 19] and dot[9, 19] and dot[11, 17] and not dot[9, 17]  # a disc, clipped at the edge
    assert_golden(request, as_image(stroke, erased, dot), "mask_brush.png")


def test_a_radius_0_stroke_is_a_bresenham_line_and_one_point_is_one_pixel() -> None:
    empty = np.zeros((5, 5), dtype=np.bool_)

    line = paint_stroke(empty, [(0, 0), (4, 2)], radius=0)
    point = paint_stroke(empty, [(2, 2)], radius=0)

    assert np.argwhere(line).tolist() == [[0, 0], [1, 1], [1, 2], [2, 3], [2, 4]]
    assert np.argwhere(point).tolist() == [[2, 2]]


def test_a_stroke_outside_the_mask_is_clipped_and_a_negative_radius_refused() -> None:
    empty = np.zeros((4, 4), dtype=np.bool_)

    assert paint_stroke(empty, [(-3, -3), (1, 1)], radius=0).sum() == 2
    with pytest.raises(ValueError, match="radius"):
        paint_stroke(empty, [(0, 0)], radius=-1)
    with pytest.raises(ValueError, match="Mask"):
        paint_stroke(np.zeros((4, 4), dtype=np.uint8), [(0, 0)], radius=0)


# splitting a painted image


def painted() -> np.ndarray:
    """16 x 8: red `solid`, yellow (the import colour: `solid`), cyan `oneway`, blank, and one stray pixel."""
    image = np.zeros((8, 16, 4), dtype=np.uint8)
    image[1:4, 1:6] = (*RED, 255)
    image[5:7, 2:14] = (*YELLOW, 255)
    image[1:3, 9:14] = (*CYAN, 255)
    image[2, 3] = (230, 20, 25, 255)  # off-colour inside the red: snaps to red
    image[6, 8] = (250, 240, 60, 255)  # off-colour inside the yellow: snaps to yellow
    return image


def test_a_painted_image_splits_into_masks_with_the_import_colour_setting_solid(request: pytest.FixtureRequest) -> None:
    defined = [(RED, ["solid"]), (CYAN, ["oneway"]), (YELLOW, ["solid"])]

    masks = split_painted(painted(), defined)

    assert list(masks) == ["solid", "oneway"]
    assert masks["solid"][2, 3] and masks["solid"][6, 8]  # the stray pixels snapped
    assert masks["solid"].sum() == 15 + 24 and masks["oneway"].sum() == 10
    assert not (masks["solid"] & masks["oneway"]).any()
    assert not masks["solid"][0].any() and not masks["solid"][4].any()  # transparent pixels set nothing
    assert_golden(request, as_image(masks["solid"], masks["oneway"]), "mask_split.png")


def test_one_import_colour_may_set_several_masks_and_an_unpainted_mask_is_empty() -> None:
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    image[0, 0] = (*YELLOW, 255)

    masks = split_painted(image, [(RED, ["solid"]), (YELLOW, ["solid", "ladder"]), (CYAN, ["oneway"])])

    assert list(masks) == ["solid", "ladder", "oneway"]
    assert masks["solid"].tolist() == masks["ladder"].tolist() == [[True, False], [False, False]]
    assert not masks["oneway"].any()


def test_a_colour_equally_near_two_defined_colours_goes_to_the_first() -> None:
    image = np.full((1, 1, 4), (10, 20, 30, 255), dtype=np.uint8)

    first = split_painted(image, [((0, 0, 0), ["a"]), ((0, 0, 0), ["b"])])
    swapped = split_painted(image, [((0, 0, 0), ["b"]), ((0, 0, 0), ["a"])])

    assert first["a"].all() and not first["b"].any()
    assert swapped["b"].all() and not swapped["a"].any()


def test_nearness_is_in_oklab_not_rgb() -> None:
    """Mid grey is nearer to white in RGB (220.0 against 221.1) but nearer to red in OKLab (0.259 against 0.400)."""
    pixel = np.full((1, 1, 4), (128, 128, 128, 255), dtype=np.uint8)

    masks = split_painted(pixel, [((255, 255, 255), ["white"]), ((255, 0, 0), ["red"])])

    assert masks["red"].all() and not masks["white"].any()


def test_a_painted_image_with_partial_alpha_is_refused() -> None:
    image = np.zeros((1, 2, 4), dtype=np.uint8)
    image[0, 0] = (*RED, 128)

    with pytest.raises(ValueError, match="partial alpha"):
        split_painted(image, [(RED, ["solid"])])


def test_a_fully_transparent_image_gives_empty_masks() -> None:
    masks = split_painted(np.zeros((3, 3, 4), dtype=np.uint8), [(RED, ["solid"])])

    assert masks["solid"].shape == (3, 3) and not masks["solid"].any()


# the cell snap


def test_a_cell_snap_sets_cells_that_are_at_least_half_set(request: pytest.FixtureRequest) -> None:
    mask = np.zeros((10, 14), dtype=np.bool_)
    mask[0:3, 0:3] = True  # 9 of 16: set
    mask[0:2, 4:8] = True  # 8 of 16: a tie, set
    mask[4:7, 4:6] = True  # 6 of 16: clear
    mask[8:10, 12:14] = True  # the 2x2 edge cell is full: set
    mask[8, 8] = True  # 1 of 8 in the edge cell: clear

    snapped = snap_cell(mask, 4)

    assert snapped[0:4, 0:4].all() and snapped[0:4, 4:8].all() and not snapped[4:8, 4:8].any()
    assert snapped[8:10, 12:14].all() and not snapped[8:10, 8:12].any()
    assert snapped.sum() == 16 + 16 + 4
    assert_golden(request, as_image(mask, snapped), "mask_snap.png")


def test_a_cell_of_0_or_1_changes_nothing_and_a_negative_one_is_refused() -> None:
    mask = np.eye(5, dtype=np.bool_)

    assert (snap_cell(mask, 0) == mask).all() and (snap_cell(mask, 1) == mask).all()
    with pytest.raises(ValueError, match="cell"):
        snap_cell(mask, -1)
