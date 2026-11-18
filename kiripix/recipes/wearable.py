"""The wearable Recipe (spec §3, §6.3, tickets 0290, 0291): model, rig, render, palette, finish, sheet, export.

A Wearable is one part of a character's dress, such as hair or a jacket: its own Model on the body's skeleton, rendered
with the body's clips, camera and cell, so that its frames stack on the body's. It is an Asset that names its body (a
character: a sprite has no Model to hold out) in its `body` parameter; it has no `clips` Stage, because the body's are used, not copied.

`model`, `rig` and `render` are built (`wearable_render.py`): they read the body's built Stages, so each waits (needs-input,
naming the body's Stage and the command that builds it) while the body isn't built. A change to the body's `model`, `rig`,
`clips` or `render` (whose input hash holds the cell) makes `render`, and everything below it, stale. `palette` and `finish`
(0292) and `sheet` and `export` (0293) are built too: the sheet has the body's cell, pivot and layout with colour, normal and
depth atlases and the default stacking `order`; `export` leaves `wearable.json` (see `wearable_export.py`).
"""

from dataclasses import replace

from kiripix.recipes.base import BODY_PARAM, BodyInputs, CheckSpec, KindSpec, ParamSpec, StageInputs, StageSpec, chain
from kiripix.recipes.blender_launcher import SETTING as BLENDER_SETTING
from kiripix.recipes.blender_launcher import VERSION_SETTING as BLENDER_VERSION_SETTING
from kiripix.recipes.character import CHARACTER
from kiripix.recipes.character_finish import check_character_finish
from kiripix.recipes.character_palette import check_character_palette
from kiripix.recipes.render import FORMAT_SETTING as RENDER_FORMAT_SETTING
from kiripix.recipes.wearable_export import check_wearable_export, export_needs_input, run_wearable_export
from kiripix.recipes.wearable_sheet import ORDER, check_wearable_sheet, run_wearable_sheet
from kiripix.recipes.wearable_palette import DROPPED_FINISH, run_wearable_finish, run_wearable_palette
from kiripix.recipes.wearable_render import check_wearable_render, run_wearable_model, run_wearable_render, run_wearable_rig

_MODEL = next(stage for stage in CHARACTER.stages if stage.name == "model")
_PALETTE = next(stage for stage in CHARACTER.stages if stage.name == "palette")
_FINISH = next(stage for stage in CHARACTER.stages if stage.name == "finish")
_SHEET = next(stage for stage in CHARACTER.stages if stage.name == "sheet")

# What of the body a Wearable's `render` follows, by the body's Kind. A character: its Model, its skeleton, its clips and
# its render, whose input hash holds the camera, the height and so the cell and pivot.
BODY_STAGES = {"character": ["model", "rig", "clips", "render"]}

WEARABLE = KindSpec(
    name="wearable",
    description="One part of a character's dress, such as hair or a jacket: its own Model on the body's skeleton, rendered "
                "with the body's clips and cell, to be stacked over the body in the game.",
    params=(
        ParamSpec(name=BODY_PARAM, type="str", required=True,
                  description="The body this is worn on: a character, by its ID, such as character.body_m. Its "
                              "Model, rig, clips and cell make the Wearable stale when they change; its cell and pivot are "
                              "the Wearable's. A Wearable is never a body."),
    ),
    takes_body=("character",),  # a sprite has no Model to hold out (the glossary's Wearable)
    stages=chain(
        replace(_MODEL, description="Imports .glb, .fbx or .blend, or builds the Model from a parameter file with the "
                                    "Project's generator; normalises the up axis. The Model is this part alone, on the body's "
                                    "skeleton, turned and scaled as the body's Model is, whatever its own size.",
                version=2,  # normalised by the body's `model_root`, not by its own height (ticket 0291)
                inputs=_MODEL.inputs.model_copy(update={"body": BodyInputs(built={"character": ["model"]}, wait=True)}),
                params=tuple(p for p in _MODEL.params if p.name != "facing"), run=run_wearable_model),
        StageSpec(
            name="rig",
            description="Checks that the Wearable's Model carries the body's skeleton, bone for bone: every bone under its "
                        "exact name and parent, none added.",
            inputs=StageInputs(upstream=["model"], settings=[BLENDER_VERSION_SETTING], given=[BLENDER_SETTING],
                               body=BodyInputs(built={"character": ["rig"]}, wait=True)),
            checks=(CheckSpec(code="wearable.rig_mismatch",
                              description="The Wearable's armature has the body's bones by name and parent, and no other."),),
            run=run_wearable_rig,
            available_from="M5",
        ),
        StageSpec(
            name="render",
            description="Renders the Wearable with the body's clips, camera and cell, the body a holdout (it hides what is "
                        "behind it and isn't drawn): colour, normal, depth, mask and material passes, no outline, and the "
                        "frames stay inside the body's cell. render.json records the render seconds.",
            version=2,  # the first render that builds anything (ticket 0291)
            inputs=StageInputs(upstream=["model", "rig"], settings=[BLENDER_VERSION_SETTING, RENDER_FORMAT_SETTING],
                               given=[BLENDER_SETTING], body=BodyInputs(built=BODY_STAGES, wait=True)),
            gpu=True,
            run=run_wearable_render,
            check=check_wearable_render,
            checks=(CheckSpec(code="wearable.outside_cell",
                              description="Every frame fits the body's cell; the finding names the frames, and the fix is "
                                          "the body's `cell_margin`."),),
            available_from="M5",
        ),
        replace(
            _PALETTE,
            description="The Wearable's palette, from the Project's: one subset and a ramp per part, every colour apart from its "
                        "body's (its fixed colours and its parts' ramps), so recolouring it touches nothing else. Hair reuses "
                        "the `hair` row of the ramp table; outfits `top`, `under`, `bottom`, `shoes`.",
            version=2,  # the first palette that builds anything (ticket 0292)
            inputs=_PALETTE.inputs.model_copy(update={"upstream": ["render"],
                                                      "body": BodyInputs(built={"character": ["palette"]}, wait=True)}),
            checks=_PALETTE.checks + (CheckSpec(code="wearable.ramp_shared",
                                                description="No colour of the Wearable's parts is in its body's palette."),),
            run=run_wearable_palette, check=check_character_palette, available_from="M5"),
        replace(
            _FINISH,
            description="The normal pass quantised and aligned to the colour frames as the body's; no outline (the game draws "
                        "one on the stack).",
            version=4,  # 3: the first finish that builds anything (ticket 0292); 4: the body's `normal_levels`
            inputs=_FINISH.inputs.model_copy(update={"body": BodyInputs(built={"character": ["finish"]}, wait=True)}),
            params=tuple(
                p.model_copy(update={"choices": ["off", "dark"]}) if p.name == "inner_lines" else p
                for p in _FINISH.params if p.name not in DROPPED_FINISH),
            checks=tuple(c for c in _FINISH.checks if c.code != "sheet.eyes_covered"),
            run=run_wearable_finish, check=check_character_finish, available_from="M5"),
        StageSpec(
            name="sheet",
            description="Packs the frames into colour, normal and depth atlases on the body's cell, pivot and frame layout, so "
                        "that a Wearable lies pixel for pixel on the body, and records its default stacking order.",
            version=2,  # the first sheet that builds anything (ticket 0293)
            inputs=StageInputs(upstream=["finish", "render"]),
            params=(ORDER,),
            checks=_SHEET.checks,
            run=run_wearable_sheet, check=check_wearable_sheet, available_from="M5"),
        StageSpec(
            name="export",
            description="The Wearable's three atlases and wearable.json (its body, stacking order, parts and ramps), then a "
                        "SpriteFrames, a CanvasTexture and a scene for the game.",
            version=2,  # the first export that builds anything (ticket 0293)
            inputs=StageInputs(upstream=["sheet", "palette"], settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),
                    CheckSpec(code="wearable.body_not_exported",
                              description="The body has been exported with the same cell (checked when exporting)."),),
            output_root="out", run=run_wearable_export, needs_input=export_needs_input, check=check_wearable_export,
            available_from="M5"),
    ),
)
