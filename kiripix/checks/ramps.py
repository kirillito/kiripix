"""The ramp Check (spec §6.3, ticket 0149): does every part keep to colours that are its own?"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks.finding import Finding, Position

FIXED = "fixed colours"  # what the finding calls the pixels of materials that are in no part


def _packed(rgb: Any) -> Any:
    rgb = rgb.astype(np.int64)
    return (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]


def check_ramp_shared(
    rgba: Any,
    labels: Any,
    parts: Mapping[str, Collection[int]],
    ramps: Mapping[str, Any],
    file: str,
    fix: str,
) -> list[Finding]:
    """`palette.ramp_shared` for each pair of parts that share a colour, and for each part whose ramp colour is in
    a pixel of another part (or of a fixed material). `fix` is the command that rebuilds the palette.

    A pair of ramps with a colour in common gives one finding naming both parts. A pixel of part B in a colour of
    part A's ramp gives one finding per (B, A) pair, naming both and the first such pixel in row-major order. Only
    opaque pixels count. The findings come in the order of `ramps`.
    """
    findings: list[Finding] = []
    names = list(ramps)
    owned = {name: set(_packed(np.asarray(ramps[name]).reshape(-1, 3)).tolist()) for name in names}
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            common = owned[first] & owned[second]
            if common:
                colour = "#%06x" % min(common)
                findings.append(Finding(
                    code="palette.ramp_shared", fix=fix, position=Position(file=file),
                    message=f"the ramps of {first} and {second} share {colour}: swapping one would recolour the other"))
    opaque = rgba[..., 3] == 255
    packed = _packed(rgba[..., :3])
    claimed = np.zeros(opaque.shape, dtype=bool)
    where: dict[str, Any] = {}
    for name, materials in parts.items():
        where[name] = opaque & np.isin(labels, np.array(sorted(materials), dtype=np.int64))
        claimed |= where[name]
    where[FIXED] = opaque & ~claimed
    for pixels_of, pixels in where.items():
        for ramp_of in names:
            if ramp_of == pixels_of or ramp_of not in ramps:
                continue
            hit = pixels & np.isin(packed, np.array(sorted(owned[ramp_of]), dtype=np.int64))
            if hit.any():
                ys, xs = np.nonzero(hit)
                x, y = int(xs[0]), int(ys[0])
                findings.append(Finding(
                    code="palette.ramp_shared", fix=fix, position=Position(file=file, x=x, y=y),
                    message=f"{file}: a pixel of {pixels_of} at ({x}, {y}) has a colour of the ramp of {ramp_of} "
                            f"({int(hit.sum())} such pixels): swapping {ramp_of} would recolour it"))
    return findings
