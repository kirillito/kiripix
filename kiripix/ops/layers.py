"""The Layer Ops (spec §7): cutting an image into Layers and putting them back, on binary Masks."""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from kiripix.ops.colour import U8, srgb_to_oklab
from kiripix.ops.compose import overlay
from kiripix.ops.resample import BoolMask, Grid, _cell_index


def grow_where_partial(alpha: BoolMask, partial: BoolMask, pixels: int) -> BoolMask:
    """`alpha` widened by `pixels` target pixels, only into or through pixels `partial` marks.

    Each step adds the 4-neighbours of the set pixels that `partial` marks, so a run of partial pixels is crossed one
    pixel per step and a pixel `partial` doesn't mark is never added. 0 returns `alpha` unchanged. The input is not
    modified.
    """
    if alpha.dtype != np.bool_ or alpha.ndim != 2 or partial.dtype != np.bool_ or partial.shape != alpha.shape:
        raise ValueError("alpha and partial are 2-D boolean arrays of one size")
    if pixels < 0:
        raise ValueError(f"pixels can't be negative, got {pixels}")
    grown = alpha.copy()
    for _ in range(pixels):
        reach = grown.copy()
        reach[1:, :] |= grown[:-1, :]
        reach[:-1, :] |= grown[1:, :]
        reach[:, 1:] |= grown[:, :-1]
        reach[:, :-1] |= grown[:, 1:]
        step = grown | (reach & partial)
        if (step == grown).all():
            break
        grown = step
    return grown


def partial_cells(mask_on_source: BoolMask, grid: Grid) -> BoolMask:
    """The target pixels whose Source cell is neither all set nor all clear in a binary Runner Mask.

    Source pixels outside the grid belong to no cell and are ignored; a cell holding no Source pixel is not partial.
    """
    if mask_on_source.dtype != np.bool_ or mask_on_source.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    index_x = _cell_index(grid.edges_x(), mask_on_source.shape[1])
    index_y = _cell_index(grid.edges_y(), mask_on_source.shape[0])
    cell = index_y[:, None] * grid.width + index_x[None, :]
    inside = (index_y[:, None] >= 0) & (index_x[None, :] >= 0)
    cells = grid.width * grid.height
    set_pixels = np.bincount(cell[inside & mask_on_source], minlength=cells)
    sizes = np.bincount(cell[inside], minlength=cells)
    result: BoolMask = ((set_pixels > 0) & (set_pixels < sizes)).reshape(grid.height, grid.width)
    return result


def mask_from_difference(full: U8, plate: U8, threshold: float) -> BoolMask:
    """Where two (H, W, 4) images of one size differ by more than `threshold` in OKLab distance.

    A pixel transparent in one image and not in the other differs; transparent in both, it doesn't, whatever its
    colour. Alpha is binary, so a pixel is either clear or opaque.
    """
    if full.shape != plate.shape or full.ndim != 3 or full.shape[2] != 4:
        raise ValueError(f"need two (H, W, 4) images of one size, got {full.shape} and {plate.shape}")
    if threshold < 0:
        raise ValueError(f"the threshold can't be negative, got {threshold}")
    distance = np.linalg.norm(srgb_to_oklab(full[..., :3]) - srgb_to_oklab(plate[..., :3]), axis=2)
    full_clear, plate_clear = full[..., 3] == 0, plate[..., 3] == 0
    result: BoolMask = np.where(full_clear | plate_clear, full_clear != plate_clear, distance > threshold)
    return result


def recompose(plate: U8, layers: Sequence[U8]) -> U8:
    """The Layers laid over the Plate in order, first to last, unblended: a painted pixel replaces what is below."""
    result = plate.copy()
    for layer in layers:
        result = overlay(result, layer)
    return result


def cut_by_alpha(image: U8, alpha: BoolMask) -> U8:
    """`image` where `alpha` is set, fully transparent (0, 0, 0, 0) elsewhere."""
    if image.ndim != 3 or image.shape[2] != 4 or alpha.dtype != np.bool_ or alpha.shape != image.shape[:2]:
        raise ValueError(f"need an (H, W, 4) image and a boolean mask of its size, got {image.shape} and {alpha.shape}")
    result = np.zeros_like(image)
    result[alpha] = image[alpha]
    return result


_FOUR = ((-1, 0), (1, 0), (0, -1), (0, 1))
_EIGHT = (*_FOUR, (-1, -1), (-1, 1), (1, -1), (1, 1))


def connected_regions(mask: BoolMask, *, eight: bool = False) -> list[npt.NDArray[np.int64]]:
    """The 4-connected regions of a binary Mask (8-connected with `eight`), each an (n, 2) array of (y, x) in raster order.

    Regions are ordered by their first pixel in raster order (top row first, then left to right), so the order is the
    same on every run.
    """
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    height, width = mask.shape
    steps = _EIGHT if eight else _FOUR
    seen = np.zeros_like(mask)
    regions: list[npt.NDArray[np.int64]] = []
    for y, x in np.argwhere(mask):
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack, found = [(int(y), int(x))], []
        while stack:
            cy, cx = stack.pop()
            found.append((cy, cx))
            for dy, dx in steps:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        regions.append(np.array(sorted(found), dtype=np.int64))
    return regions


def remove_small_pieces(mask: BoolMask, min_piece: int) -> BoolMask:
    """`mask` without its 8-connected pieces of fewer than `min_piece` pixels. 0 (or 1) removes nothing. The input is not
    modified. A piece is 8-connected, the same as in the layer statistics, so what they count small is what goes."""
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    if min_piece < 0:
        raise ValueError(f"min_piece can't be negative, got {min_piece}")
    result = mask.copy()
    if min_piece <= 1:
        return result
    for piece in connected_regions(mask, eight=True):
        if len(piece) < min_piece:
            result[piece[:, 0], piece[:, 1]] = False
    return result


def enclosed_holes(mask: BoolMask) -> BoolMask:
    """The pixels a binary Mask encloses without containing: clear pixels that can't reach the image edge through clear
    pixels, moving up, down, left or right (so a gap one pixel wide, even a diagonal one, doesn't let a hole out of an
    8-connected piece)."""
    if mask.dtype != np.bool_ or mask.ndim != 2:
        raise ValueError("a Mask is a 2-D boolean array")
    height, width = mask.shape
    outside = np.zeros_like(mask)
    stack = [(y, x) for y in range(height) for x in range(width)
             if (y in (0, height - 1) or x in (0, width - 1)) and not mask[y, x]]
    for y, x in stack:
        outside[y, x] = True
    while stack:
        cy, cx = stack.pop()
        for dy, dx in _FOUR:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < height and 0 <= nx < width and not mask[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True
                stack.append((ny, nx))
    result: BoolMask = ~mask & ~outside
    return result
