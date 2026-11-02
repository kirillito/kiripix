"""The prop Recipe (spec §6.2): brief, source, cutout, fit, palette, finish, footprint, export."""

from kiripix.recipes.base import (
    FIT_PARAMS,
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

PROP = KindSpec(
    name="prop",
    description="A standalone, reusable object for scenes: a bench, a sign, a lamp.",
    stages=chain(
        StageSpec(
            name="brief",
            description="Size, viewing angle and notes.",
            params=(
                ParamSpec(name="width", type="int", description="Width in px.", default=32, minimum=1),
                ParamSpec(name="height", type="int", description="Height in px.", default=32, minimum=1),
                ParamSpec(
                    name="angle",
                    type="choice",
                    description="Viewing angle.",
                    default="top34",
                    choices=["top34", "side"],
                ),
            ),
            owner_input="Writes the brief.",
            available_from="M2",
        ),
        StageSpec(
            name="source",
            description="Generated on a flat chroma background, or imported.",
            inputs=StageInputs(files=["src/*"]),
            decisions=(PICK,),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."),),
            owner_input="Picks one Variant.",
            available_from="M2",
        ),
        StageSpec(
            name="cutout",
            description="Chroma key or matting on the full-size Source.",
            params=(
                ParamSpec(
                    name="method",
                    type="choice",
                    description="Exact chroma key, or matting.",
                    default="chroma",
                    choices=["chroma", "matting"],
                ),
                ParamSpec(name="chroma", type="str", description="Background colour, #RRGGBB.", default="#00FF00"),
            ),
            gpu=True,
            available_from="M2",
        ),
        StageSpec(
            name="fit",
            description="Grid snap or downscale; alpha goes to the target grid by majority vote.",
            params=FIT_PARAMS,
            checks=(CheckSpec(code="image.partial_alpha", description="Alpha is binary."),),
            available_from="M2",
        ),
        StageSpec(
            name="palette",
            description="Palette mapping and orphan cleanup.",
            inputs=StageInputs(settings=["palette"]),
            params=PALETTE_PARAMS,
            checks=(CheckSpec(code="palette.off_palette", description="Every pixel is a palette colour."),),
            available_from="M2",
        ),
        StageSpec(
            name="finish",
            description="Optional 1 px outline in a palette colour.",
            inputs=StageInputs(settings=["palette"]),
            params=(
                ParamSpec(name="outline", type="bool", description="Draw an outline.", default=False),
                ParamSpec(name="outline_colour", type="int", description="Palette index.", default=0, minimum=0),
            ),
            available_from="M2",
        ),
        StageSpec(
            name="footprint",
            description="The base's collision shape and the y-sort origin; optional foreground split.",
            decisions=(
                DecisionSpec(
                    name="footprint",
                    description="The collision polygon and the origin, in target pixels.",
                    entry_schema={
                        "type": "object",
                        "properties": {
                            "polygon": {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                                   "minItems": 2, "maxItems": 2}},
                            "origin": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                        },
                        "required": ["polygon", "origin"],
                        "additionalProperties": False,
                    },
                ),
            ),
            checks=(CheckSpec(code="prop.no_origin", description="An origin is set."),),
            owner_input="Draws the footprint and the origin.",
            available_from="M2",
        ),
        StageSpec(
            name="export",
            description="A Sprite2D scene with collision and origin.",
            inputs=StageInputs(settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),),
            output_root="out",
            available_from="M2",
        ),
    ),
)
