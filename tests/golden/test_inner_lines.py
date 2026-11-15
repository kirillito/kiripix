"""Golden and unit tests for the inner-line Ops (ticket 0214).

The golden is shown enlarged and captioned for review; the comparison is pixel-exact.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from kiripix.ops import inner_lines, line_colours

EXPECTED = Path(__file__).parent / "expected"
SCALE = 12


def fixture() -> tuple[np.ndarray, np.ndarray]:
    # 1 torso (depth 5), 2 sleeve (depth 3, nearer), 3 collar (depth 8, farther), 4 belt (depth 5, ties the torso).
    rows = [
        "..........",
        ".3333333..",
        ".3333333..",
        ".1111122..",
        ".1111122..",
        ".1111122..",
        ".4444444..",
        "..........",
    ]
    material = np.array([[0 if c == "." else int(c) for c in r] for r in rows], dtype=np.uint8)
    depth = np.zeros(material.shape, dtype=np.float32)
    for m, d in {1: 5, 2: 3, 3: 8, 4: 5}.items():
        depth[material == m] = d
    return material, depth


PALETTE_COLOURS = {0: (24, 24, 40), 1: (200, 90, 80), 2: (80, 160, 200), 3: (230, 220, 170), 4: (90, 120, 70)}


def drawn(material: np.ndarray, lines: np.ndarray, caption: str) -> np.ndarray:
    h, w = material.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for m, c in PALETTE_COLOURS.items():
        rgb[material == m] = c
    rgb[lines] = (255, 255, 255)
    big = np.kron(rgb, np.ones((SCALE, SCALE, 1), dtype=np.uint8))
    canvas = Image.new("RGB", (w * SCALE, h * SCALE + 18), (0, 0, 0))
    canvas.paste(Image.fromarray(big, "RGB"), (0, 0))
    ImageDraw.Draw(canvas).text((2, h * SCALE + 3), caption, fill=(255, 255, 255))
    out = np.asarray(canvas.convert("RGBA"), dtype=np.uint8)
    return out


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def test_lines_on_the_farther_side_of_each_border(request: pytest.FixtureRequest) -> None:
    material, depth = fixture()
    lines = inner_lines(material, depth, [])
    assert not lines[material == 0].any()
    assert_golden(request, drawn(material, lines, "line: farther side"), "inner_lines_all.png")


def test_skipped_pair_and_skipped_material(request: pytest.FixtureRequest) -> None:
    material, depth = fixture()
    lines = inner_lines(material, depth, [(1, 3), 2])
    assert not (lines & (material == 3)).any()  # the collar-torso pair
    assert not lines[:, 6:8][3:6].any()  # the sleeve's borders
    assert_golden(request, drawn(material, lines, "skip (1,3) and 2"), "inner_lines_skipped.png")


def test_a_depth_tie_puts_the_line_on_the_lower_or_right_pixel() -> None:
    vertical = inner_lines(np.array([[1], [2]], dtype=np.uint8), np.zeros((2, 1)), [])
    assert vertical.tolist() == [[False], [True]]
    horizontal = inner_lines(np.array([[1, 2]], dtype=np.uint8), np.zeros((1, 2)), [])
    assert horizontal.tolist() == [[False, True]]


def test_the_nearer_part_keeps_its_pixels() -> None:
    material = np.array([[1, 2]], dtype=np.uint8)
    assert inner_lines(material, np.array([[9.0, 1.0]]), []).tolist() == [[True, False]]
    assert inner_lines(material, np.array([[1.0, 9.0]]), []).tolist() == [[False, True]]


def mapped(material: np.ndarray, palette: np.ndarray, picks: np.ndarray) -> np.ndarray:
    out = np.zeros((*material.shape, 4), dtype=np.uint8)
    out[..., :3] = palette[picks]
    out[..., 3] = np.where(material > 0, 255, 0)
    return out


PALETTE = np.array([[20, 20, 30], [60, 30, 30], [200, 90, 80], [240, 200, 190], [30, 60, 120], [100, 160, 220]], dtype=np.uint8)


def test_line_colours_ignore_frame_order_and_are_palette_colours() -> None:
    material = np.zeros((4, 5), dtype=np.uint8)
    material[:, :3] = 1
    material[:, 3:] = 2
    picks_a = np.array([[2, 2, 2, 5, 5]] * 3 + [[1, 3, 3, 4, 5]])
    picks_b = np.array([[1, 3, 2, 5, 5]] * 4)
    frames = [mapped(material, PALETTE, picks_a), mapped(material, PALETTE, picks_b)]
    labels = [material, material]
    forward = line_colours(frames, labels, PALETTE, 0.5)
    backward = line_colours(frames[::-1], labels[::-1], PALETTE, 0.5)
    assert forward == backward
    assert set(forward) == {1, 2}
    assert all(0 <= v < len(PALETTE) for v in forward.values())
    # Material 1's colour 1 is 5 of 24 pixels, so it is the darkest kept; halved in linear light it maps to colour 0.
    assert forward[1] == 0


def test_a_colour_under_five_percent_is_not_the_darkest() -> None:
    material = np.ones((1, 40), dtype=np.uint8)
    picks = np.full((1, 40), 2)
    picks[0, 0] = 0  # 1 of 40 pixels: 2.5 %
    out = line_colours([mapped(material, PALETTE, picks)], [material], PALETTE, 0.5)
    assert out[1] != 0
    picks[0, :2] = 0  # 5 %: kept
    out_kept = line_colours([mapped(material, PALETTE, picks)], [material], PALETTE, 0.0)
    assert out_kept[1] == 0


def test_a_material_with_no_pixels_has_no_entry() -> None:
    material = np.zeros((2, 2), dtype=np.uint8)
    assert line_colours([mapped(material, PALETTE, np.zeros((2, 2), dtype=int))], [material], PALETTE, 0.5) == {}
