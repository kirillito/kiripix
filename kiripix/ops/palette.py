"""Palette files: GIMP `.gpl` (stored) and `.hex` (imported). Text in, data out; no I/O."""

import re
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


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


def format_gpl(palette: Palette) -> str:
    """Write a GIMP palette, LF line endings."""
    lines = ["GIMP Palette", f"Name: {palette.name}", "#"]
    for e in palette.entries:
        lines.append(f"{e.r:3d} {e.g:3d} {e.b:3d}\t{e.name or e.hex}")
    return "\n".join(lines) + "\n"
