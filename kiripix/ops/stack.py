"""Stacking frames of one cell over each other (spec §7, ticket 0294): by a fixed order, or by the depth pass."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from kiripix.ops.colour import U8
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

DEPTH_FAR = 65536  # beyond any 16 bit depth value


def stack_by_order(frames: Sequence[U8]) -> U8:
    """RGBA frames of one size, the lowest first, each pasted over the last wherever it has a pixel (alpha above 0)."""
    if not frames:
        raise ValueError("nothing to stack")
    out = np.zeros_like(frames[0])
    for frame in frames:
        if frame.shape != out.shape or frame.ndim != 3 or frame.shape[2] != 4:
            raise ValueError("frames are RGBA arrays of one size")
        covered = frame[..., 3] > 0
        out[covered] = frame[covered]
    return out


def stack_by_depth(frames: Sequence[U8], depths: Sequence[np.ndarray]) -> U8:
    """The same frames, but at each pixel the nearest one wins by its depth pass (16 bit, smaller is nearer). A pixel
    without alpha takes no part. A tie goes to the later frame in the list (the higher in the order)."""
    if not frames or len(frames) != len(depths):
        raise ValueError("one depth pass for each frame")
    out = np.zeros_like(frames[0])
    best = np.full(frames[0].shape[:2], DEPTH_FAR, dtype=np.int64)
    for frame, depth in zip(frames, depths, strict=True):
        if frame.shape != out.shape or depth.shape != frame.shape[:2]:
            raise ValueError("frames and depth passes are of one size")
        nearer = (frame[..., 3] > 0) & (depth.astype(np.int64) <= best)
        out[nearer] = frame[nearer]
        best[nearer] = depth[nearer]
    return out


def stack_difference(a: U8, b: U8) -> np.ndarray:
    """A boolean image of the pixels where two RGBA frames differ: one has alpha and the other not, or both have it and
    their colours differ."""
    if a.shape != b.shape:
        raise ValueError("frames are of one size")
    in_a, in_b = a[..., 3] > 0, b[..., 3] > 0
    same: np.ndarray = (a[..., :3] == b[..., :3]).all(axis=-1)
    return np.asarray((in_a != in_b) | (in_a & in_b & ~same))
