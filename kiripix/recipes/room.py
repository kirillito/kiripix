"""The room Recipe (spec §6.1): brief, source, fit, layers, masks, palette, place, reach, export."""

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
    point_decision,
)

ROOM = KindSpec(
    name="room",
    description="A background scene with Layers, Masks and Markers, in top or side view.",
    params=(
        ParamSpec(
            name="view",
            type="choice",
            description="Top-down or side-view room.",
            required=True,
            choices=["top", "side"],
        ),
    ),
    stages=chain(
        StageSpec(
            name="brief",
            description="Size, mood, Exits and notes; renders the generation prompt.",
            inputs=StageInputs(settings=["project.tile"]),
            params=(
                ParamSpec(name="width", type="int", description="Width in px.", default=480, minimum=1),
                ParamSpec(name="height", type="int", description="Height in px.", default=270, minimum=1),
                ParamSpec(name="mood", type="str", description="Mood words for the prompt.", default=""),
            ),
            checks=(CheckSpec(code="brief.size_not_tiles", description="The size is a whole number of tiles."),),
            owner_input="Writes the brief.",
            available_from="M1",
        ),
        StageSpec(
            name="source",
            description="Generated Variants or an imported image; the Owner picks one as the Source.",
            inputs=StageInputs(files=["src/*"]),
            decisions=(PICK,),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."),),
            owner_input="Picks one Variant.",
            available_from="M1",
        ),
        StageSpec(
            name="fit",
            description="Grid detection or downscale to the target size; records the Grid transform. Palette-free.",
            params=FIT_PARAMS,
            checks=(CheckSpec(code="fit.size_mismatch", description="The output has the brief's exact size."),),
            owner_input="Tunes the grid.",
            available_from="M1",
        ),
        StageSpec(
            name="layers",
            description="Builds the Plate and the foreground Layers (segment and inpaint, or a difference).",
            params=(
                ParamSpec(
                    name="grow",
                    type="int",
                    description="Widen a Layer's alpha and its Plate hole where the Runner's alpha was partial, px.",
                    default=1,
                    minimum=0,
                    maximum=8,
                ),
            ),
            decisions=(point_decision("click", "A click on an object to lift out.", layer={"type": "string"},
                                      positive={"type": "boolean"}),),
            checks=(
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers recompose to the fit image."),
                CheckSpec(code="layers.plate_hole", description="The Plate has no holes."),
            ),
            owner_input="Clicks objects to lift out.",
            gpu=True,
            available_from="M2",
        ),
        StageSpec(
            name="masks",
            description="Paints the Masks: click-to-segment, flood, polygon, brush or an imported painted image.",
            params=(ParamSpec(name="snap_cell", type="int", description="Snap to an N px grid; 0 is off.", default=0,
                              minimum=0),),
            decisions=(
                point_decision("click", "A segmentation click.", mask={"type": "string"}, positive={"type": "boolean"}),
                DecisionSpec(
                    name="brush",
                    description="A brush stroke on one Mask, in target pixels.",
                    entry_schema={
                        "type": "object",
                        "properties": {
                            "mask": {"type": "string"},
                            "erase": {"type": "boolean"},
                            "radius": {"type": "integer", "minimum": 0},
                            "points": {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                                  "minItems": 2, "maxItems": 2}},
                        },
                        "required": ["mask", "erase", "radius", "points"],
                        "additionalProperties": False,
                    },
                ),
            ),
            checks=(CheckSpec(code="mask.not_binary", description="Every Mask is a 1-bit image."),),
            owner_input="Clicks and brushes.",
            gpu=True,
            available_from="M1",
        ),
        StageSpec(
            name="palette",
            description="Maps the composite to the palette in OKLab and removes orphan pixels.",
            inputs=StageInputs(settings=["palette"]),
            params=PALETTE_PARAMS,
            checks=(
                CheckSpec(code="palette.off_palette", description="Every pixel is a palette colour."),
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers still recompose exactly."),
            ),
            owner_input="Tunes the sliders.",
            available_from="M1",
        ),
        StageSpec(
            name="place",
            description="Places Markers: Exits, Spawns, lights, emitters and y-sort lines.",
            inputs=StageInputs(settings=["body"]),
            decisions=(
                point_decision(
                    "marker",
                    "A Marker with a stable ID.",
                    id={"type": "string"},
                    type={"enum": ["exit", "spawn", "interactable", "light", "emitter", "ysort"]},
                ),
            ),
            checks=(
                CheckSpec(code="marker.duplicate_id", description="Marker IDs are unique."),
                CheckSpec(code="marker.not_walkable", description="Exits and Spawns stand on walkable ground."),
                CheckSpec(code="layer.no_ysort", description="Every foreground Layer has a y-sort line or is above."),
            ),
            owner_input="Places Markers.",
            available_from="M1",
        ),
        StageSpec(
            name="reach",
            description="Reachability of every Marker for the Body's footprint.",
            inputs=StageInputs(settings=["body"]),
            params=(ParamSpec(name="step", type="int", description="Flood step in px.", default=4, minimum=1),),
            checks=(CheckSpec(code="reach.unreachable_marker", description="Every Marker is reachable."),),
            available_from="M1",
        ),
        StageSpec(
            name="export",
            description="Writes the Godot scene.",
            inputs=StageInputs(settings=["export.godot"]),
            checks=(
                CheckSpec(code="export.no_target", description="The export target is set."),
                CheckSpec(code="exit.unpaired", description="Every Exit points to an Exit that points back."),
            ),
            output_root="out",
            available_from="M1",
        ),
    ),
)
