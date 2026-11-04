"""The geometry Ops, called directly: contours and simplify compared pixel-exactly with golden PNGs (the Mask in grey, the
rings drawn over it at 8x, outer rings in white and holes in red), and worked examples for the shapes built from them."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from kiripix.ops import Outline, collision_shapes, contours, navigation_polygon, simplify
from kiripix.ops.geometry import Ring

EXPECTED = Path(__file__).parent / "expected"
SCALE = 8


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def drawn(mask: np.ndarray, outlines: list[Outline]) -> np.ndarray:
    grey = np.where(mask, 96, 24).astype(np.uint8)
    base = np.dstack([grey, grey, grey, np.full_like(grey, 255)])
    image = Image.fromarray(np.repeat(np.repeat(base, SCALE, axis=0), SCALE, axis=1), "RGBA")
    draw = ImageDraw.Draw(image)

    def ring(points: Ring, colour: tuple[int, int, int, int]) -> None:
        scaled = [(x * SCALE, y * SCALE) for x, y in points]
        draw.line([*scaled, scaled[0]], fill=colour)

    for outline in outlines:
        ring(outline.outer, (255, 255, 255, 255))
        for hole in outline.holes:
            ring(hole, (255, 64, 64, 255))
    return np.asarray(image, dtype=np.uint8).copy()


def blob() -> np.ndarray:
    """48 x 32: a stair-stepped disc with a stair-stepped hole, and a small square apart from it."""
    ys, xs = np.mgrid[0:32, 0:48]
    distance = (xs - 18) ** 2 + (ys - 16) ** 2
    mask = (distance <= 14 ** 2) & (distance > 5 ** 2)
    mask[4:9, 38:44] = True
    return mask


def area(ring: Ring) -> float:
    """The ring's signed area: positive for an outer ring, negative for a hole. Half a whole number, so it adds up exactly."""
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, [*ring[1:], ring[0]])) / 2


def is_convex(ring: Ring) -> bool:
    return all((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) >= 0
               for a, b, c in zip(ring, [*ring[1:], ring[0]], [*ring[2:], *ring[:2]]))


def test_a_contour_of_a_mask_with_a_hole(request: pytest.FixtureRequest) -> None:
    assert_golden(request, drawn(blob(), contours(blob())), "contour_blob.png")


def test_simplify_a_contour_with_a_hole_at_a_one_pixel_tolerance(request: pytest.FixtureRequest) -> None:
    assert_golden(request, drawn(blob(), simplify(contours(blob()), 1.0)), "simplify_blob.png")


def test_a_square_ring_has_its_hole_worked_by_hand() -> None:
    mask = np.ones((5, 5), dtype=np.bool_)
    mask[2, 2] = False

    assert contours(mask) == [Outline(outer=[(0, 0), (5, 0), (5, 5), (0, 5)],
                                      holes=[[(2, 2), (2, 3), (3, 3), (3, 2)]])]


def test_an_island_inside_a_hole_is_its_own_outline() -> None:
    mask = np.ones((7, 7), dtype=np.bool_)
    mask[1:6, 1:6] = False
    mask[3, 3] = True

    outer, island = contours(mask)

    assert area(outer.outer) == 49 and [area(hole) for hole in outer.holes] == [-25]
    assert island == Outline(outer=[(3, 3), (4, 3), (4, 4), (3, 4)], holes=[])


def test_tolerance_zero_keeps_every_corner_and_an_empty_mask_has_no_contours() -> None:
    assert simplify(contours(blob()), 0.0) == contours(blob())
    assert contours(np.zeros((4, 4), dtype=np.bool_)) == []


def test_a_ring_too_small_for_the_tolerance_is_kept_whole() -> None:
    mask = np.zeros((3, 3), dtype=np.bool_)
    mask[1, 1] = True

    assert simplify(contours(mask), 5.0) == contours(mask)


def test_collision_shapes_of_a_square_ring_are_convex_and_cover_it_exactly() -> None:
    mask = np.ones((5, 5), dtype=np.bool_)
    mask[2, 2] = False

    shapes = collision_shapes(contours(mask))

    assert all(is_convex(shape) for shape in shapes)
    assert sum(area(shape) for shape in shapes) == 24
    assert len(shapes) <= 6, "merged, not left as triangles"


def test_a_plain_rectangle_is_one_shape() -> None:
    mask = np.zeros((6, 8), dtype=np.bool_)
    mask[1:5, 2:7] = True

    assert collision_shapes(contours(mask)) == [[(2, 1), (7, 1), (7, 5), (2, 5)]]


def test_two_pixels_touching_only_at_a_corner_stay_apart() -> None:
    mask = np.zeros((2, 2), dtype=np.bool_)
    mask[0, 0] = mask[1, 1] = True

    assert len(contours(mask)) == 2
    assert sum(area(shape) for shape in collision_shapes(contours(mask))) == 2


@pytest.mark.parametrize("seed", range(40))
def test_shapes_of_any_mask_are_convex_and_add_up_to_its_area(seed: int) -> None:
    random = np.random.default_rng(seed)
    mask = random.random((16, 16)) < random.uniform(0.3, 0.8)  # corners touching, holes, islands in holes

    shapes = collision_shapes(contours(mask))

    assert all(is_convex(shape) for shape in shapes)
    assert sum(area(shape) for shape in shapes) == int(mask.sum())


@pytest.mark.parametrize("seed", range(10))
def test_simplified_shapes_of_a_painted_blob_stay_near_its_area(seed: int) -> None:
    random = np.random.default_rng(seed)
    mask = blob()
    for _ in range(30):
        x, y = int(random.integers(0, 47)), int(random.integers(0, 31))
        mask[y:y + 2, x:x + 2] = not mask[y, x]

    outlines = simplify(contours(mask), 1.0)
    shapes = collision_shapes(outlines)

    assert all(is_convex(shape) for shape in shapes)
    assert sum(area(shape) for shape in shapes) == sum(
        area(o.outer) + sum(area(hole) for hole in o.holes) for o in outlines)


def test_a_navigation_polygon_is_convex_polygons_that_share_whole_edges() -> None:
    mask = np.ones((12, 12), dtype=np.bool_)
    mask[4:8, 4:8] = False

    navigation = navigation_polygon(contours(mask))

    rings = [[navigation.vertices[i] for i in polygon] for polygon in navigation.polygons]
    assert all(is_convex(ring) for ring in rings)
    assert sum(area(ring) for ring in rings) == 144 - 16
    edges = [(ring[i], ring[(i + 1) % len(ring)]) for ring in rings for i in range(len(ring))]
    boundary = [(a, b) for a, b in edges if (b, a) not in edges]
    assert sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in boundary) == 48 + 16, \
        "every edge inside the polygon is shared whole by two polygons, so the agent can cross it"
    assert navigation.outlines == [[(0, 0), (12, 0), (12, 12), (0, 12)], [(4, 4), (4, 8), (8, 8), (8, 4)]]
