"""Mask Ops (spec §7, ADR 0001): a Mask is an (H, W) boolean array, one per name. Colours exist only for import.

Pure: arrays in, arrays out. Every tie is broken explicitly: a flood takes 4-connected pixels, a stroke stamps its
points in order, and a colour that is equally near two defined colours goes to the first one given.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from fractions import Fraction

from typing import TYPE_CHECKING, Any
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

from kiripix.ops.colour import U8, has_partial_alpha, nearest_index, srgb_to_oklab

if TYPE_CHECKING:
    BoolMask = npt.NDArray[np.bool_]
else:
    BoolMask = Any  # the array types are for the type checker; numpy loads late
RGB = tuple[int, int, int]


def _require_mask(mask: BoolMask) -> None:
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")


def flood_region(rgba: U8, x: int, y: int, tolerance: float = 0.0) -> BoolMask:
    """The 4-connected region containing the pixel (x, y) whose colour is within `tolerance` (OKLab distance) of the
    clicked pixel's own colour, not of its neighbour's. 0 is exact equality. Transparent pixels are all one colour, at
    any tolerance: a transparent seed floods only transparent pixels, and an opaque one never floods into them."""
    height, width = rgba.shape[:2]
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"the point ({x}, {y}) is outside the {width}x{height} image")
    if tolerance < 0:
        raise ValueError("the tolerance is not negative")
    clear = rgba[..., 3] == 0
    if tolerance == 0:
        key = rgba.astype(np.uint32)
        packed = key[..., 0] << 24 | key[..., 1] << 16 | key[..., 2] << 8 | key[..., 3]
        packed = np.where(clear, np.uint32(0), packed)
        same = packed == packed[y, x]
    elif clear[y, x]:
        same = clear
    else:
        lab = srgb_to_oklab(rgba[..., :3])
        distance = np.sqrt(((lab - lab[y, x]) ** 2).sum(axis=-1))
        same = (distance <= tolerance) & ~clear
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


def fill_polygon(mask: BoolMask, points: Sequence[tuple[int, int]], erase: bool = False) -> BoolMask:
    """`mask` with a polygon set (or, with `erase`, cleared). The points are pixel coordinates, the polygon closes
    itself, and it needs at least three.

    A pixel is filled when its centre is inside the polygon by the even-odd rule (so a self-crossing polygon has holes
    where it overlaps itself) or when it is on the outline, a Bresenham line between each pair of neighbouring points
    and from the last point back to the first. Edge pixels are therefore included: a rectangle through the corner
    pixels fills exactly that box. All arithmetic is on integers. Points outside the Mask are clipped.
    """
    _require_mask(mask)
    if len(points) < 3:
        raise ValueError("a polygon needs at least 3 points")
    height, width = mask.shape
    result = mask.copy()
    value = not erase
    count = len(points)
    for y in range(max(0, min(p[1] for p in points)), min(height - 1, max(p[1] for p in points)) + 1):
        crossings: list[tuple[int, int]] = []  # x of the crossing as a fraction (numerator, positive denominator)
        for index in range(count):
            (x0, y0), (x1, y1) = points[index - 1], points[index]
            if y0 == y1 or not (min(y0, y1) <= y < max(y0, y1)):  # half-open, so a shared vertex counts once
                continue
            denominator = y1 - y0
            numerator = x0 * denominator + (y - y0) * (x1 - x0)
            crossings.append((numerator, denominator) if denominator > 0 else (-numerator, -denominator))
        crossings.sort(key=lambda c: Fraction(c[0], c[1]))  # exact
        for first, last in zip(crossings[0::2], crossings[1::2]):
            left = -((-first[0]) // first[1])  # ceil
            right = last[0] // last[1]  # floor
            left, right = max(left, 0), min(right, width - 1)
            if left <= right:
                result[y, left:right + 1] = value
    for index in range(count):
        for x, y in _line(points[index - 1], points[index]):
            if 0 <= x < width and 0 <= y < height:
                result[y, x] = value
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


SIDES = ("top", "right", "bottom", "left")


def _check_sides(sides: Sequence[str]) -> None:
    for side in sides:
        if side not in SIDES:
            raise ValueError(f"'{side}' is not a side; the sides are {', '.join(SIDES)}")


def wall_off(mask: BoolMask, sides: Sequence[str], thickness: int) -> BoolMask:
    """`mask` with a wall `thickness` pixels deep set along each of the `sides` (`top`, `right`, `bottom`, `left`).

    A thickness larger than the room is clipped to it, so it fills it. The input is not changed.
    """
    _require_mask(mask)
    _check_sides(sides)
    if thickness < 1:
        raise ValueError("a wall is at least 1 px thick")
    result = mask.copy()
    if "top" in sides:
        result[:thickness, :] = True
    if "bottom" in sides:
        result[-thickness:, :] = True
    if "left" in sides:
        result[:, :thickness] = True
    if "right" in sides:
        result[:, -thickness:] = True
    return result


def open_edges(blocked: BoolMask) -> dict[str, tuple[int, int]]:
    """The room's edges where the outermost row or column of `blocked` isn't blocked all along: for each such side (in
    the order `top`, `right`, `bottom`, `left`), the first and last open pixel along it, as (first, last). A side that
    is blocked all along is left out."""
    _require_mask(blocked)
    lines = {"top": blocked[0, :], "right": blocked[:, -1], "bottom": blocked[-1, :], "left": blocked[:, 0]}
    result: dict[str, tuple[int, int]] = {}
    for side in SIDES:
        open_at = np.flatnonzero(~lines[side])
        if len(open_at):
            result[side] = (int(open_at[0]), int(open_at[-1]))
    return result
