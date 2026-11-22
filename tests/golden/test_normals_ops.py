"""The normals Ops (ticket 0341, ADR 0014), called directly on a box on a floor and compared pixel-exactly with golden PNGs:
the room's normal map from a height (the Plate's, and a Layer's refilled over its alpha), flatten, and the room lit from a
corner. A flat pixel is (128, 128, 255), the floor stays exactly flat, and nothing is palette-mapped."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops.normals import cell_means, encode, flatten, front_normals, heights, lit, masked_fill, tilt_of, tilts

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


def box_on_floor() -> np.ndarray:
    """A 40 x 28 depth: a floor at 0 and a box, x 12 to 27 and y 6 to 17, standing 1.0 above it (nearer is bigger)."""
    depth = np.zeros((28, 40), dtype=np.float32)
    depth[6:18, 12:28] = 1.0
    return depth


def wall_and_box() -> np.ndarray:
    """The box on the floor, and a wall, three times the box's height, on the room's left edge."""
    depth = box_on_floor()
    depth[:, :6] = 3.0
    return depth


def box_alpha() -> np.ndarray:
    alpha = np.zeros((28, 40), dtype=np.bool_)
    alpha[6:18, 12:28] = True  # a Layer that is the box exactly
    return alpha


def test_the_floor_is_exactly_flat_and_the_box_catches_the_light_from_its_sides(request: pytest.FixtureRequest) -> None:
    normal = front_normals(heights(box_on_floor(), 6.0), [], 0.10, 3)

    assert (normal[0, 0] == (128, 128, 255, 255)).all() and (normal[..., 3] == 255).all()
    assert (normal[12, 20] == (128, 128, 255, 255)).all(), "the box's top is flat too"
    assert normal[12, 12, 0] < 128 and normal[12, 27, 0] > 128, "its left face tilts left, its right face tilts right"
    assert normal[6, 20, 1] > 128 and normal[17, 20, 1] < 128, "Y is up: the box's top edge faces up, its bottom edge down"
    assert_golden(request, normal, "normals_box.png")


def test_a_layers_normals_come_from_the_height_refilled_outside_its_alpha(request: pytest.FixtureRequest) -> None:
    height = heights(wall_and_box(), 6.0)
    plain = front_normals(height, [], 0.10, 3)
    layered = front_normals(height, [box_alpha()], 0.10, 3)

    alpha = box_alpha()
    assert (layered[~alpha] == plain[~alpha]).all(), "outside the Layer's alpha the Plate's normals stay"
    assert (tilt_of(plain)[alpha] > 0.4).any(), "the Plate's own normals tilt at the box's edge"
    assert (layered[alpha] == (128, 128, 255, 255)).all(), "refilled from the box's own height, the Layer has no step at its cut"
    assert_golden(request, layered, "normals_box_layer.png")


def test_flatten_makes_the_normals_face_the_camera_and_lit_keeps_flat_pixels_as_they_were(request: pytest.FixtureRequest) -> None:
    normal = front_normals(heights(box_on_floor(), 6.0), [], 0.10, 3)
    inside = np.zeros(normal.shape[:2], dtype=np.bool_)
    inside[4:20, 10:20] = True
    flat = flatten(normal, inside)
    assert (flat[inside] == (128, 128, 255, 255)).all() and (flat[~inside] == normal[~inside]).all()
    assert tilt_of(flat)[inside].max() < 1e-6

    room = np.zeros(normal.shape, dtype=np.uint8)
    room[..., :3] = (120, 100, 80)
    room[..., 3] = 255
    shown = lit(room, normal)
    assert (shown[0, 0] == room[0, 0]).all(), "a flat floor keeps its colour"
    assert shown[12, 12, 0] != room[12, 12, 0], "the box's faces do not"
    assert_golden(request, shown, "normals_box_lit.png")


def test_the_deadzone_keeps_a_gentle_slope_flat_and_levels_steps_the_tilt() -> None:
    ramp = np.tile(np.linspace(0, 1, 32, dtype=np.float32), (8, 1)) * 2.0  # a slope of about 0.0645 a pixel
    x, y = tilts(ramp, 0.10, 3)
    assert (x == 0).all() and (y == 0).all()
    x, y = tilts(ramp * 16, 0.10, 3)
    assert set(np.unique(np.abs(x[:, 1:-1]))) == {np.float32(0.75)} and (y == 0).all(), "a steep slope: the top level"
    assert (encode(x * 0, y)[..., :3] == (128, 128, 255)).all()


def test_masked_fill_leaves_the_inside_and_takes_the_edge_outward() -> None:
    values = np.zeros((8, 8), dtype=np.float32)
    values[2:6, 2:6] = 4.0
    inside = np.zeros((8, 8), dtype=np.bool_)
    inside[2:6, 2:6] = True
    filled = masked_fill(values + np.where(inside, 0, 9).astype(np.float32), inside)
    assert (filled[inside] == 4.0).all() and np.allclose(filled[~inside], 4.0)
    assert (masked_fill(values, np.zeros_like(inside)) == values).all(), "nothing inside: unchanged"


def test_cell_means_averages_each_cell_and_a_padded_cell_takes_the_last() -> None:
    values = np.arange(24, dtype=np.float32).reshape(4, 6)
    edges_x = np.array([0, 2, 4, 6, 6])  # three cells of 2 px and one padded cell
    edges_y = np.array([0, 2, 4])
    means = cell_means(values, edges_x, edges_y)
    assert means.shape == (2, 4)
    assert means[0].tolist() == [3.5, 5.5, 7.5, 7.5] and means[1].tolist() == [15.5, 17.5, 19.5, 19.5]
