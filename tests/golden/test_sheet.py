"""Golden tests for `pack_atlas` and direct tests for the sheet Checks (ticket 0108)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.checks import (
    SheetFrame,
    check_empty_frame,
    check_frame_count,
    check_frame_overflow,
    check_normal_size,
    check_pivot_drift,
)
from kiripix.ops import pack_atlas

EXPECTED = Path(__file__).parent / "expected"
FIX = "kiripix op render"


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


def block(w: int, h: int, colour: tuple[int, int, int]) -> np.ndarray:
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = colour
    out[..., 3] = 255
    return out


def five_frames() -> tuple[list[np.ndarray], list[tuple[int, int]]]:
    """Five frames of different sizes, each with a distinct colour and a pivot at its bottom centre."""
    sizes = [(3, 4), (5, 3), (2, 5), (4, 4), (3, 2)]
    colours = [(200, 40, 40), (40, 200, 40), (40, 40, 200), (200, 200, 40), (40, 200, 200)]
    frames = [block(w, h, c) for (w, h), c in zip(sizes, colours, strict=True)]
    return frames, [(w // 2, h - 1) for w, h in sizes]


def test_pack_atlas_aligns_pivots_and_handles_an_odd_count(request: pytest.FixtureRequest) -> None:
    frames, pivots = five_frames()

    atlas, rects = pack_atlas(frames, pivots, (6, 6))

    # Five frames: 3 columns, 2 rows; the last cell is empty.
    assert atlas.shape == (12, 18, 4)
    assert rects == [(0, 0, 6, 6), (6, 0, 6, 6), (12, 0, 6, 6), (0, 6, 6, 6), (6, 6, 6, 6)]
    for (x, y, _w, h), frame, pivot in zip(rects, frames, pivots, strict=True):
        # The pivot lands on the cell's bottom centre (3, 5) in every cell, so every frame's bottom row is row 5.
        assert atlas[y + 5, x + 3, 3] == 255
        assert atlas[y + 5, x + 3, :3].tolist() == frame[pivot[1], pivot[0], :3].tolist()
    assert (atlas[6:12, 12:18] == 0).all()
    assert_golden(request, atlas, "sheet_atlas_five.png")


def test_pack_atlas_with_columns_and_a_chosen_pivot() -> None:
    frames, pivots = five_frames()

    atlas, rects = pack_atlas(frames[:2], pivots[:2], (6, 6), columns=1, cell_pivot=(2, 2))

    assert atlas.shape == (12, 6, 4)
    assert rects == [(0, 0, 6, 6), (0, 6, 6, 6)]
    assert atlas[2, 2, 3] == 255 and atlas[1, 0, 3] == 0  # frame 0's pivot (1, 3) is placed at (2, 2)


def test_pack_atlas_cuts_off_what_overflows_and_never_shifts_it() -> None:
    frame = block(4, 4, (9, 9, 9))

    atlas, _ = pack_atlas([frame], [(0, 0)], (3, 3), cell_pivot=(1, 1))

    assert atlas.shape == (3, 3, 4)
    assert (atlas[0, :, 3] == 0).all() and (atlas[:, 0, 3] == 0).all()
    assert (atlas[1:, 1:, 3] == 255).all()


def test_pack_atlas_needs_a_pivot_per_frame() -> None:
    with pytest.raises(ValueError):
        pack_atlas([block(2, 2, (1, 1, 1))], [], (4, 4))


def sf(clip: str, direction: str, index: int, pivot: tuple[int, int] = (2, 3), image: np.ndarray | None = None,
       normal: np.ndarray | None = None) -> SheetFrame:
    return SheetFrame(clip, direction, index, block(5, 4, (1, 2, 3)) if image is None else image, pivot, normal)


def test_pivot_drift() -> None:
    steady = [sf("idle", "e", i) for i in range(3)]
    assert check_pivot_drift(steady, {"idle"}, FIX) == []

    drifting = [sf("idle", "e", 0), sf("idle", "e", 1, (2, 4)), sf("idle", "w", 0), sf("idle", "w", 1)]
    found = check_pivot_drift(drifting, {"idle"}, FIX)
    assert [(f.code, f.position.field if f.position else None) for f in found] == [("sheet.pivot_drift", "idle/e/1")]
    assert found[0].position is not None and (found[0].position.x, found[0].position.y) == (2, 4)
    assert found[0].fix == FIX

    assert check_pivot_drift(drifting, {"idle"}, FIX, tolerance=1) == []
    assert check_pivot_drift(drifting, set(), FIX) == []  # a clip that isn't stationary is not checked
    assert check_pivot_drift(drifting, {"walk"}, FIX) == []


def test_frame_overflow() -> None:
    fits = [sf("idle", "e", 0, (2, 3))]
    assert check_frame_overflow(fits, (6, 6), FIX, cell_pivot=(2, 4)) == []

    found = check_frame_overflow([fits[0], sf("idle", "e", 1, (0, 0))], (6, 6), FIX, cell_pivot=(2, 4))
    assert [f.code for f in found] == ["sheet.frame_overflow"]
    pos = found[0].position
    assert pos is not None and pos.field == "idle/e/1"
    # Pivot (0, 0) on (2, 4): the 5 x 4 frame spans x 2..6, y 4..7, beyond a 6 x 6 cell.
    assert (pos.x, pos.y, pos.width, pos.height) == (2, 4, 5, 4)


def test_frame_overflow_ignores_transparent_pixels() -> None:
    image = np.zeros((10, 10, 4), dtype=np.uint8)
    image[4, 4] = (1, 1, 1, 255)
    assert check_frame_overflow([sf("idle", "e", 0, (4, 4), image)], (2, 2), FIX, cell_pivot=(1, 1)) == []


def test_frame_count() -> None:
    frames = [sf("walk", "e", i) for i in range(4)] + [sf("walk", "w", i) for i in range(3)]
    found = check_frame_count(frames, {"walk": 4}, FIX)
    assert [(f.code, f.position.field if f.position else None) for f in found] == [("sheet.frame_count", "walk/w")]
    assert check_frame_count(frames[:4], {"walk": 4}, FIX) == []
    assert check_frame_count(frames, {"run": 9}, FIX) == []
    missing = check_frame_count(frames[:4], {"walk": 4}, FIX, directions=["e", "w"])
    assert [(f.code, f.position.field if f.position else None) for f in missing] == [("sheet.frame_count", "walk/w")]
    assert "0 frames" in missing[0].message


def test_empty_frame() -> None:
    clear = np.zeros((4, 5, 4), dtype=np.uint8)
    found = check_empty_frame([sf("idle", "e", 0), sf("idle", "e", 1, image=clear)], FIX)
    assert [(f.code, f.position.field if f.position else None) for f in found] == [("sheet.empty_frame", "idle/e/1")]
    assert check_empty_frame([sf("idle", "e", 0)], FIX) == []


def test_normal_size_mismatch() -> None:
    good = np.zeros((4, 5, 4), dtype=np.uint8)
    bad = np.zeros((4, 4, 4), dtype=np.uint8)
    found = check_normal_size([sf("idle", "e", 0, normal=good), sf("idle", "e", 1, normal=bad), sf("idle", "e", 2)], FIX)
    assert [(f.code, f.position.field if f.position else None) for f in found] == [("normal.size_mismatch", "idle/e/1")]
