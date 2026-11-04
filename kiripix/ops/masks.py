"""Mask Ops (spec §7, ADR 0001): a Mask is an (H, W) boolean array, one per name. Colours exist only for import.

Pure: arrays in, arrays out. Every tie is broken explicitly: a flood takes 4-connected pixels, a stroke stamps its
points in order, and a colour that is equally near two defined colours goes to the first one given.
"""

from collections import deque
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from kiripix.ops.colour import U8, has_partial_alpha, nearest_index, srgb_to_oklab

BoolMask = npt.NDArray[np.bool_]
RGB = tuple[int, int, int]


def _require_mask(mask: BoolMask) -> None:
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")


def flood_region(rgba: U8, x: int, y: int) -> BoolMask:
    """The 4-connected region of equal colour containing the pixel (x, y). Transparent pixels are all one colour."""
    height, width = rgba.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"the point ({x}, {y}) is outside the {width}x{height} image")
    key = rgba.astype(np.uint32)
    packed = key[..., 0] << 24 | key[..., 1] << 16 | key[..., 2] << 8 | key[..., 3]
    packed = np.where(rgba[..., 3] == 0, np.uint32(0), packed)
    wanted = packed[y, x]
    same = packed == wanted
    region = np.zeros((height, width), dtype=np.bool_)
    region[y, x] = True
    queue: deque[tuple[int, int]] = deque([(x, y)])
    while queue:
        cx, cy = queue.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < width and 0 <= ny < height and same[ny, nx] and not region[ny, nx]:
                region[ny, nx] = True
                queue.append((nx, ny))
    return region


def _line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Bresenham's line from `start` to `end`, both included."""
    (x0, y0), (x1, y1) = start, end
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    step_x, step_y = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    points = []
    while True:
        points.append((x0, y0))
        if (x0, y0) == (x1, y1):
            return points
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += step_x
        if doubled <= dx:
            error += dx
            y0 += step_y


def paint_stroke(mask: BoolMask, points: Sequence[tuple[int, int]], radius: int, erase: bool = False) -> BoolMask:
    """`mask` with a brush stroke set (or, with `erase`, cleared): a disc of `radius` pixels stamped along the line
    through `points`. Radius 0 is one pixel. The stroke is clipped to the Mask."""
    _require_mask(mask)
    if radius < 0:
        raise ValueError("the brush radius can't be negative")
    height, width = mask.shape
    result = mask.copy()
    offsets = [(dx, dy) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)
               if dx * dx + dy * dy <= radius * radius]
    path: list[tuple[int, int]] = []
    for index, point in enumerate(points):
        path.extend(_line(points[index - 1], point) if index else [point])
    for px, py in path:
        for dx, dy in offsets:
            x, y = px + dx, py + dy
            if 0 <= x < width and 0 <= y < height:
                result[y, x] = not erase
    return result


def split_painted(rgba: U8, colours: Sequence[tuple[RGB, Sequence[str]]]) -> dict[str, BoolMask]:
    """Split a painted colour image into binary Masks.

    `colours` are the defined colours in order, each with the Masks it sets (a Mask's own colour sets that Mask; an
    import colour such as yellow may set several). Every opaque pixel takes the nearest defined colour by OKLab
    distance, so a stray off-colour pixel snaps to its neighbours' colour; an exact tie goes to the first colour given.
    Transparent pixels set nothing. Partial alpha is refused, never rounded. Every named Mask is returned, empty
    when nothing is painted in it, in order of first appearance.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("a painted image is (H, W, 4) RGBA")
    if has_partial_alpha(rgba):
        raise ValueError("the painted image has partial alpha; paint with fully opaque or fully transparent pixels")
    if not colours:
        raise ValueError("no colours are defined to split by")
    height, width = rgba.shape[:2]
    result: dict[str, BoolMask] = {}
    for _, names in colours:
        for name in names:
            result.setdefault(name, np.zeros((height, width), dtype=np.bool_))
    opaque = rgba[..., 3] == 255
    ys, xs = np.nonzero(opaque)
    if len(ys) == 0:
        return result
    defined = np.array([colour for colour, _ in colours], dtype=np.uint8)
    nearest = nearest_index(srgb_to_oklab(rgba[ys, xs, :3]), srgb_to_oklab(defined))
    for index, (_, names) in enumerate(colours):
        chosen = nearest == index
        for name in names:
            result[name][ys[chosen], xs[chosen]] = True
    return result


def snap_cell(mask: BoolMask, cell: int) -> BoolMask:
    """Quantise a Mask to an N px cell grid from the top-left: a cell is wholly set when at least half its pixels
    are (a tie sets it), else wholly clear. Cells at the right and bottom edges may be smaller. 0 and 1 change
    nothing."""
    _require_mask(mask)
    if cell < 0:
        raise ValueError("the cell size can't be negative")
    if cell <= 1:
        return mask.copy()
    height, width = mask.shape
    result = np.zeros_like(mask)
    for top in range(0, height, cell):
        for left in range(0, width, cell):
            block = mask[top:top + cell, left:left + cell]
            if int(block.sum()) * 2 >= block.size:
                result[top:top + cell, left:left + cell] = True
    return result


def mask_runs(mask: BoolMask) -> list[list[int]]:
    """The Mask as rows of set pixels: [y, x, length], top-left first. A compact form to send to a UI."""
    edges = np.diff(np.pad(mask.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    ys, starts = np.nonzero(edges == 1)
    _, ends = np.nonzero(edges == -1)
    return [[int(y), int(start), int(end - start)] for y, start, end in zip(ys, starts, ends)]
