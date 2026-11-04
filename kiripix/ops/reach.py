"""Reach Ops (spec §7): where the Body's footprint fits, where it can get to, and the gaps it has to pass.

Pure: arrays in, arrays out. A spot (x, y) is where the footprint is centred. A `width` x `height` footprint covers
x - width // 2 up to x + (width - 1) // 2 and likewise in y, so with an even size the extra pixel is up and to the left.
"""

from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import numpy as np

from kiripix.ops.masks import BoolMask


def _require_mask(mask: BoolMask) -> None:
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")


def _require_footprint(footprint: tuple[int, int]) -> None:
    width, height = footprint
    if width < 1 or height < 1:
        raise ValueError(f"a footprint is at least 1x1, got {width}x{height}")


def walkable(solid: BoolMask, footprint: tuple[int, int]) -> BoolMask:
    """Every spot where a (width, height) footprint lies wholly inside the room and touches no `solid` pixel.

    It says nothing about reachability. The time doesn't depend on the footprint's size: each spot sums its footprint's
    pixels from one table.
    """
    _require_mask(solid)
    _require_footprint(footprint)
    width, height = footprint
    rows, columns = solid.shape
    result = np.zeros_like(solid)
    if width > columns or height > rows:
        return result
    table = np.zeros((rows + 1, columns + 1), dtype=np.int64)
    table[1:, 1:] = solid.astype(np.int64).cumsum(axis=0).cumsum(axis=1)
    touched = table[height:, width:] - table[:-height, width:] - table[height:, :-width] + table[:-height, :-width]
    top, left = height // 2, width // 2
    result[top:top + touched.shape[0], left:left + touched.shape[1]] = touched == 0
    return result


def reachable(ground: BoolMask, seeds: Iterable[tuple[int, int]], footprint: tuple[int, int], step: int = 1,
              dash: int = 0, solid: BoolMask | None = None) -> BoolMask:
    """The spots of walkable `ground` the Body can get to from any of the `seeds` (x, y), moving along the axes.

    A move goes `step` px, every spot on the way must be walkable, and a wall stops it short, where it lands against the
    wall. Step 1 is exact. A longer step visits fewer spots, so it can miss a gap the Body fits only at one exact offset;
    the spots between those it visits are filled in, never across a wall.

    A Body with a `dash` can also cross a pit of up to `dash` px: from a spot with no walkable spot next to it, to the
    first walkable one along the axis. A footprint clears a pit only by its own size more, so the jump is at most
    `dash` plus the footprint's size along that axis. A dash needs `solid`, because it never crosses it: the footprint
    must touch no `solid` pixel on the way. A seed off walkable ground or outside the room floods nothing.
    """
    _require_mask(ground)
    _require_footprint(footprint)
    if step < 1:
        raise ValueError(f"a step is at least 1 px, got {step}")
    if dash < 0:
        raise ValueError(f"a dash can't be negative, got {dash}")
    if dash and solid is None:
        raise ValueError("a dash needs the solid Mask, which it can't cross")
    rows, columns = ground.shape
    free = ground.tobytes()
    clear = walkable(solid, footprint).tobytes() if dash and solid is not None else b""
    landed = bytearray(rows * columns)
    swept = bytearray(rows * columns)
    queue: deque[tuple[int, int]] = deque()
    for x, y in seeds:
        if 0 <= x < columns and 0 <= y < rows and free[y * columns + x] and not landed[y * columns + x]:
            landed[y * columns + x] = swept[y * columns + x] = 1
            queue.append((x, y))
    width, height = footprint
    moves = ((-1, 0, width), (1, 0, width), (0, -1, height), (0, 1, height))
    while queue:
        x, y = queue.popleft()
        for dx, dy, across in moves:
            nx, ny, moved = x, y, 0
            while moved < step:
                tx, ty = nx + dx, ny + dy
                if not (0 <= tx < columns and 0 <= ty < rows and free[ty * columns + tx]):
                    break
                nx, ny, moved = tx, ty, moved + 1
                swept[ny * columns + nx] = 1
            if not moved and dash:
                for distance in range(1, dash + across + 1):
                    tx, ty = x + dx * distance, y + dy * distance
                    if not (0 <= tx < columns and 0 <= ty < rows and clear[ty * columns + tx]):
                        break
                    if free[ty * columns + tx]:
                        nx, ny, moved = tx, ty, distance
                        swept[ny * columns + nx] = 1
                        break
            if moved and not landed[ny * columns + nx]:
                landed[ny * columns + nx] = 1
                queue.append((nx, ny))
    result: BoolMask = np.frombuffer(bytes(swept), dtype=np.bool_).reshape(rows, columns).copy()
    for _ in range(step - 1):
        grown = result.copy()
        grown[1:] |= result[:-1]
        grown[:-1] |= result[1:]
        grown[:, 1:] |= result[:, :-1]
        grown[:, :-1] |= result[:, 1:]
        result = grown & ground
    return result


@dataclass(frozen=True)
class Island:
    """Walkable ground nothing reaches: its bounding box in spots, and how many spots it has."""

    x: int
    y: int
    width: int
    height: int
    spots: int


def walkable_islands(ground: BoolMask, reached: BoolMask) -> list[Island]:
    """The 4-connected pieces of `ground` with no spot in `reached`, the largest first; ties go top-left first."""
    _require_mask(ground)
    _require_mask(reached)
    rows, columns = ground.shape
    free = ground.tobytes()
    seen = bytearray(rows * columns)
    islands = []
    for start in np.flatnonzero(ground):
        origin = int(start)
        if seen[origin]:
            continue
        seen[origin] = 1
        queue = deque([origin])
        pieces = []
        while queue:
            at = queue.popleft()
            pieces.append(at)
            neighbours = (at - columns if at >= columns else -1, at + columns if at + columns < rows * columns else -1,
                          at - 1 if at % columns else -1, at + 1 if (at + 1) % columns else -1)
            for near in neighbours:
                if near >= 0 and free[near] and not seen[near]:
                    seen[near] = 1
                    queue.append(near)
        spots = np.array(pieces)
        ys, xs = spots // columns, spots % columns
        if not reached[ys, xs].any():
            left, top = int(xs.min()), int(ys.min())
            islands.append(Island(left, top, int(xs.max()) - left + 1, int(ys.max()) - top + 1, len(pieces)))
    return sorted(islands, key=lambda island: (-island.spots, island.y, island.x))


@dataclass(frozen=True)
class Gap:
    """A way through `solid`: its `width` in px, what the Body needs to pass there, and the pixel at its centre."""

    width: int
    needed: int
    x: int
    y: int


def _passages(free: BoolMask, needed: int) -> Iterator[tuple[int, int, int, int]]:
    """The gaps across the rows of `free`, column by column: free runs narrower than twice the Body, walled at one end
    or both, that hold still over some columns and open onto free pixels at both sides. Each is (first row, last row,
    first column, last column)."""
    rows, columns = free.shape
    open_columns: dict[tuple[int, int], int] = {}
    for column in range(columns + 1):
        runs = set()
        if column < columns:
            edges = np.flatnonzero(np.diff(free[:, column].astype(np.int8), prepend=0, append=0))
            runs = {(int(top), int(bottom) - 1) for top, bottom in zip(edges[::2], edges[1::2])
                    if int(bottom) - int(top) < 2 * needed and (top > 0 or bottom < rows)}
        for run in set(open_columns) - runs:
            first = open_columns.pop(run)
            top, bottom = run
            if first > 0 and column < columns and free[top:bottom + 1, first - 1].any() and \
                    free[top:bottom + 1, column].any():
                yield top, bottom, first, column - 1
        for run in runs:
            open_columns.setdefault(run, column)


def _one_per_passage(runs: Iterable[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    """A passage with uneven edges comes as several runs, each touching the next across neighbouring columns. Keeps the
    narrowest of each passage; a tie goes to the first."""
    passages: list[list[tuple[int, int, int, int]]] = []
    for run in sorted(runs, key=lambda run: (run[2], run[0])):
        top, bottom, first, _ = run
        for passage in passages:
            if any(other[3] + 1 == first and other[0] <= bottom and top <= other[1] for other in passage):
                passage.append(run)
                break
        else:
            passages.append([run])
    return [min(passage, key=lambda run: run[1] - run[0]) for passage in passages]


def narrowest_gaps(solid: BoolMask, footprint: tuple[int, int], limit: int = 3) -> list[Gap]:
    """Where the Body has to squeeze through `solid`, or can't: the ways through narrower than twice the Body, the
    narrowest first, at most `limit`. Ties go top-left first.

    It looks at `solid`, not at walkable, so that a gap too narrow for the Body, which leaves no walkable spot at all,
    is reported too. A way through is a free run across one axis that opens onto free pixels at both ends along the
    other. A room edge bounds a run as a wall does; a run from edge to edge is just open floor. A passage with uneven
    edges is one gap, at its narrowest.
    """
    _require_mask(solid)
    _require_footprint(footprint)
    width, height = footprint
    free = ~solid
    gaps = [Gap(bottom - top + 1, height, (first + last) // 2, (top + bottom) // 2)
            for top, bottom, first, last in _one_per_passage(_passages(free, height))]
    gaps += [Gap(bottom - top + 1, width, (top + bottom) // 2, (first + last) // 2)
             for top, bottom, first, last in _one_per_passage(_passages(free.T, width))]
    return sorted(gaps, key=lambda gap: (gap.width, gap.y, gap.x))[:limit]
