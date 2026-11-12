"""Cleanup Ops (spec §7): orphan pixel removal. Pure numpy; deterministic."""

from __future__ import annotations

from collections import Counter, deque
from typing import TYPE_CHECKING, Literal

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

U8 = npt.NDArray[np.uint8]


def remove_orphans(rgba: U8, orphan_size: int) -> U8:
    """Give each island of at most `orphan_size` pixels its most common neighbour colour.

    An island is a 4-connected region of one opaque colour. Its neighbours are the opaque pixels that touch it along an
    edge, counted once per touching edge, and only those in regions larger than `orphan_size` count: islands never
    take colours from each other, so the result does not depend on processing order and two orphans never swap
    colours. A tie goes to the smaller (r, g, b). An island with no such neighbour is left as it is, and transparent
    pixels are neither changed nor counted. Size 0 returns the image unchanged.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if orphan_size < 0:
        raise ValueError("orphan_size can't be negative")
    out = rgba.copy()
    if orphan_size == 0:
        return out
    height, width = rgba.shape[:2]
    packed = (
        (rgba[..., 0].astype(np.int64) << 16) | (rgba[..., 1].astype(np.int64) << 8) | rgba[..., 2].astype(np.int64)
    )
    packed = np.where(rgba[..., 3] == 255, packed, -1)  # -1: transparent
    flat = packed.ravel().tolist()
    label = [-1] * (height * width)
    regions: list[list[int]] = []  # in raster order of each region's first pixel
    for start in range(height * width):
        if flat[start] < 0 or label[start] >= 0:
            continue
        colour, found = flat[start], len(regions)
        members = [start]
        label[start] = found
        queue = deque([start])
        while queue:
            at = queue.popleft()
            y, x = divmod(at, width)
            for ok, to in ((y > 0, at - width), (y < height - 1, at + width), (x > 0, at - 1), (x < width - 1, at + 1)):
                if ok and label[to] < 0 and flat[to] == colour:
                    label[to] = found
                    members.append(to)
                    queue.append(to)
        regions.append(members)
    for members in regions:
        if len(members) > orphan_size:
            continue
        own = label[members[0]]
        votes: Counter[int] = Counter()
        for at in members:
            y, x = divmod(at, width)
            for ok, to in ((y > 0, at - width), (y < height - 1, at + width), (x > 0, at - 1), (x < width - 1, at + 1)):
                if ok and label[to] >= 0 and label[to] != own and len(regions[label[to]]) > orphan_size:
                    votes[flat[to]] += 1
        if not votes:
            continue
        best = min(votes, key=lambda colour: (-votes[colour], colour))
        rgb = np.array([best >> 16, (best >> 8) & 255, best & 255], dtype=np.uint8)
        for at in members:
            out[divmod(at, width) + (slice(0, 3),)] = rgb
    return out


Placement = Literal["outside", "edge"]


def outline_mask(mask: npt.NDArray[np.bool_], placement: Placement = "outside") -> npt.NDArray[np.bool_]:
    """The 1 px line Mask of a silhouette Mask: binary, the same shape, 4-connected (no diagonal-only growth).

    `"outside"`: the empty pixels that touch the silhouette along an edge, so the line grows around it. It is clipped at
    the canvas: a shape that touches the frame's edge has no line there.
    `"edge"`: the silhouette's own pixels that touch an empty pixel along an edge, so the shape keeps its size. The
    canvas beyond the frame counts as empty, so a shape touching the frame's edge has its line there too.
    The line depends only on the silhouette pixels and their four neighbours, so a part that doesn't move between
    frames gets the same line in each, wherever its neighbours differ elsewhere.
    """
    if mask.ndim != 2:
        raise ValueError("expected an (H, W) Mask")
    if placement not in ("outside", "edge"):
        raise ValueError(f"placement is 'outside' or 'edge', not {placement!r}")
    shape = mask.astype(bool)
    padded = np.pad(shape, 1, constant_values=False)
    up, down = padded[:-2, 1:-1], padded[2:, 1:-1]
    left, right = padded[1:-1, :-2], padded[1:-1, 2:]
    if placement == "outside":
        return np.asarray(~shape & (up | down | left | right))
    return np.asarray(shape & ~(up & down & left & right))


def paint_outline(rgba: U8, line: npt.NDArray[np.bool_], colour: tuple[int, int, int]) -> U8:
    """Paint the line Mask `line` in the one colour `colour`, opaque. Everything else is unchanged; the input is not."""
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    if line.shape != rgba.shape[:2]:
        raise ValueError(f"the line Mask is {line.shape[1]} x {line.shape[0]} but the image is {rgba.shape[1]} x {rgba.shape[0]}")
    out = rgba.copy()
    out[line.astype(bool)] = (*colour, 255)
    return out


def add_outline(rgba: U8, colour: tuple[int, int, int], placement: Placement = "outside") -> U8:
    """Outline the image's silhouette (alpha from 1 up) in `colour`: `paint_outline` of `outline_mask`.

    By default (`"outside"`) every transparent pixel that touches an opaque one along an edge (4-adjacent) becomes
    `colour`, opaque, clipped at the canvas, and opaque pixels are not changed. `"edge"` paints the silhouette's own
    border pixels instead.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA image")
    return paint_outline(rgba, outline_mask(rgba[..., 3] > 0, placement), colour)
