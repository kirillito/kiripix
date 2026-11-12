"""The cutout Checks (spec §6.2, ticket 0050): did an exact chroma key take the background out?"""

from __future__ import annotations

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks.finding import Finding, Position
from kiripix.ops import key_fringe

KEYED_LEAST = 0.01  # a key that clears less of the image than this removed almost nothing
KEYED_MOST = 0.99  # one that clears more than this took nearly everything
FRINGE_DISTANCE = 0.06  # OKLab distance from the key within which a surviving edge pixel looks like leftover background


def check_chroma_cutout(keyed: np.ndarray, key: tuple[int, int, int], file: str, fix: str) -> list[Finding]:
    """The findings for an image a chroma key has cleared. `fix` is the command that switches to matting."""
    total = keyed.shape[0] * keyed.shape[1]
    cleared = int((keyed[..., 3] == 0).sum())
    hex_key = "#{:02X}{:02X}{:02X}".format(*key)
    if cleared < KEYED_LEAST * total:
        return [Finding(code="cutout.chroma_keyed_nothing", position=Position(file=file), fix=fix,
                        message=f"the key {hex_key} cleared {cleared} of {total} pixels: the background is not that "
                                "colour, or isn't flat")]
    if cleared > KEYED_MOST * total:
        return [Finding(code="cutout.chroma_keyed_everything", position=Position(file=file), fix=fix,
                        message=f"the key {hex_key} cleared {cleared} of {total} pixels: the subject is that colour "
                                "too, or the key is wrong")]
    fringe = key_fringe(keyed, key, FRINGE_DISTANCE)
    if fringe.any():
        ys, xs = np.nonzero(fringe)
        return [Finding(code="cutout.chroma_fringe", severity="warning", position=Position(file=file, x=int(xs[0]),
                                                                                             y=int(ys[0])),
                        message=f"the key {hex_key} left {int(fringe.sum())} pixels along the edge that are close to "
                                f"it but not exactly it, the first at ({int(xs[0])}, {int(ys[0])})", fix=fix)]
    return []
