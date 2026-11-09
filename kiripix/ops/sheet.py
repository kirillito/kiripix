"""The character sheet's Ops (spec §7, ticket 0108): pack a character's frames into one atlas."""

import math

import numpy as np

Rect = tuple[int, int, int, int]  # x, y, width, height in the atlas


def default_cell_pivot(cell: tuple[int, int]) -> tuple[int, int]:
    """Bottom centre of a cell (width, height): the pivot sits at the feet, centred."""
    return cell[0] // 2, cell[1] - 1


def pack_atlas(
    frames: list[np.ndarray],
    pivots: list[tuple[int, int]],
    cell: tuple[int, int],
    columns: int | None = None,
    cell_pivot: tuple[int, int] | None = None,
) -> tuple[np.ndarray, list[Rect]]:
    """Pack RGBA `frames` into a grid of equal cells of `cell` (width, height), in the order given.

    Each frame's pivot (x, y in the frame) lands on `cell_pivot` (default: bottom centre) in its cell. Pixels that
    fall outside the cell are cut off, never moved: `sheet.frame_overflow` reports them. `columns` defaults to the
    ceiling of the square root of the frame count; the last row may be partly empty (transparent). Returns the atlas
    and each frame's cell rectangle (x, y, width, height), in frame order.
    """
    if len(frames) != len(pivots):
        raise ValueError("every frame needs a pivot")
    cw, ch = cell
    if cw < 1 or ch < 1:
        raise ValueError("the cell must be at least 1 x 1")
    count = len(frames)
    cols = columns if columns is not None else max(1, math.ceil(math.sqrt(count)))
    if cols < 1:
        raise ValueError("columns must be at least 1")
    rows = max(1, math.ceil(count / cols))
    px, py = cell_pivot if cell_pivot is not None else default_cell_pivot(cell)
    atlas = np.zeros((rows * ch, cols * cw, 4), dtype=np.uint8)
    rects: list[Rect] = []
    for i, (frame, (fx, fy)) in enumerate(zip(frames, pivots, strict=True)):
        ox, oy = (i % cols) * cw, (i // cols) * ch
        rects.append((ox, oy, cw, ch))
        # The frame's top-left in cell coordinates, then the overlap of frame and cell.
        left, top = px - fx, py - fy
        h, w = frame.shape[:2]
        x0, y0 = max(left, 0), max(top, 0)
        x1, y1 = min(left + w, cw), min(top + h, ch)
        if x1 <= x0 or y1 <= y0:
            continue
        atlas[oy + y0 : oy + y1, ox + x0 : ox + x1] = frame[y0 - top : y1 - top, x0 - left : x1 - left]
    return atlas, rects
