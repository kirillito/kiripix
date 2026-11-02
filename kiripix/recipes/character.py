"""The character Recipe (spec §6.3): model, rig, clips, render, palette, finish, sheet, export."""

from kiripix.recipes.base import (
    PALETTE_PARAMS,
    PICK,
    CheckSpec,
    DecisionSpec,
    KindSpec,
    ParamSpec,
    StageInputs,
    StageSpec,
    chain,
)

CHARACTER = KindSpec(
    name="character",
    description="A character, NPC or enemy rendered from a 3D Model, so every animation stays on-model.",
    stages=chain(
        StageSpec(
            name="model",
            description="Imports .glb, .fbx or .blend; normalises scale and the up axis.",
            inputs=StageInputs(files=["src/*"]),
            decisions=(PICK,),
            owner_input="Picks or imports a Model.",
            available_from="M3",
        ),
        StageSpec(
            name="rig",
            description="Validates a humanoid rig, or guides the Mixamo round trip.",
            owner_input="The Mixamo step, when used.",
            available_from="M3",
        ),
        StageSpec(
            name="clips",
            description="Maps named clips to animation sources, with frame range, frame rate and loop flag.",
            decisions=(
                DecisionSpec(
                    name="clip",
                    description="One named clip.",
                    entry_schema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "source": {"type": "string"},
                            "start": {"type": "integer", "minimum": 0},
                            "end": {"type": "integer", "minimum": 0},
                            "fps": {"type": "integer", "minimum": 1},
                            "loop": {"type": "boolean"},
                        },
                        "required": ["name", "source", "start", "end", "fps", "loop"],
                        "additionalProperties": False,
                    },
                ),
            ),
            owner_input="Chooses clips.",
            available_from="M3",
        ),
        StageSpec(
            name="render",
            description="Headless Blender render at the target pixel size: colour, normal, depth and mask passes.",
            params=(
                ParamSpec(
                    name="camera",
                    type="choice",
                    description="Camera preset.",
                    default="top34_8",
                    choices=["top34_4", "top34_8", "side", "battle"],
                ),
            ),
            gpu=True,
            owner_input="Tunes the camera preset once per project.",
            available_from="M3",
        ),
        StageSpec(
            name="palette",
            description="One palette per character across all frames, and orphan cleanup.",
            inputs=StageInputs(settings=["palette"]),
            params=PALETTE_PARAMS,
            checks=(CheckSpec(code="palette.off_palette", description="Every pixel is a palette colour."),),
            available_from="M3",
        ),
        StageSpec(
            name="finish",
            description="Outline after mapping; the normal pass quantised and aligned to the colour frames.",
            params=(ParamSpec(name="outline_colour", type="int", description="Palette index.", default=0, minimum=0),),
            checks=(CheckSpec(code="normal.size_mismatch", description="Normal map size equals the colour frame's."),),
            available_from="M3",
        ),
        StageSpec(
            name="sheet",
            description="Packs frames into an atlas with a fixed pivot per frame.",
            checks=(
                CheckSpec(code="sheet.pivot_drift", description="The feet don't move in a stationary clip."),
                CheckSpec(code="sheet.frame_overflow", description="Every frame fits its cell."),
                CheckSpec(code="sheet.frame_count", description="Frame counts match the clip."),
                CheckSpec(code="sheet.empty_frame", description="No frame is empty."),
            ),
            available_from="M3",
        ),
        StageSpec(
            name="export",
            description="SpriteFrames, a CanvasTexture with the normal map, and an AnimatedSprite2D scene.",
            inputs=StageInputs(settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),),
            output_root="out",
            available_from="M3",
        ),
    ),
)
