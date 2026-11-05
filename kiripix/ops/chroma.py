"""Chroma key (spec §6.2, §7): remove a flat background colour exactly. Pure numpy; deterministic."""

import numpy as np

from kiripix.ops.colour import U8, srgb_to_oklab
from kiripix.ops.resample import BoolMask


def _check_rgba(rgba: U8) -> None:
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("expected an (H, W, 4) uint8 RGBA image")


def chroma_key(rgba: U8, key: tuple[int, int, int]) -> U8:
    """`rgba` with every pixel whose colour is exactly `key` cleared to (0, 0, 0, 0).

    Exact: a pixel one level off the key stays. Pixels that were already fully transparent are cleared too, so equal
    transparent pixels are equal. Alpha of the other pixels is untouched, partial or not. The input is not modified.
    """
    _check_rgba(rgba)
    if len(key) != 3 or any(not 0 <= value <= 255 for value in key):
        raise ValueError(f"the key is three numbers from 0 to 255, got {key}")
    out = rgba.copy()
    background = (rgba[..., :3] == np.array(key, dtype=np.uint8)).all(axis=2) | (rgba[..., 3] == 0)
    out[background] = 0
    return out


def key_fringe(rgba: U8, key: tuple[int, int, int], distance: float) -> BoolMask:
    """The pixels a chroma key left that look like leftover background: opaque, not exactly the key, within `distance`
    of it in OKLab, and touching (along an edge) a cleared pixel. Run it on the keyed image."""
    _check_rgba(rgba)
    if distance < 0:
        raise ValueError(f"the distance can't be negative, got {distance}")
    opaque = rgba[..., 3] != 0
    key_lab = srgb_to_oklab(np.array(key, dtype=np.uint8))
    near = np.sqrt(((srgb_to_oklab(rgba[..., :3]) - key_lab) ** 2).sum(axis=2)) <= distance
    cleared = ~opaque
    touching = np.zeros_like(cleared)
    touching[1:, :] |= cleared[:-1, :]
    touching[:-1, :] |= cleared[1:, :]
    touching[:, 1:] |= cleared[:, :-1]
    touching[:, :-1] |= cleared[:, 1:]
    result: BoolMask = opaque & near & touching
    return result
