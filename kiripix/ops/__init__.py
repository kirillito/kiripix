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
from kiripix.ops.cleanup import remove_orphans
from kiripix.ops.compose import overlay
from kiripix.ops.masks import flood_region, paint_stroke, snap_cell, split_painted
from kiripix.ops.palette import Palette, PaletteEntry, PaletteSyntaxError, format_gpl, parse_gpl, parse_hex
from kiripix.ops.reach import walkable
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
    "flood_region",
    "format_gpl",
    "has_partial_alpha",
    "mask_to_source",
    "mask_to_target",
    "nearest_index",
    "overlay",
    "paint_stroke",
    "parse_gpl",
    "parse_hex",
    "point_to_target",
    "quantize",
    "remove_orphans",
    "sample_nearest",
    "snap_cell",
    "split_painted",
    "srgb_to_oklab",
    "target_centre",
    "upscale",
    "walkable",
]
