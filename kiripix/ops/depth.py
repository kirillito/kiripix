"""A float image in 0 to 1 as 16-bit pixels and back: how a depth result is pinned (ticket 0340). 16 bits keep a depth's
gradients smooth under a Sobel filter, where 8 would stair-step them. Pure: arrays in, arrays out."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")


def unit_to_u16(values: np.ndarray) -> np.ndarray:
    """Floats in 0 to 1 as uint16, 0 to 65535, rounded; anything outside is clipped."""
    return np.clip(np.rint(values * 65535), 0, 65535).astype(np.uint16)


def u16_to_unit(pixels: np.ndarray) -> np.ndarray:
    """uint16 pixels as float32 in 0 to 1."""
    return (pixels.astype(np.float32) / 65535).astype(np.float32)
