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
from kiripix.ops.compose import overlay
from kiripix.ops.palette import Palette, PaletteEntry, PaletteSyntaxError, format_gpl, parse_gpl, parse_hex
from kiripix.ops.resample import (
    Grid,
    detect_grid,
    downscale_mode,
    mask_to_source,
    mask_to_target,
    point_to_target,
    sample_nearest,
    target_centre,
    upscale,
)

__all__ = [
    "BayerSize",
    "ConformanceReport",
    "Grid",
    "Palette",
    "PaletteEntry",
    "PaletteSyntaxError",
    "bayer_matrix",
    "conformance",
    "detect_grid",
    "downscale_mode",
    "format_gpl",
    "has_partial_alpha",
    "mask_to_source",
    "mask_to_target",
    "nearest_index",
    "overlay",
    "parse_gpl",
    "parse_hex",
    "point_to_target",
    "quantize",
    "sample_nearest",
    "srgb_to_oklab",
    "target_centre",
    "upscale",
]
