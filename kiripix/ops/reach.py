"""Reach Ops (spec §7): where the Body's footprint fits.

Pure: arrays in, arrays out. A spot (x, y) is where the footprint is centred. A `width` x `height` footprint covers
x - width // 2 up to x + (width - 1) // 2 and likewise in y, so with an even size the extra pixel is up and to the left.
"""

import numpy as np

from kiripix.ops.masks import BoolMask


def walkable(solid: BoolMask, footprint: tuple[int, int]) -> BoolMask:
    """Every spot where a (width, height) footprint lies wholly inside the room and touches no `solid` pixel.

    It says nothing about reachability. The time doesn't depend on the footprint's size: each spot sums its footprint's
    pixels from one table.
    """
    if solid.dtype != np.bool_ or solid.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    width, height = footprint
    if width < 1 or height < 1:
        raise ValueError(f"a footprint is at least 1x1, got {width}x{height}")
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
