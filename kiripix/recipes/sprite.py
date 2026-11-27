"""The sprite Recipe (spec §6.4, ticket 0179): frames, fit, palette, finish, sheet, export.

An actor built from imported 2D frames, such as a PixelLab figure. From `palette` down it is the character's Recipe: the same
StageSpecs, made by the factories of ticket 0176 with `fit` as the Stage that holds the frame list, so the export is the
character's. A sprite has no material pass from a render: its parts are its colour regions, which its `palette` groups and
writes as one (ticket 0319). It has no `clips` Stage (its clips are in `frames`) and no normal pass (`finish` makes normals
from the silhouette by default).
"""

from dataclasses import replace

from kiripix.recipes.base import CheckSpec, KindSpec, ParamSpec, StageInputs, StageSpec, chain
from kiripix.recipes.character import CHARACTER
from kiripix.recipes.character_export import run_character_export
from kiripix.recipes.character_finish import finish_stage, normals_params
from kiripix.recipes.character_palette import SPRITE_HUE_GAP, SPRITE_SHADES, sprite_palette_stage
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
    palette_run, palette_check = sprite_palette_stage("fit")
    # `finish` draws inner lines from the material pass `palette` writes for a sprite's parts (ticket 0320); its Checks stay on
    # `fit`'s frames, which have no material pass, so `sheet.part_vanishes` (not a sprite's) finds nothing
    finish_run, _ = finish_stage("palette")
    _, finish_check = finish_stage("fit")
    sheet_run, sheet_check = sheet_stage("finish")
    palette = _CHARACTER["palette"]
    finish = _CHARACTER["finish"]
    kept = {"colors", "dither", "strength", "orphan_size", "part_lines"}
    palette_params = tuple(p for p in palette.params if p.name in kept) + (
        ParamSpec(name="parts", type="str", default="",
                  description="The swappable parts, comma-separated, each a colour region of palette.json's `regions` (by hue: "
                              "orange, blue_2, grey) or several joined by `+`, each with a ramp of `shades` palette colours, dark "
                              "to light; `name=regions` names a part apart from its regions. For example "
                              "skin=orange,top=grey,cap=green. With the Project's ramp table, every part must be a row of it, "
                              "which gives its length. Regions in no part take `colors` as before; empty for none."),
        ParamSpec(name="shades", type="int", minimum=1, default=SPRITE_SHADES,
                  description="With `parts`, each part's ramp length when the Project has no ramp table."),
        ParamSpec(name="hue_gap", type="float", minimum=2.0, maximum=180.0, default=SPRITE_HUE_GAP,
                  description="Degrees of OKLab hue between two neighbouring colours that splits them into two regions."),
    )
    finish_params = tuple(p.model_copy(update={"default": "edge"}) if p.name == "placement" else p
                          for p in finish.params if p.name not in {"watch_parts", "part_min_pixels"})
    return chain(
        StageSpec(
            name="frames",
            # 2: a PixelLab state's rotations are the state's clip, not `idle`; `leave_out` (ticket 0385).
            version=2,
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
                CheckSpec(code="clips.ticks_count", description="A clip's `ticks` has one duration per frame."),
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
            # 2: the pivot at the ground point, 0.08 of the figure above the feet; fit.json's `ground` (ticket 0318).
            # 3: fit.json records the source's partial alpha (`alpha`, `alpha_partial`), read by fit.alpha_partial (ticket 0363)
            # 4: with align_feet, a moving clip is placed whole by the median of its feet; fit.json's `unmeasured` (ticket 0392)
            version=4,
            description="Every frame onto the target pixel grid, its feet found, all placed on one cell around one pivot.",
            inputs=StageInputs(upstream=["frames"], settings=["character.height"]),
            params=FIT_PARAMS,
            decisions=(PIVOT,),
            checks=(
                CheckSpec(code="fit.grid_differs", description="Every frame has the same pixel scale."),
                CheckSpec(code="fit.alpha_partial", description="Every pixel is opaque or clear; and a warning when the source had "
                                                                 "partial alpha, with its share (the vote or the dither changed it)."),
                CheckSpec(code="fit.height", description="The tallest figure's height against the target and the game's "
                                                          "band (info)."),
                CheckSpec(code="fit.cell_grew", description="A frame far from the others that widened the cell (info)."),
                CheckSpec(code="fit.clip_unmeasured", description="A moving clip with no measurable feet keeps its place (info)."),
            ),
            run=run_sprite_fit,
            check=check_sprite_fit,
            owner_input="A `pivot` Decision, only when the measured feet are wrong.",
            available_from="M4",
        ),
        replace(palette, inputs=StageInputs(upstream=["fit"], settings=["palette", "character.ramps"]),
                version=palette.version + 1,  # colour regions as parts, `shades`, palette.json's `regions`, the material pass (ticket 0319)
                params=palette_params,
                checks=palette.checks + (
                    CheckSpec(code="palette.sprite_regions", description="The sprite's colour regions, while it has no "
                                                                         "`parts` (info)."),),
                run=palette_run, check=palette_check, available_from="M4"),
        replace(finish, inputs=StageInputs(upstream=["palette", "fit"], settings=["palette"]),
                version=_CHARACTER["finish"].version + 1,  # inner lines between a sprite's parts (ticket 0320)
                params=finish_params + normals_params("height"),
                checks=tuple(c for c in finish.checks if c.code not in ("sheet.part_vanishes", "sheet.eyes_covered")),
                run=finish_run, check=finish_check, available_from="M4"),
        replace(_CHARACTER["sheet"], inputs=StageInputs(upstream=["finish"]), run=sheet_run, check=sheet_check,
                available_from="M4"),
        replace(_CHARACTER["export"], inputs=StageInputs(upstream=["sheet", "palette"], settings=["export.godot"]),
                params=(
                    ParamSpec(name="blend", type="choice", choices=["mix", "add"], default="mix",
                              description="How the game draws the sprite: `mix` (normal) or `add` (additive, for glows and "
                                          "sparks). At `add` the scene's AnimatedSprite2D takes a shared CanvasItemMaterial."),
                    ParamSpec(name="lit", type="bool", default=True,
                              description="Whether the room's lights touch the sprite. False draws it unshaded (the scene's "
                                          "material has light_mode unshaded), as a room's Loops are."),
                ),
                run=run_character_export, available_from="M4"),
    )


SPRITE = KindSpec(
    name="sprite",
    description="An actor built from imported 2D frames, such as a PixelLab figure, exported exactly as a character is.",
    stages=_stages(),
    takes_sheets=True,
)
