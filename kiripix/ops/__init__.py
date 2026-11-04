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
from kiripix.ops.reach import Gap, Island, narrowest_gaps, reachable, walkable, walkable_islands
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
    "Gap",
    "Grid",
    "Island",
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
    "narrowest_gaps",
    "paint_stroke",
    "parse_gpl",
    "parse_hex",
    "point_to_target",
    "quantize",
    "reachable",
    "remove_orphans",
    "sample_nearest",
    "snap_cell",
    "split_painted",
    "srgb_to_oklab",
    "target_centre",
    "upscale",
    "walkable",
    "walkable_islands",
]
