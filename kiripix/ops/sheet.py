"""The character sheet's Ops (spec §7, ticket 0108): pack a character's frames into one atlas."""

from __future__ import annotations

import math

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

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


def place_in_cell(frame: np.ndarray, pivot: tuple[int, int], cell: tuple[int, int], cell_pivot: tuple[int, int]) -> np.ndarray:
    """One frame as a whole cell of `cell` (width, height): its pivot on `cell_pivot`, what falls outside cut off (as `pack_atlas`)."""
    return pack_atlas([frame], [pivot], cell, 1, cell_pivot)[0]


def opaque_box(cells: list[np.ndarray]) -> Rect:
    """The smallest box (x, y, width, height) holding every pixel that isn't all zero in any of `cells`, one frame's layers of
    one size (colour, normal, ...). A frame with no such pixel has the 1 x 1 box at (0, 0), so it still has a region."""
    seen = np.zeros(cells[0].shape[:2], dtype=bool)
    for layer in cells:
        seen |= layer.reshape(*layer.shape[:2], -1).any(axis=2)
    rows, columns = np.nonzero(seen.any(axis=1))[0], np.nonzero(seen.any(axis=0))[0]
    if not len(rows):
        return (0, 0, 1, 1)
    return (int(columns[0]), int(rows[0]), int(columns[-1]) - int(columns[0]) + 1, int(rows[-1]) - int(rows[0]) + 1)


def shelf_layout(sizes: list[tuple[int, int]], gap: int = 1) -> tuple[list[tuple[int, int]], tuple[int, int]]:
    """Places boxes (width, height) in rows ("shelves"), tallest first, with `gap` empty px between them and no overlap. The
    width aims at a square atlas. Returns each box's top left, in the order given, and the atlas size (width, height). Pure and
    deterministic: the same sizes give the same layout."""
    if not sizes:
        return [], (1, 1)
    area = sum((w + gap) * (h + gap) for w, h in sizes)
    width = max(max(w for w, _ in sizes), math.ceil(math.sqrt(area * 1.1)))
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0], i))
    places: list[tuple[int, int]] = [(0, 0)] * len(sizes)
    x = y = shelf = reach = 0
    for i in order:
        w, h = sizes[i]
        if x and x + w > width:
            y, x, shelf = y + shelf + gap, 0, 0
        places[i] = (x, y)
        x += w + gap
        shelf = max(shelf, h)
        reach = max(reach, x - gap)
    return places, (reach, y + shelf)


def blit_trimmed(cells: list[np.ndarray], rects: list[Rect], offsets: list[tuple[int, int]], size: tuple[int, int]) -> np.ndarray:
    """An RGBA atlas of `size` (width, height): each whole-cell frame's box (`rect`'s size, at `offset` in its cell) copied to
    `rect`'s place."""
    atlas = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    for cell, (x, y, w, h), (ox, oy) in zip(cells, rects, offsets, strict=True):
        atlas[y:y + h, x:x + w] = cell[oy:oy + h, ox:ox + w]
    return atlas


def pack_trimmed(layers: list[list[np.ndarray]], gap: int = 1) -> tuple[list[np.ndarray], list[Rect], list[tuple[int, int]]]:
    """Packs frames cut to their opaque boxes. `layers[k][i]` is frame i's whole cell in layer k (colour, normal, ...; a frame's
    layers are one size, and frames may differ). One box for each frame over every layer (`opaque_box`), so the layers share a
    layout. Returns one RGBA atlas for each layer, each frame's rect in them, and each frame's offset (x, y) in its cell:
    `cell[offset.y : offset.y + rect.height, offset.x : offset.x + rect.width] = atlas[rect]` restores the cell exactly."""
    count = len(layers[0]) if layers else 0
    boxes = [opaque_box([layer[i] for layer in layers]) for i in range(count)]
    places, size = shelf_layout([(b[2], b[3]) for b in boxes], gap)
    rects = [(x, y, b[2], b[3]) for (x, y), b in zip(places, boxes, strict=True)]
    offsets = [(b[0], b[1]) for b in boxes]
    return [blit_trimmed(layer, rects, offsets, size) for layer in layers], rects, offsets
