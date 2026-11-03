"""The room Recipe (spec §6.1): brief, source, fit, layers, masks, palette, place, reach, export."""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from kiripix.checks import Finding, Position
from kiripix.recipes.base import (
    FIT_PARAMS,
    PALETTE_PARAMS,
    PICK,
    CheckSpec,
    DecisionSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
    point_decision,
)
from kiripix.ops import Grid, detect_grid, downscale_mode, sample_nearest

# brief


def _brief(run: StageRun) -> None:
    """Writes the brief; rendering it into a generation prompt waits for `gen` (M4)."""
    brief = {
        "width": run.params["width"],
        "height": run.params["height"],
        "view": run.asset_params["view"],
        "mood": run.params["mood"],
        "tile": run.settings["project.tile"],
    }
    (run.output_dir / "brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")


def _whole_tiles(size: int, tile: int) -> int:
    return max(tile, round(size / tile) * tile)


def _check_brief(run: StageRun) -> list[Finding]:
    brief = json.loads((run.output_dir / "brief.json").read_text(encoding="utf-8"))
    width, height, tile = int(brief["width"]), int(brief["height"]), int(brief["tile"])
    if width % tile == 0 and height % tile == 0:
        return []
    return [
        Finding(
            code="brief.size_not_tiles",
            message=f"the brief's size {width}x{height} isn't a whole number of {tile} px tiles",
            position=Position(asset=run.asset_id, stage="brief",
                              field="stages.brief.width" if width % tile else "stages.brief.height"),
            fix=f"kiripix set {run.asset_id} brief width={_whole_tiles(width, tile)} "
                f"height={_whole_tiles(height, tile)}",
        )
    ]


# source: the Variants are src/<hash>.png, imported (or, from M4, generated); the Pick chooses one.


def _variants(run: StageRun) -> dict[str, Path]:
    return {Path(name).stem: path for name, path in run.files.items()}


def _picked(run: StageRun) -> str | None:
    picks = [d for d in run.decisions if d.name == PICK.name]
    return str(picks[-1].data["variant"]) if picks else None


def _source_needs_input(run: StageRun) -> NeedsInput | None:
    variants = sorted(_variants(run))
    picked = _picked(run)
    if picked in variants:
        return None
    reason = "no Source picked" if picked is None else f"the picked Variant {picked} was deleted"
    if not variants:
        return NeedsInput(reason, command=f"kiripix import {run.asset_id} <file>")
    if len(variants) == 1:
        return NeedsInput(reason, command=f"kiripix pick {run.asset_id} {variants[0]}")
    return NeedsInput(reason, owner_action=f"Pick one of the Variants {', '.join(variants)}: "
                                           f"kiripix pick {run.asset_id} <variant>")


def _source(run: StageRun) -> None:
    picked = _picked(run)
    assert picked is not None  # `_source_needs_input` holds the Stage back until there is a Pick
    path = _variants(run)[picked]
    if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(picked):
        raise StageFailure(f"the Variant {path.name} was changed after it was imported, and Variants are immutable; "
                           "import the changed image as a new Variant and pick that")
    shutil.copyfile(path, run.output_dir / "source.png")


# fit: the Source's pixel grid (or a mode-filter downscale) down to the brief's exact size. Palette-free.


def _read_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def _write_rgba(path: Path, rgba: np.ndarray) -> None:
    Image.fromarray(rgba, "RGBA").save(path, format="PNG")


def _brief_size(run: StageRun) -> tuple[int, int]:
    brief = json.loads((run.upstream["brief"] / "brief.json").read_text(encoding="utf-8"))
    return int(brief["width"]), int(brief["height"])


def _fit(run: StageRun) -> None:
    source = _read_rgba(run.upstream["source"] / "source.png")
    height, width = source.shape[:2]
    target_width, target_height = _brief_size(run)
    mode = str(run.params["mode"])
    scale = int(run.params["scale"])
    if mode == "downscale":
        try:
            grid = Grid.to_size(width, height, target_width, target_height)
        except ValueError:
            raise StageFailure(f"can't downscale the {width}x{height} Source to the brief's "
                               f"{target_width}x{target_height}: the Source is smaller") from None
        fitted = downscale_mode(source, grid)
    else:
        try:
            grid = (Grid.uniform(scale, int(run.params["offset_x"]), int(run.params["offset_y"]), width, height)
                    if scale > 0 else detect_grid(source))
        except ValueError as error:
            raise StageFailure(str(error)) from None
        fitted = sample_nearest(source, grid)
    _write_rgba(run.output_dir / "fit.png", fitted)
    record = {"mode": mode, "source": [width, height], **grid.to_json()}
    (run.output_dir / "grid.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _check_fit(run: StageRun) -> list[Finding]:
    grid = json.loads((run.output_dir / "grid.json").read_text(encoding="utf-8"))
    width, height = int(grid["width"]), int(grid["height"])
    target_width, target_height = _brief_size(run)
    if (width, height) == (target_width, target_height):
        return []
    source_width, source_height = grid["source"]
    asset = run.asset_id
    ratio = source_width // target_width if target_width else 0
    if source_width == ratio * target_width and source_height == ratio * target_height and ratio >= 1:
        fix = f"kiripix set {asset} fit scale={ratio}"
        if int(run.params["offset_x"]) or int(run.params["offset_y"]):
            fix += " offset_x=0 offset_y=0"
        if grid["mode"] == "grid" and int(run.params["scale"]) == ratio:  # already that: the grid isn't the problem
            fix = f"kiripix set {asset} fit mode=downscale"
    else:
        fix = f"kiripix set {asset} fit mode=downscale"
    return [
        Finding(
            code="fit.size_mismatch",
            message=f"the fit image is {width}x{height}, the brief asks for {target_width}x{target_height}",
            position=Position(asset=asset, stage="fit", field="stages.fit.scale"
                              if grid["mode"] == "grid" else "stages.fit.mode"),
            fix=fix,
        )
    ]


# layers: a pass-through in M1. The Plate is the fit image, and there are no foreground Layers.


def _layers(run: StageRun) -> None:
    shutil.copyfile(run.upstream["fit"] / "fit.png", run.output_dir / "plate.png")
    (run.output_dir / "layers.json").write_text(json.dumps({"layers": []}) + "\n", encoding="utf-8")


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
            run=_brief,
            check=_check_brief,
        ),
        StageSpec(
            name="source",
            description="Generated Variants or an imported image; the Owner picks one as the Source.",
            inputs=StageInputs(files=["src/*.png"]),
            decisions=(PICK,),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."),),
            owner_input="Picks one Variant.",
            available_from="M1",
            image="source.png",
            run=_source,
            needs_input=_source_needs_input,
        ),
        StageSpec(
            name="fit",
            description="Grid detection or downscale to the target size; records the Grid transform. Palette-free.",
            inputs=StageInputs(upstream=["source", "brief"]),
            params=FIT_PARAMS,
            checks=(CheckSpec(code="fit.size_mismatch", description="The output has the brief's exact size."),),
            owner_input="Tunes the grid.",
            available_from="M1",
            image="fit.png",
            run=_fit,
            check=_check_fit,
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
            decisions=(point_decision("click", "A click on an object to lift out.", on_image=True,
                                      layer={"type": "string"}, positive={"type": "boolean"}),),
            checks=(
                CheckSpec(code="layers.recompose_mismatch", description="Plate and Layers recompose to the fit image."),
                CheckSpec(code="layers.plate_hole", description="The Plate has no holes."),
            ),
            owner_input="Clicks objects to lift out.",
            available_from="M1",  # the pass-through; the real Stage (M2) needs the GPU
            image="plate.png",
            run=_layers,
        ),
        StageSpec(
            name="masks",
            description="Paints the Masks: click-to-segment, flood, polygon, brush or an imported painted image.",
            params=(ParamSpec(name="snap_cell", type="int", description="Snap to an N px grid; 0 is off.", default=0,
                              minimum=0),),
            decisions=(
                point_decision("click", "A segmentation click.", on_image=True, mask={"type": "string"},
                               positive={"type": "boolean"}),
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
            inputs=StageInputs(upstream=["layers"], settings=["palette"]),  # ADR 0004: not `masks`
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
