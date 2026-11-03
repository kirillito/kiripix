"""Putting one image on top of another, pixel-exactly."""

import numpy as np

from kiripix.ops.colour import U8


def overlay(base: U8, top: U8) -> U8:
    """`base` with every pixel of `top` that isn't fully transparent copied over it, unblended.

    Both are (H, W, 4) uint8 arrays of the same size. Pixel art has no partial edges, so a painted pixel replaces the
    one below it whole, alpha included; a transparent pixel of `top` leaves `base` as it was.
    """
    if base.shape != top.shape:
        raise ValueError(f"overlay needs images of the same size, got {base.shape} and {top.shape}")
    painted = top[..., 3] > 0
    result = base.copy()
    result[painted] = top[painted]
    return result
