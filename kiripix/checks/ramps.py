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


class RampLookup:
    """What `check_ramp_shared` needs from the parts and ramps, which are the same for every frame of a character (ticket
    0368): build it once per Check and pass it to each call."""

    def __init__(self, parts: Mapping[str, Collection[int]], ramps: Mapping[str, Any]) -> None:
        self.names = list(ramps)
        self.parts = {name: sorted(int(m) for m in materials) for name, materials in parts.items()}
        owned = {name: set(_packed(np.asarray(ramps[name]).reshape(-1, 3)).tolist()) for name in self.names}
        self.shared: list[tuple[str, str, str]] = []  # (first, second, the lowest colour they share)
        for i, first in enumerate(self.names):
            for second in self.names[i + 1:]:
                common = owned[first] & owned[second]
                if common:
                    self.shared.append((first, second, "#%06x" % min(common)))
        self.colours = np.array(sorted(set().union(*owned.values())), dtype=np.int64)  # every ramp colour, ascending
        self.member = np.zeros((len(self.colours), len(self.names)), dtype=bool)  # [colour, ramp]: the colour is in the ramp
        for r, name in enumerate(self.names):
            self.member[np.searchsorted(self.colours, np.array(sorted(owned[name]), dtype=np.int64)), r] = True
        self.size = max([256] + [m + 1 for materials in self.parts.values() for m in materials])
        self.tables = {name: self._table(materials) for name, materials in self.parts.items()}

    def _table(self, materials: list[int]) -> Any:
        table = np.zeros(self.size, dtype=bool)
        table[[m for m in materials if m >= 0]] = True
        return table

    def in_part(self, name: str, labels: Any) -> Any:
        """The pixels whose label is a material of the part."""
        if labels.size and (int(labels.min()) < 0 or int(labels.max()) >= self.size):
            return np.isin(labels, np.array(self.parts[name], dtype=np.int64))
        return self.tables[name][labels]


def check_ramp_shared(
    rgba: Any,
    labels: Any,
    parts: Mapping[str, Collection[int]],
    ramps: Mapping[str, Any],
    file: str,
    fix: str,
    lookup: RampLookup | None = None,
) -> list[Finding]:
    """`palette.ramp_shared` for each pair of parts that share a colour, and for each part whose ramp colour is in
    a pixel of another part (or of a fixed material). `fix` is the command that rebuilds the palette.

    A pair of ramps with a colour in common gives one finding naming both parts. A pixel of part B in a colour of
    part A's ramp gives one finding per (B, A) pair, naming both and the first such pixel in row-major order. Only
    opaque pixels count. The findings come in the order of `ramps`.

    `lookup` is `RampLookup(parts, ramps)`, built once for all the frames of one Check; without it, one is built here.
    """
    if lookup is None:
        lookup = RampLookup(parts, ramps)
    names = lookup.names
    findings: list[Finding] = []
    for first, second, colour in lookup.shared:
        findings.append(Finding(
            code="palette.ramp_shared", fix=fix, position=Position(file=file),
            message=f"the ramps of {first} and {second} share {colour}: swapping one would recolour the other"))
    if not names:
        return findings
    opaque = rgba[..., 3] == 255
    packed = _packed(rgba[..., :3])
    # Only the opaque pixels that have a colour of some ramp can be a finding: work on those, in row-major order.
    at = np.minimum(np.searchsorted(lookup.colours, packed), len(lookup.colours) - 1)
    flat = np.flatnonzero(opaque & (lookup.colours[at] == packed))
    if not flat.size:
        return findings
    colour_at = at.reshape(-1)[flat]
    sub_labels = labels.reshape(-1)[flat]
    in_ramp = lookup.member[colour_at]  # [pixel, ramp]
    claimed = np.zeros(flat.size, dtype=bool)
    groups: dict[str, Any] = {}
    for name in lookup.parts:
        groups[name] = lookup.in_part(name, sub_labels)
        claimed |= groups[name]
    groups[FIXED] = ~claimed
    width = opaque.shape[1]
    for pixels_of, pixels in groups.items():
        for r, ramp_of in enumerate(names):
            if ramp_of == pixels_of:
                continue
            hit = pixels & in_ramp[:, r]
            if hit.any():
                y, x = divmod(int(flat[int(np.argmax(hit))]), width)
                findings.append(Finding(
                    code="palette.ramp_shared", fix=fix, position=Position(file=file, x=x, y=y),
                    message=f"{file}: a pixel of {pixels_of} at ({x}, {y}) has a colour of the ramp of {ramp_of} "
                            f"({int(hit.sum())} such pixels): swapping {ramp_of} would recolour it"))
    return findings
