"""Golden tests for the sprite Kind's Ops (ticket 0177): `slice_grid`, `feet_point`, `height_from_alpha` and
`normals_from_height`, called directly. The `reference_*` functions are copied from the game's `tools/normal_map.py`
(urban-mystery-club), not imported.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import (
    encode_normals,
    feet_point,
    height_from_alpha,
    normals_from_height,
    quantise_normals,
    slice_grid,
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


# --- the game's reference (tools/normal_map.py), copied -------------------------------------------------------------

SATURATE_PX = 4.0
STRENGTH = 1.6


def reference_chamfer(m: np.ndarray) -> np.ndarray:
    h, w = m.shape
    d = np.pad(np.where(m, 1e9, 0.0), 1, constant_values=0.0)
    s2 = 1.41421356
    for y in range(1, h + 1):
        for x in range(1, w + 1):
            if d[y, x]:
                d[y, x] = min(d[y, x], d[y - 1, x] + 1, d[y, x - 1] + 1, d[y - 1, x - 1] + s2, d[y - 1, x + 1] + s2)
    for y in range(h, 0, -1):
        for x in range(w, 0, -1):
            if d[y, x]:
                d[y, x] = min(d[y, x], d[y + 1, x] + 1, d[y, x + 1] + 1, d[y + 1, x + 1] + s2, d[y + 1, x - 1] + s2)
    return d[1:-1, 1:-1]


def reference_normal_map(rgba: np.ndarray) -> np.ndarray:
    alpha = rgba[..., 3] > 0
    pad = np.pad(alpha, 1)
    height = np.sqrt(np.clip(reference_chamfer(pad) / SATURATE_PX, 0, 1))
    hp = np.pad(height, 1, mode="edge")
    gx = (hp[:-2, 2:] + 2 * hp[1:-1, 2:] + hp[2:, 2:]) - (hp[:-2, :-2] + 2 * hp[1:-1, :-2] + hp[2:, :-2])
    gy = (hp[2:, :-2] + 2 * hp[2:, 1:-1] + hp[2:, 2:]) - (hp[:-2, :-2] + 2 * hp[:-2, 1:-1] + hp[:-2, 2:])
    nx = -gx * STRENGTH
    ny = gy * STRENGTH
    nz = np.ones_like(nx)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.dstack([nx / length, ny / length, nz / length])[1:-1, 1:-1]
    enc = ((n * 0.5 + 0.5) * 255).round().astype(np.uint8)
    out = np.dstack([enc, (alpha * 255).astype(np.uint8)])
    out[~alpha] = (128, 128, 255, 0)
    return out


# --- inputs ---------------------------------------------------------------------------------------------------------


def disc(size: int = 21, radius: float = 9.5) -> np.ndarray:
    yy, xx = np.mgrid[:size, :size]
    c = (size - 1) / 2
    return np.where((yy - c) ** 2 + (xx - c) ** 2 <= radius**2, 255, 0).astype(np.uint8)


def silhouette() -> np.ndarray:
    """A 52 px tall figure on a 40 x 56 canvas: head, torso, arms and two legs, one a step ahead of the other."""
    a = np.zeros((56, 40), dtype=np.uint8)
    yy, xx = np.mgrid[:56, :40]
    a[(yy - 8) ** 2 + (xx - 20) ** 2 <= 36] = 255  # head, rows 2..14
    a[14:34, 13:28] = 255  # torso
    a[16:32, 9:13] = 255  # left arm
    a[16:30, 28:32] = 255  # right arm
    a[34:54, 14:19] = 255  # left leg, to row 53
    a[34:52, 22:27] = 255  # right leg, a step shorter
    return a


def as_gray(values: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    grey = np.floor(values * 255 + 0.5).astype(np.uint8)
    return np.dstack([grey, grey, grey, np.where(alpha > 0, 255, 0).astype(np.uint8)])


# --- slice_grid -----------------------------------------------------------------------------------------------------


def test_slice_grid_cuts_a_3_by_4_sheet_row_by_row(request: pytest.FixtureRequest) -> None:
    cw, ch = 3, 2
    sheet = np.zeros((3 * ch, 4 * cw, 4), dtype=np.uint8)
    for r in range(3):
        for c in range(4):
            n = r * 4 + c
            cell = sheet[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw]
            cell[...] = (20 * n + 10, 255 - 20 * n, 40, 255)
            cell[0, 0] = (255, 255, 255, 255)  # a corner mark, so a shifted cut shows
    cells = slice_grid(sheet, columns=4, rows=3)
    assert len(cells) == 3 and all(len(row) == 4 for row in cells)
    assert all(cell.shape == (ch, cw, 4) for row in cells for cell in row)
    assert_golden(request, np.concatenate([cell for row in cells for cell in row], axis=1), "sprite_slice_cells.png")
    assert np.array_equal(cells[2][3], sheet[4:6, 9:12])
    assert np.array_equal(np.concatenate([np.concatenate(row, axis=1) for row in cells], axis=0), sheet)


def test_slice_grid_refuses_a_sheet_of_the_wrong_size() -> None:
    sheet = np.zeros((10, 13, 4), dtype=np.uint8)
    with pytest.raises(ValueError) as error:
        slice_grid(sheet, columns=4, rows=2)
    message = str(error.value)
    assert "13 x 10" in message and "4 columns x 2 rows" in message
    with pytest.raises(ValueError):
        slice_grid(sheet, columns=0, rows=1)


# --- feet_point -----------------------------------------------------------------------------------------------------


def test_feet_of_a_standing_figure() -> None:
    alpha = np.zeros((20, 20), dtype=np.uint8)
    alpha[2:18, 7:13] = 255  # a body 6 wide, feet on row 17
    assert feet_point(alpha) == (9, 17)  # the centre of columns 7..12 is 9.5, rounded half down


def test_feet_of_a_figure_with_one_leg_forward() -> None:
    alpha = np.zeros((20, 20), dtype=np.uint8)
    alpha[2:12, 6:14] = 255  # body
    alpha[12:17, 6:9] = 255  # back leg, to row 16
    alpha[12:19, 11:14] = 255  # front leg, to row 18
    # the lowest rows, 18 and 17, hold only the front leg, columns 11..13
    assert feet_point(alpha) == (12, 18)


def test_feet_of_an_empty_frame() -> None:
    assert feet_point(np.zeros((8, 8), dtype=np.uint8)) is None


def test_feet_of_a_figure_on_the_first_row() -> None:
    alpha = np.zeros((4, 4), dtype=np.uint8)
    alpha[0, 1:3] = 255
    assert feet_point(alpha) == (1, 0)


# --- height_from_alpha, normals_from_height -------------------------------------------------------------------------


def test_height_of_a_disc(request: pytest.FixtureRequest) -> None:
    alpha = disc()
    height = height_from_alpha(alpha)
    assert height.shape == alpha.shape and height.dtype == np.float64
    assert height[alpha == 0].max() == 0 and height[alpha > 0].min() > 0 and height.max() == 1.0
    assert_golden(request, as_gray(height, alpha), "sprite_height_disc.png")


def test_height_of_the_silhouette(request: pytest.FixtureRequest) -> None:
    alpha = silhouette()
    assert_golden(request, as_gray(height_from_alpha(alpha), alpha), "sprite_height_silhouette.png")


def test_height_matches_the_reference_chamfer() -> None:
    alpha = silhouette()
    expected = np.sqrt(np.clip(reference_chamfer(np.pad(alpha > 0, 1))[1:-1, 1:-1] / SATURATE_PX, 0, 1))
    assert np.allclose(height_from_alpha(alpha), expected, atol=1e-6)


def test_height_at_the_image_edge_counts_the_outside() -> None:
    alpha = np.full((6, 6), 255, dtype=np.uint8)
    height = height_from_alpha(alpha, saturate=4.0)
    assert height[0, 0] == pytest.approx(0.5)  # distance 1 from the outside: sqrt(1 / 4)


def test_normals_of_a_disc(request: pytest.FixtureRequest) -> None:
    alpha = disc()
    normals = normals_from_height(height_from_alpha(alpha), alpha)
    assert normals.dtype == np.uint8 and normals.shape == (*alpha.shape, 4)
    assert (normals[alpha == 0] == 0).all() and (normals[alpha > 0][:, 3] == 255).all()
    # +Y is up: the top rim leans up (green above 128), the bottom rim down; +X right: the right rim leans right.
    assert normals[3, 10, 1] > 128 and normals[17, 10, 1] < 128
    assert normals[10, 17, 0] > 128 and normals[10, 3, 0] < 128
    assert_golden(request, normals, "sprite_normals_disc.png")


def test_normals_of_the_silhouette(request: pytest.FixtureRequest) -> None:
    alpha = silhouette()
    normals = normals_from_height(height_from_alpha(alpha), alpha)
    assert_golden(request, normals, "sprite_normals_silhouette.png")


def test_normals_match_the_games_tool_within_one_per_channel() -> None:
    alpha = silhouette()
    rgba = np.dstack([np.full_like(alpha, 200)] * 3 + [alpha])
    expected = reference_normal_map(rgba)
    actual = normals_from_height(height_from_alpha(alpha), alpha)
    opaque = alpha > 0
    assert (actual[..., 3] == expected[..., 3]).all()
    difference = np.abs(actual[opaque].astype(int) - expected[opaque].astype(int))
    assert difference.max() <= 1
    # the game's tool writes (128, 128, 255, 0) outside; Kiripix's convention is (0, 0, 0, 0)
    assert (actual[~opaque] == 0).all()


def test_normals_go_through_quantise_and_encode_unchanged() -> None:
    alpha = disc()
    normals = normals_from_height(height_from_alpha(alpha), alpha)
    out = encode_normals(quantise_normals(normals, 8))
    assert out.shape == normals.shape and (out[..., 3] == normals[..., 3]).all()


def test_flat_height_gives_flat_normals() -> None:
    alpha = np.full((5, 5), 255, dtype=np.uint8)
    normals = normals_from_height(np.ones((5, 5)), alpha)
    assert (normals[2, 2] == (128, 128, 255, 255)).all()
