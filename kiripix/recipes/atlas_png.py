"""How the `sheet` Stage writes its colour atlas (ticket 0310): an indexed PNG when the pixels hold at most 256 colours, else RGBA.

The one place that writes the colour atlas's file, so that the layout work around it (the packer, trimmed cells) doesn't touch the
encoding. A palette-mapped character always fits: its colours are the Project palette's, and index 0 is transparent. The decoded
pixels are exactly the RGBA given. Nothing but PIL and numpy: no I/O besides the one file.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kiripix.ops.lazy import lazy_module
from kiripix.recipes.common import write_rgba

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

MAX_COLOURS = 256


def write_colour_atlas(path: Path, rgba: np.ndarray) -> int | None:
    """Writes `rgba` (height, width, 4 uint8) as an indexed PNG with transparency, index 0 being transparent black, when it has
    at most `MAX_COLOURS` distinct colours (that one counted). Otherwise writes RGBA and returns the number of distinct colours
    in the atlas, as the `sheet` Check counts them."""
    from PIL import Image

    packed = np.ascontiguousarray(rgba).view("<u4").reshape(rgba.shape[:2])  # one number per pixel: r, g, b, a bytes
    distinct = np.unique(packed)
    colours = distinct[distinct != 0]  # transparent black is index 0 whether or not the atlas has it
    if colours.size + 1 > MAX_COLOURS:
        write_rgba(path, rgba)
        return int(distinct.size)
    table = np.concatenate([np.zeros(1, dtype="<u4"), colours])
    indices = np.searchsorted(table[1:], packed, side="left") + 1
    indices[packed == 0] = 0
    entries = table.view(np.uint8).reshape(-1, 4)
    image = Image.fromarray(indices.astype(np.uint8), "P")
    image.putpalette(entries[:, :3].tobytes())
    image.save(path, format="PNG", optimize=True, transparency=entries[:, 3].tobytes())
    return None
