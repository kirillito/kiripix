"""A hole for a Runner call: the Mask an earlier pinned call returned, as a crop and runs (ticket 0039, ADR 0002).

A Stage builds a chained call's `params` from the pinned result of the call before it, so the key and the pinned record
cover the hole with no extra field. The hole is the Mask cropped to its bounding box plus a margin, as rows of set pixels
in the style of `ops.mask_runs`: a hole is mostly a few solid blobs, so a 1000 px wide hole of 300 rows is some 300
runs, a few KB of JSON, not a bitmap.
"""

from typing import Any

import numpy as np

from kiripix.ops import mask_runs


def hole_params(mask: np.ndarray, margin: int = 0) -> dict[str, Any]:
    """`{"crop": [top, left, bottom, right], "runs": [[y, x, length], ...]}`: the box around the set pixels, grown by
    `margin` and kept inside the image (bottom and right are exclusive), and the runs relative to its top-left corner.
    An empty Mask is an empty crop with no runs."""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return {"crop": [0, 0, 0, 0], "runs": []}
    height, width = mask.shape
    top, left = max(int(ys.min()) - margin, 0), max(int(xs.min()) - margin, 0)
    bottom, right = min(int(ys.max()) + 1 + margin, height), min(int(xs.max()) + 1 + margin, width)
    return {"crop": [top, left, bottom, right], "runs": mask_runs(mask[top:bottom, left:right].astype(np.bool_))}


def hole_mask(params: dict[str, Any], shape: tuple[int, int]) -> np.ndarray:
    """The Mask of `shape` that `hole_params` described: what a Runner reads its hole from."""
    mask = np.zeros(shape, dtype=np.bool_)
    top, left, _, _ = params["crop"]
    for y, x, length in params["runs"]:
        mask[top + y, left + x:left + x + length] = True
    return mask
