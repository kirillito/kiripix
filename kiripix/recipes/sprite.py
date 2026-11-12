"""The sprite Recipe (spec §6.4, ticket 0179): frames, fit, palette, finish, sheet, export.

An actor built from imported 2D frames, such as a PixelLab figure. From `palette` down it is the character's Recipe: the same
StageSpecs, made by the factories of ticket 0176 with `fit` as the Stage that holds the frame list, so the export is the
character's. A sprite has no part ramps (no material pass), no `clips` Stage (its clips are in `frames`) and no normal pass
(`finish` makes normals from the silhouette by default).
"""

from dataclasses import replace

from kiripix.recipes.base import CheckSpec, KindSpec, StageInputs, StageSpec, chain
from kiripix.recipes.character import CHARACTER
from kiripix.recipes.character_export import run_character_export
from kiripix.recipes.character_finish import finish_stage, normals_params
from kiripix.recipes.character_palette import palette_stage
from kiripix.recipes.character_sheet import sheet_stage
from kiripix.recipes.sprite_fit import FIT_PARAMS, PIVOT, check_sprite_fit, run_sprite_fit
from kiripix.recipes.sprite_frames import (
    CLIP,
    DIRECTIONS_PARAM,
    SHEET,
    check_frames,
    frames_needs_input,
    run_frames,
)

_CHARACTER = {stage.name: stage for stage in CHARACTER.stages}


def _stages() -> tuple[StageSpec, ...]:
    palette_run, palette_check = palette_stage("fit")
    finish_run, finish_check = finish_stage("fit")
    sheet_run, sheet_check = sheet_stage("finish")
    palette = _CHARACTER["palette"]
    finish = _CHARACTER["finish"]
    kept = {"colors", "dither", "strength", "orphan_size"}  # `parts` is for a material pass, which a sprite has none of
    finish_params = tuple(p.model_copy(update={"default": "edge"}) if p.name == "placement" else p
                          for p in finish.params if p.name not in {"watch_parts", "part_min_pixels"})
    return chain(
        StageSpec(
            name="frames",
            description="Cuts the imported sheets into clip, direction and frame at source resolution.",
            inputs=StageInputs(files=["src/sheets/*"]),
            params=(DIRECTIONS_PARAM,),
            decisions=(SHEET, CLIP),
            checks=(
                CheckSpec(code="frames.direction_missing", description="Every clip has every direction the sprite asks for; "
                                                                       "none is mirrored."),
                CheckSpec(code="frames.frame_count", description="A clip's directions have the same number of frames (a "
                                                                 "warning)."),
                CheckSpec(code="frames.unknown_direction", description="Every entry of a ZIP is placed by its direction (a "
                                                                       "warning)."),
                CheckSpec(code="clips.bad_name", description="A clip name is lower-case snake_case with no direction suffix."),
                CheckSpec(code="clips.duplicate_name", description="No clip gets the same direction and frame from two sources."),
            ),
            run=run_frames,
            check=check_frames,
            needs_input=frames_needs_input,
            owner_input="Imports sheets (kiripix import <id> <file.png|file.zip> --role sheet), says how a PNG's rows map to "
                        "directions (`sheet`) and sets a clip's frame rate, loop and stationary flags (`clip`).",
            available_from="M4",
        ),
        StageSpec(
            name="fit",
            description="Every frame onto the target pixel grid, its feet found, all placed on one cell around one pivot.",
            inputs=StageInputs(upstream=["frames"], settings=["character.height"]),
            params=FIT_PARAMS,
            decisions=(PIVOT,),
            checks=(
                CheckSpec(code="fit.grid_differs", description="Every frame has the same pixel scale."),
                CheckSpec(code="fit.alpha_partial", description="Every pixel is opaque or clear."),
                CheckSpec(code="fit.height", description="The tallest figure's height against the target and the game's "
                                                          "band (info)."),
                CheckSpec(code="fit.cell_grew", description="A frame far from the others that widened the cell (info)."),
            ),
            run=run_sprite_fit,
            check=check_sprite_fit,
            owner_input="A `pivot` Decision, only when the measured feet are wrong.",
            available_from="M4",
        ),
        replace(palette, inputs=StageInputs(upstream=["fit"], settings=["palette"]),
                params=tuple(p for p in palette.params if p.name in kept),
                checks=tuple(c for c in palette.checks if c.code != "palette.ramp_shared"),
                run=palette_run, check=palette_check, available_from="M4"),
        replace(finish, inputs=StageInputs(upstream=["palette", "fit"], settings=["palette"]),
                params=finish_params + normals_params("height"),
                checks=tuple(c for c in finish.checks if c.code != "sheet.part_vanishes"),
                run=finish_run, check=finish_check, available_from="M4"),
        replace(_CHARACTER["sheet"], inputs=StageInputs(upstream=["finish"]), run=sheet_run, check=sheet_check,
                available_from="M4"),
        replace(_CHARACTER["export"], inputs=StageInputs(upstream=["sheet", "palette"], settings=["export.godot"]),
                run=run_character_export, available_from="M4"),
    )


SPRITE = KindSpec(
    name="sprite",
    description="An actor built from imported 2D frames, such as a PixelLab figure, exported exactly as a character is.",
    stages=_stages(),
    takes_sheets=True,
)
