"""Palette files: GIMP `.gpl` (stored) and `.hex` (imported). Text in, data out; no I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

from kiripix.ops.colour import srgb_to_oklab


@dataclass(frozen=True)
class PaletteEntry:
    """One palette line as written in the file. `alpha` is kept so that a Check can refuse it."""

    r: int
    g: int
    b: int
    alpha: int = 255
    name: str = ""
    line: int = 0

    @property
    def hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"


@dataclass(frozen=True)
class Palette:
    """An ordered list of colours. Order matters: it breaks ties in nearest-colour mapping."""

    name: str
    entries: tuple[PaletteEntry, ...]

    def rgb(self) -> npt.NDArray[np.uint8]:
        """The colours as an (N, 3) uint8 array, in palette order."""
        return np.array([(e.r, e.g, e.b) for e in self.entries], dtype=np.uint8).reshape(-1, 3)


class PaletteSyntaxError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


def parse_gpl(text: str) -> Palette:
    """Parse a GIMP palette. Supports the `Channels: RGBA` extension, so that alpha can be reported."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "GIMP Palette":
        raise PaletteSyntaxError(1, "expected the header 'GIMP Palette'")
    name = ""
    channels = 3
    entries: list[PaletteEntry] = []
    for number, raw in enumerate(lines[1:], start=2):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("Name:"):
            name = line[5:].strip()
            continue
        if line.startswith("Columns:"):
            continue
        if line.startswith("Channels:"):
            value = line[9:].strip().upper()
            if value not in ("RGB", "RGBA"):
                raise PaletteSyntaxError(number, f"unknown channels '{value}'")
            channels = len(value)
            continue
        parts = line.split(None, channels)
        try:
            values = [int(p) for p in parts[:channels]]
        except ValueError:
            raise PaletteSyntaxError(number, f"expected {channels} numbers, got '{line}'") from None
        if len(values) < channels or any(not 0 <= v <= 255 for v in values):
            raise PaletteSyntaxError(number, f"expected {channels} numbers from 0 to 255, got '{line}'")
        colour_name = parts[channels].strip() if len(parts) > channels else ""
        alpha = values[3] if channels == 4 else 255
        entries.append(PaletteEntry(values[0], values[1], values[2], alpha, colour_name, number))
    return Palette(name, tuple(entries))


_HEX_LINE = re.compile(r"^#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")


def parse_hex(text: str, name: str = "") -> Palette:
    """Parse a `.hex` palette: one `RRGGBB` (or `RRGGBBAA`) per line, `#` optional."""
    entries: list[PaletteEntry] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        match = _HEX_LINE.match(line)
        if not match:
            raise PaletteSyntaxError(number, f"expected RRGGBB, got '{line}'")
        rgb = match.group(1)
        alpha = int(match.group(2), 16) if match.group(2) else 255
        entries.append(PaletteEntry(int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16), alpha, "", number))
    return Palette(name, tuple(entries))


@dataclass(frozen=True)
class PaletteSuggestion:
    """New colours for a palette, most-used first, and the mean OKLab distance from the image's opaque pixels to their
    nearest palette colour before and after adding them."""

    colours: npt.NDArray[np.uint8]  # (K, 3), K <= the count asked for
    error_before: float
    error_after: float


_LLOYD_ROUNDS = 12


_CHUNK = 1 << 14  # colours per distance block, so the (colours x centres) array stays small


def _squared_distances(lab: npt.NDArray[np.float64], centres: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """(len(lab), len(centres)) squared OKLab distances, computed a block of colours at a time."""
    out = np.empty((len(lab), len(centres)), dtype=np.float64)
    for start in range(0, len(lab), _CHUNK):
        chunk = lab[start : start + _CHUNK]
        out[start : start + _CHUNK] = ((chunk[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
    return out


def _nearest_distance(lab: npt.NDArray[np.float64], centres: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    out: npt.NDArray[np.float64] = np.sqrt(_squared_distances(lab, centres).min(axis=1))
    return out


def suggest_palette(
    rgba: npt.NDArray[np.uint8], palette_rgb: npt.NDArray[np.uint8], count: int, min_distance: float
) -> PaletteSuggestion:
    """Up to `count` colours that the palette lacks for this image.

    Clusters the image's opaque pixels in OKLab with the palette's colours fixed as clusters. New clusters are seeded one
    at a time where the pixels, weighted by how many there are, are worst served by the palette and the clusters chosen so
    far (the largest count times squared distance; ties go to the smaller colour), then refined by a fixed number of
    Lloyd rounds. A seed farther than `min_distance` from every existing or chosen colour is needed to start a cluster, and
    a result within `min_distance` of an existing or earlier colour is dropped, so fewer than `count` may come back.
    Transparent pixels are ignored; the same input gives the same colours.
    """
    if count < 0:
        raise ValueError("the count can't be negative")
    if len(palette_rgb) == 0:
        raise ValueError("the palette has no colours")
    opaque = rgba[..., 3] >= 128
    pixels = rgba[..., :3][opaque]
    empty = np.zeros((0, 3), dtype=np.uint8)
    if len(pixels) == 0:
        return PaletteSuggestion(empty, 0.0, 0.0)
    colours, weights = np.unique(pixels, axis=0, return_counts=True)
    w = weights.astype(np.float64)
    lab = srgb_to_oklab(colours)
    fixed = srgb_to_oklab(palette_rgb)
    total = float(w.sum())
    before = float((_nearest_distance(lab, fixed) * w).sum() / total)
    if count == 0:
        return PaletteSuggestion(empty, before, before)

    # Seed: the colour the current centres serve worst, by count times squared distance.
    nearest = _nearest_distance(lab, fixed)
    seeds: list[int] = []
    for _ in range(count):
        score = np.round(w * nearest**2, 12)
        score[nearest < min_distance] = 0.0
        pick = int(score.argmax())
        if score[pick] <= 0.0:
            break
        seeds.append(pick)
        nearest = np.minimum(nearest, np.sqrt(((lab - lab[pick]) ** 2).sum(axis=1)))
    if not seeds:
        return PaletteSuggestion(empty, before, before)

    new = lab[seeds].copy()
    rgb_f = colours.astype(np.float64)
    owner = np.zeros(len(lab), dtype=np.intp)
    for _ in range(_LLOYD_ROUNDS):
        both = np.concatenate([fixed, new])
        d2 = np.round(_squared_distances(lab, both), 12)
        owner = d2.argmin(axis=1)  # ties go to the lower index: the palette first, then older clusters
        moved = False
        for k in range(len(new)):
            members = owner == len(fixed) + k
            if members.any():
                centre = (lab[members] * w[members, None]).sum(axis=0) / w[members].sum()
                if not np.array_equal(centre, new[k]):
                    new[k] = centre
                    moved = True
        if not moved:
            break

    chosen: list[tuple[int, int, int]] = []
    weight: list[float] = []
    for k in range(len(new)):
        members = owner == len(fixed) + k
        if not members.any():
            continue
        mean = (rgb_f[members] * w[members, None]).sum(axis=0) / w[members].sum()
        chosen.append((int(np.round(mean[0])), int(np.round(mean[1])), int(np.round(mean[2]))))
        weight.append(float(w[members].sum()))
    order = sorted(range(len(chosen)), key=lambda i: (-weight[i], i))
    kept: list[tuple[int, int, int]] = []
    for i in order:
        candidate = np.array([chosen[i]], dtype=np.uint8)
        pool = np.concatenate([palette_rgb, np.array(kept, dtype=np.uint8).reshape(-1, 3)])
        if _nearest_distance(srgb_to_oklab(candidate), srgb_to_oklab(pool))[0] >= min_distance:
            kept.append(chosen[i])
    result = np.array(kept, dtype=np.uint8).reshape(-1, 3)
    after_lab = np.concatenate([fixed, srgb_to_oklab(result)]) if len(result) else fixed
    after = float((_nearest_distance(lab, after_lab) * w).sum() / total)
    return PaletteSuggestion(result, before, after)


def format_gpl(palette: Palette) -> str:
    """Write a GIMP palette, LF line endings."""
    lines = ["GIMP Palette", f"Name: {palette.name}", "#"]
    for e in palette.entries:
        lines.append(f"{e.r:3d} {e.g:3d} {e.b:3d}\t{e.name or e.hex}")
    return "\n".join(lines) + "\n"
