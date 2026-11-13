"""Golden tests for the join Ops (ticket 0135): `register_piece`, `resample_piece`, `match_tone` and `seam_join`, called
directly on synthetic Sources. The scene is a fixed sum of sinusoids, so a piece is that scene sampled with a scale and a
shift, and the right answer is known exactly.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import Overlap, match_tone, register_piece, resample_piece, seam_join

EXPECTED = Path(__file__).parent / "expected"
SCALE_X, SCALE_Y = 1.012, 1.0125  # an image model's rescale of a piece, as trial 0063 measured it


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


def scene(width: int, height: int, scale_x: float = 1.0, scale_y: float = 1.0, x0: float = 0.0, y0: float = 0.0) -> np.ndarray:
    """The scene sampled at (scale * pixel + origin): the base is scale 1, origin 0."""
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    x, y = scale_x * xx + x0, scale_y * yy + y0
    wave = np.zeros((height, width))
    for _ in range(16):
        k, angle, phase, amp = rng.uniform(0.08, 0.9), rng.uniform(0, np.pi), rng.uniform(0, 6.28), rng.uniform(10, 30)
        wave += amp * np.sin(k * (np.cos(angle) * x + np.sin(angle) * y) + phase)
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = np.clip(128 + wave, 0, 255)
    rgba[..., 1] = np.clip(110 + 0.8 * wave + (x % 37 < 3) * 40, 0, 255)
    rgba[..., 2] = np.clip(90 + 0.5 * wave, 0, 255)
    rgba[..., 3] = 255
    return rgba


def corner_error(registration, truth) -> float:  # type: ignore[no-untyped-def]
    """The largest distance in px between where the registration and the truth put the piece's corners."""
    (sx, sy, tx, ty), (w, h) = truth, (199, 119)
    return max(
        float(np.hypot(registration.to_base(x, y)[0] - (sx * x + tx), registration.to_base(x, y)[1] - (sy * y + ty)))
        for x in (0, w)
        for y in (0, h)
    )


def test_register_a_scaled_and_shifted_piece(request: pytest.FixtureRequest) -> None:
    base = scene(200, 120)
    truth = (SCALE_X, SCALE_Y, 98.4, 2.6)  # the piece lies east, covering the last 100 px, 1.2 % too large
    piece = scene(200, 120, *truth)
    registration = register_piece(base, piece, [Overlap("east", 100, 0)])
    assert registration.residual <= 0.5
    assert corner_error(registration, truth) <= 0.5
    assert abs(registration.scale_y - SCALE_Y) < 0.002

    placed, origin = resample_piece(piece, registration)
    overlap = Overlap.placed("east", base.shape, placed.shape, origin)
    toned, _ = match_tone(base, placed, overlap)
    joined, _ = seam_join(base, toned, overlap, 6)
    assert joined.shape[0] == max(120, placed.shape[0] + origin[1]) - min(0, origin[1])
    assert_golden(request, joined, "join_pipeline.png")


def test_register_a_corner_piece_against_two_edges() -> None:
    """The base is an L: the east piece along the top and the south piece down the left, with the corner not yet filled."""
    base = scene(300, 300)
    base[260:, 260:, 3] = 0
    truth = (SCALE_X, SCALE_Y, 179.0, 181.5)
    piece = scene(150, 150, *truth)
    registration = register_piece(base, piece, [Overlap("east", 120, 0), Overlap("south", 120, 0)])
    assert registration.residual <= 0.5
    for x, y in ((0, 0), (149, 0), (0, 149), (149, 149)):
        bx, by = registration.to_base(x, y)
        assert np.hypot(bx - (SCALE_X * x + truth[2]), by - (SCALE_Y * y + truth[3])) <= 0.5


def test_a_tone_step_is_removed(request: pytest.FixtureRequest) -> None:
    base = scene(200, 120)
    piece = scene(200, 120, 1.0, 1.0, 100.0, 0.0)  # the same scene, the piece's left half covering the base's right half
    darkened = piece.astype(np.float64)
    darkened[:60, :, :3] *= 0.7  # the piece's upper rows are darker, then a step to 0.9
    darkened[60:, :, :3] *= 0.9
    darkened = np.floor(darkened + 0.5).astype(np.uint8)
    overlap = Overlap("east", 100, 0)
    before = np.abs(darkened[:, :100, :3].astype(int) - base[:, 100:, :3].astype(int)).mean()
    toned, gain = match_tone(base, darkened, overlap, sigma=6.0)
    after = np.abs(toned[:, :100, :3].astype(int) - base[:, 100:, :3].astype(int)).mean()
    assert before > 20 and after < 4
    assert 1 / 0.9 - 0.1 < gain.low < gain.high < 1 / 0.7 + 0.1
    assert np.array_equal(toned[..., 3], darkened[..., 3])
    assert_golden(request, toned, "join_tone.png")


def band_case() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A base and a piece that differ everywhere except in a wavy band; the band's centre per row."""
    base = scene(160, 100)
    piece = 255 - base
    piece[..., 3] = 255
    centre = (110 + np.round(8 * np.sin(np.arange(100) / 15.0))).astype(int)
    for y, c in enumerate(centre):
        piece[y, c - 3 : c + 4] = base[y, c - 3 : c + 4]
    return base, piece, centre


def test_the_seam_follows_a_band_of_low_difference(request: pytest.FixtureRequest) -> None:
    base, piece, centre = band_case()
    overlap = Overlap("east", 160, 0)  # the piece lies over the whole base
    joined, seam = seam_join(base, piece, overlap, 4)
    assert len(seam.points) == 100
    assert np.all(np.abs(seam.points[:, 0] - centre) <= 3)
    assert seam.mean_difference < 10
    assert seam.base_origin == (0, 0) and seam.piece_origin == (0, 0)
    assert_golden(request, joined, "join_seam.png")


def test_the_seam_is_the_same_on_a_south_join() -> None:
    base, piece, _ = band_case()
    east, east_seam = seam_join(base, piece, Overlap("east", 160, 0), 4)
    south, south_seam = seam_join(base.swapaxes(0, 1), piece.swapaxes(0, 1), Overlap("south", 160, 0), 4)
    assert np.array_equal(south.swapaxes(0, 1), east)
    assert np.array_equal(south_seam.points[:, ::-1], east_seam.points)


def test_a_west_join_grows_the_canvas_to_the_left() -> None:
    base = scene(100, 60)
    piece = scene(100, 60, 1.0, 1.0, -70.0, 0.0)  # the piece shows the scene 70 px further left
    joined, seam = seam_join(base, piece, Overlap("west", 30, 0), 4)
    assert joined.shape == (60, 170, 4)
    assert seam.base_origin == (70, 0) and seam.piece_origin == (0, 0)
    assert np.abs(joined[:, 70:, :3].astype(int) - base[..., :3].astype(int)).max() < 10  # base side kept (blend aside)
