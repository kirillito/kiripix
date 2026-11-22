"""Check functions returning findings. Imports only `ops` from the rest of Kiripix."""

from kiripix.checks.cutout import check_chroma_cutout
from kiripix.checks.finding import Finding, Position, Severity
from kiripix.checks.join import check_join_gain, check_join_residual, check_seam_difference
from kiripix.checks.palette import check_alpha, check_conformance, check_mapping_error, check_palette

from kiripix.checks.parts import EyeCover, PartCounts, check_eyes_covered, check_part_vanishes
from kiripix.checks.npc import (
    LayerFrame,
    buried_by_order,
    check_colour_choice,
    check_npc_stack,
    check_part_unset,
    check_wearable_body,
)
from kiripix.checks.ramps import check_ramp_shared
from kiripix.checks.style import check_outline_density, check_pixel_scale, check_style_measures
from kiripix.checks.stack import StackFrame, check_stack_differs
from kiripix.checks.sheet import (
    SheetFrame,
    check_empty_frame,
    check_frame_count,
    check_frame_overflow,
    check_normal_size,
    check_pivot_drift,
)

__all__ = ["check_outline_density", "check_pixel_scale", "check_style_measures", "Finding", "Position", "Severity", "SheetFrame", "check_alpha", "check_chroma_cutout", "check_conformance",
           "check_empty_frame", "check_frame_count", "check_frame_overflow", "check_join_gain", "check_join_residual", "check_seam_difference", "check_mapping_error",
           "check_normal_size", "check_palette", "check_part_vanishes", "check_pivot_drift", "check_ramp_shared",
           "LayerFrame", "buried_by_order", "check_colour_choice", "check_npc_stack", "check_part_unset", "check_wearable_body",
           "PartCounts", "StackFrame", "check_stack_differs", "EyeCover", "check_eyes_covered"]
