"""Cleanup Ops (spec §7): orphan pixel removal. Pure numpy; deterministic."""

from collections import Counter, deque

import numpy as np
import numpy.typing as npt

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
