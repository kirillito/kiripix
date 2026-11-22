"""The ramp swap (spec §6.3, ticket 0337): the game's rule for recolouring a Part, drawn here so a Probe can show it."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from kiripix.ops.colour import U8
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")


def swap_ramps(image: U8, swaps: Sequence[tuple[Sequence[Sequence[int]], Sequence[Sequence[int]]]]) -> U8:
    """An RGBA frame with each Part's ramp swapped. A swap is the Part's ramp as built and the ramp to put in its place,
    both dark to light and as long as each other: a pixel (alpha above 0) whose colour is in `built` takes the colour at
    the same place in `new`. Every other pixel, and every alpha, is left as it is. The swaps are applied together, on the
    colours of the input, so a colour one swap makes is never swapped again by another. A colour that is in two ramps
    takes the first swap that lists it. Returns a copy."""
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("the frame is an RGBA array")
    out = image.copy()
    taken = np.zeros(image.shape[:2], dtype=bool)
    opaque = image[..., 3] > 0
    for built, new in swaps:
        if len(built) != len(new):
            raise ValueError(f"a ramp of {len(built)} colours can't be swapped for one of {len(new)}")
        for old, now in zip(built, new, strict=True):
            hit = opaque & ~taken & (image[..., :3] == np.asarray(old, dtype=np.uint8)).all(axis=-1)
            out[hit, :3] = np.asarray(now, dtype=np.uint8)
            taken |= hit
    return out
