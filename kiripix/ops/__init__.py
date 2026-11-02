"""Pure image functions (spec §7): numpy arrays in, arrays out. No I/O, no global state.

Imports nothing else from Kiripix.
"""

from kiripix.ops.colour import (
    BayerSize,
    ConformanceReport,
    bayer_matrix,
    conformance,
    has_partial_alpha,
    nearest_index,
    quantize,
    srgb_to_oklab,
)
from kiripix.ops.palette import Palette, PaletteEntry, PaletteSyntaxError, format_gpl, parse_gpl, parse_hex

__all__ = [
    "BayerSize",
    "ConformanceReport",
    "Palette",
    "PaletteEntry",
    "PaletteSyntaxError",
    "bayer_matrix",
    "conformance",
    "format_gpl",
    "has_partial_alpha",
    "nearest_index",
    "parse_gpl",
    "parse_hex",
    "quantize",
    "srgb_to_oklab",
]
