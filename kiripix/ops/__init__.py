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
from kiripix.ops.geometry import NavigationPolygon, Outline, collision_shapes, contours, navigation_polygon, simplify
from kiripix.ops.layers import (
    connected_regions,
    cut_by_alpha,
    grow_where_partial,
    mask_from_difference,
    partial_cells,
    recompose,
)
from kiripix.ops.masks import flood_region, mask_runs, paint_stroke, snap_cell, split_painted
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
    "NavigationPolygon",
    "Outline",
    "Palette",
    "PaletteEntry",
    "PaletteSyntaxError",
    "bayer_matrix",
    "collision_shapes",
    "conformance",
    "connected_regions",
    "contours",
    "cut_by_alpha",
    "detect_grid",
    "downscale_mode",
    "flood_region",
    "format_gpl",
    "grow_where_partial",
    "has_partial_alpha",
    "mask_from_difference",
    "mask_runs",
    "mask_to_source",
    "mask_to_target",
    "nearest_index",
    "overlay",
    "narrowest_gaps",
    "navigation_polygon",
    "paint_stroke",
    "parse_gpl",
    "parse_hex",
    "partial_cells",
    "point_to_target",
    "quantize",
    "reachable",
    "recompose",
    "remove_orphans",
    "sample_nearest",
    "simplify",
    "snap_cell",
    "split_painted",
    "srgb_to_oklab",
    "target_centre",
    "upscale",
    "walkable",
    "walkable_islands",
]
