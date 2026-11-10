"""The prop Recipe (spec §6.2): brief, source, cutout, fit, palette, finish, footprint, export.

Built to the footprint (tickets 0050, 0051); `export` leaves the engine-free files the Exporter reads (ticket 0052)."""

import json
import re
import shutil
from typing import Any

import numpy as np
from PIL import Image

from kiripix.checks import Finding, Position, check_alpha, check_conformance, check_chroma_cutout
from kiripix.ops import Outline, add_outline, chroma_key, collision_shapes, conformance
from kiripix.recipes.base import (
    FIT_PARAMS,
    PALETTE_PARAMS,
    PICK,
    CheckSpec,
    DecisionSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    RunnerCall,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
)
from kiripix.recipes.common import (
    palette_rgb,
    check_fit,
    check_palette,
    read_rgba,
    run_fit,
    run_palette,
    run_source,
    source_needs_input,
    write_rgba,
)
from kiripix.runners import MATTER

_RUNNER_MAX_SIZE = 1536  # px on the longer side, to fit 8 GB of VRAM (ADR 0004)
_CHROMA = re.compile("^#[0-9A-Fa-f]{6}$")
PROP_SCHEMA_VERSION = 1  # 1: `size`, `origin` and the footprint's convex `collision` shapes (ticket 0052)
_NO_TARGET = "Set project under [export.godot] in kiripix.toml to the Godot project's folder."


# brief


def _brief(run: StageRun) -> None:
    brief = {"width": run.params["width"], "height": run.params["height"], "angle": run.params["angle"]}
    (run.output_dir / "brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")


def _check_brief(run: StageRun) -> list[Finding]:
    """D8: exactly the brief's size (`fit` checks that), and no larger than the project's resolution."""
    brief = json.loads((run.output_dir / "brief.json").read_text(encoding="utf-8"))
    width, height = int(brief["width"]), int(brief["height"])
    limit_width, limit_height = (int(v) for v in run.settings["project.resolution"])
    if width <= limit_width and height <= limit_height:
        return []
    return [
        Finding(
            code="brief.larger_than_resolution",
            message=f"the brief's size {width}x{height} is larger than the project's resolution "
                    f"{limit_width}x{limit_height}",
            position=Position(asset=run.asset_id, stage="brief",
                              field="stages.brief.width" if width > limit_width else "stages.brief.height"),
            fix=f"kiripix set {run.asset_id} brief width={min(width, limit_width)} height={min(height, limit_height)}",
        )
    ]


# cutout: the background out of the full-size Source. Chroma key is an Op and calls no Runner. Matting is one pinned call
# to the MATTER Runner on the Source, capped; its matte (alpha, possibly partial) is laid over the Source's own colours
# at the Source's size, so `fit` sees what the Source holds. `fit` binarises the alpha.


def _key(run: StageRun) -> tuple[int, int, int]:
    colour = str(run.params["chroma"])
    if not _CHROMA.match(colour):
        raise StageFailure(f"the chroma colour {colour!r} isn't #RRGGBB; "
                           f"kiripix set {run.asset_id} cutout chroma=#00FF00")
    return int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)


def _cutout_calls(run: StageRun) -> list[RunnerCall]:
    source = run.upstream["source"] / "source.png"
    if run.params["method"] != "matting" or not source.is_file():
        return []
    return [RunnerCall(runner=MATTER, image=source, params={"max_size": _RUNNER_MAX_SIZE}, decisions=[])]


def _cutout(run: StageRun) -> None:
    source = read_rgba(run.upstream["source"] / "source.png")
    if run.params["method"] == "chroma":
        write_rgba(run.output_dir / "cutout.png", chroma_key(source, _key(run)))
        return
    [call] = _cutout_calls(run)
    height, width = source.shape[:2]
    with Image.open(run.pinned(call)) as opened:
        matte = opened.convert("RGBA").getchannel("A")
        if matte.size != (width, height):  # the call was capped: nearest, so the matte's own alpha values stay
            matte = matte.resize((width, height), Image.Resampling.NEAREST)
        alpha = np.asarray(matte, dtype=np.uint8)
    cut = source.copy()
    cut[..., 3] = np.minimum(source[..., 3], alpha)
    cut[cut[..., 3] == 0] = 0
    write_rgba(run.output_dir / "cutout.png", cut)


def _check_cutout(run: StageRun) -> list[Finding]:
    if run.params["method"] != "chroma":
        return []
    try:
        key = _key(run)
    except StageFailure:
        return []  # the run reports it
    findings = check_chroma_cutout(read_rgba(run.output_dir / "cutout.png"), key, "cutout.png",
                                   fix=f"kiripix set {run.asset_id} cutout method=matting")
    for finding in findings:
        assert finding.position is not None
        finding.position.asset, finding.position.stage = run.asset_id, "cutout"
    return findings


# fit: as for rooms, on the cutout; the alpha goes to the target grid by majority vote, so it is binary.


def _fit(run: StageRun) -> None:
    run_fit(run, run.upstream["cutout"] / "cutout.png", vote_alpha=True)


def _check_fit(run: StageRun) -> list[Finding]:
    report = conformance(read_rgba(run.output_dir / "fit.png"), np.zeros((0, 3), dtype=np.uint8))
    findings = check_alpha(report, "fit.png") + check_fit(run)
    for finding in findings:
        if finding.position is not None:
            finding.position.asset, finding.position.stage = run.asset_id, "fit"
    return findings


# palette: the fit image mapped to the palette once, orphans removed, transparent pixels kept.


def _palette(run: StageRun) -> None:
    run_palette(run, run.upstream["fit"] / "fit.png", "fit image")


# finish: the palette image, with an optional 1 px outline in a palette colour. Transparent pixels stay transparent.


def _finish(run: StageRun) -> None:
    rgba = read_rgba(run.upstream["palette"] / "palette.png")
    if run.params["outline"]:
        palette = palette_rgb(run)
        index = int(run.params["outline_colour"])
        if not 0 <= index < len(palette):
            raise StageFailure(f"the outline colour {index} is not in the palette, which has {len(palette)} colours "
                               f"(indexes 0 to {len(palette) - 1}); "
                               f"kiripix set {run.asset_id} finish outline_colour=0")
        r, g, b = (int(v) for v in palette[index])
        rgba = add_outline(rgba, (r, g, b))
    write_rgba(run.output_dir / "finish.png", rgba)


def _check_finish(run: StageRun) -> list[Finding]:
    try:
        palette = palette_rgb(run)
    except StageFailure:
        return []
    findings = check_conformance(conformance(read_rgba(run.output_dir / "finish.png"), palette), "finish.png",
                                 fix=f"kiripix run {run.asset_id} finish --force")
    for finding in findings:
        assert finding.position is not None
        finding.position.asset, finding.position.stage = run.asset_id, "finish"
    return findings


# footprint: the Owner's collision polygon and y-sort origin, in target pixels. The latest Decision is the one that counts.


def _footprint_decision(run: StageRun) -> dict[str, Any] | None:
    found = [d for d in run.decisions if d.name == "footprint"]
    return dict(found[-1].data) if found else None


_FOOTPRINT_EXAMPLE = json.dumps({"decision": "footprint", "data": {"polygon": [[2, 28], [29, 28], [29, 31], [2, 31]],
                                                                     "origin": [16, 31]}})


def _footprint_needs_input(run: StageRun) -> NeedsInput | None:
    if _footprint_decision(run) is not None:
        return None
    return NeedsInput(
        "no footprint or origin is set",
        owner_action=f"Draw the footprint and the origin, in target pixels (an empty polygon means no collision): "
                     f"kiripix decide {run.asset_id} footprint --decision '{_FOOTPRINT_EXAMPLE}'")


def _footprint(run: StageRun) -> None:
    decision = _footprint_decision(run)
    assert decision is not None  # `_footprint_needs_input` holds the Stage back until there is one
    shutil.copyfile(run.upstream["finish"] / "finish.png", run.output_dir / "sprite.png")
    record = {"polygon": decision["polygon"], "origin": decision["origin"]}
    (run.output_dir / "footprint.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _check_footprint(run: StageRun) -> list[Finding]:
    position = Position(asset=run.asset_id, stage="footprint")
    decision = _footprint_decision(run)
    redo = (f"Draw it again: kiripix decide {run.asset_id} footprint --decision '{_FOOTPRINT_EXAMPLE}'")
    if decision is None:
        return [Finding(code="prop.no_origin", message="the prop has no origin, so Godot can't y-sort it",
                        position=position, owner_action=redo)]
    findings: list[Finding] = []
    with Image.open(run.output_dir / "sprite.png") as sprite:
        width, height = sprite.size
    x, y = decision["origin"]
    if not (0 <= x < width and 0 <= y < height):
        findings.append(Finding(
            code="prop.origin_outside", message=f"the origin ({x}, {y}) is outside the {width}x{height} sprite",
            position=position, owner_action=redo))
    if len(decision["polygon"]) in (1, 2):
        findings.append(Finding(
            code="prop.footprint_too_small",
            message=f"the footprint has {len(decision['polygon'])} point(s); a polygon needs 3 or more, "
                    "or none for no collision",
            position=position, owner_action=redo))
    return findings


# export: what the game gets, with nothing of Godot in it: the sprite, and `prop.json` with its size, origin and the
# footprint as convex collision shapes. The Exporter (`kiripix.export`) turns those into the engine's files.


def _export_needs_input(run: StageRun) -> NeedsInput | None:
    if run.settings["export.godot"].get("project"):
        return None
    return NeedsInput("no Godot project to export into", owner_action=_NO_TARGET)


def _footprint_shapes(polygon: list[list[int]], asset: str) -> list[list[list[int]]]:
    """The footprint as convex polygons, since a collision polygon in Godot can be neither concave nor crossing itself."""
    if len(polygon) < 3:
        return []
    ring = [(int(x), int(y)) for x, y in polygon]
    area = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1]
               for i in range(len(ring)))
    if area == 0:
        raise StageFailure("the footprint has no area; draw it again: "
                           f"kiripix decide {asset} footprint --decision '{_FOOTPRINT_EXAMPLE}'")
    if area < 0:
        ring.reverse()  # an outer ring runs clockwise on screen
    try:
        shapes = collision_shapes([Outline(outer=ring, holes=[])])
    except (ValueError, IndexError, KeyError) as error:
        raise StageFailure(f"the footprint can't be made into collision shapes ({error}); it must not cross itself: "
                           f"kiripix decide {asset} footprint --decision '{_FOOTPRINT_EXAMPLE}'") from error
    return [[[x, y] for x, y in shape] for shape in shapes]


def _export(run: StageRun) -> None:
    folder = run.upstream["footprint"]
    record = json.loads((folder / "footprint.json").read_text(encoding="utf-8"))
    shutil.copyfile(folder / "sprite.png", run.output_dir / "sprite.png")
    with Image.open(folder / "sprite.png") as sprite:
        width, height = sprite.size
    prop = {
        "schema_version": PROP_SCHEMA_VERSION,
        "asset": run.asset_id,
        "size": [width, height],
        "origin": record["origin"],
        "collision": _footprint_shapes(record["polygon"], run.asset_id),
    }
    (run.output_dir / "prop.json").write_text(json.dumps(prop, indent=2) + "\n", encoding="utf-8")


def _check_export(run: StageRun) -> list[Finding]:
    if run.settings["export.godot"].get("project"):
        return []
    return [Finding(code="export.no_target", message="no Godot project to export into",
                    position=Position(asset=run.asset_id, stage="export"), owner_action=_NO_TARGET)]


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
            inputs=StageInputs(settings=["project.resolution"]),
            checks=(CheckSpec(code="brief.larger_than_resolution",
                              description="The size is no larger than the project's resolution."),),
            owner_input="Writes the brief.",
            available_from="M2",
            run=_brief,
            check=_check_brief,
        ),
        StageSpec(
            name="source",
            description="Generated on a flat chroma background, or imported.",
            inputs=StageInputs(files=["src/*.png"]),
            decisions=(PICK,),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."),),
            owner_input="Picks one Variant.",
            available_from="M2",
            image="source.png",
            run=run_source,
            needs_input=source_needs_input,
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
            checks=(
                CheckSpec(code="cutout.chroma_keyed_nothing", description="The key cleared some of the image."),
                CheckSpec(code="cutout.chroma_keyed_everything", description="The key left some of the image."),
                CheckSpec(code="cutout.chroma_fringe", description="No near-key fringe along the edge (warning)."),
            ),
            available_from="M2",
            image="cutout.png",
            run=_cutout,
            check=_check_cutout,
            runner_calls=_cutout_calls,  # `gpu` stays off: a Runner call takes the GPU lock itself (0037 D10)
        ),
        StageSpec(
            name="fit",
            description="Grid snap or downscale; alpha goes to the target grid by majority vote. A grid output smaller "
                        "than the brief is padded right and bottom with transparent pixels (`fit.padded`).",
            inputs=StageInputs(upstream=["cutout", "brief"]),
            params=FIT_PARAMS,
            checks=(
                CheckSpec(code="fit.size_mismatch", description="The output has the brief's exact size."),
                CheckSpec(code="fit.padded", description="The grid output was padded up to the brief (info)."),
                CheckSpec(code="image.partial_alpha", description="Alpha is binary."),
            ),
            available_from="M2",
            image="fit.png",
            run=_fit,
            check=_check_fit,
        ),
        StageSpec(
            name="palette",
            description="Palette mapping and orphan cleanup.",
            inputs=StageInputs(settings=["palette"]),
            params=PALETTE_PARAMS,
            checks=(
                CheckSpec(code="palette.off_palette", description="Every opaque pixel is a palette colour."),
                CheckSpec(code="palette.mapping_error", description="The palette maps the image without a high error."),
            ),
            available_from="M2",
            image="palette.png",
            run=_palette,
            check=check_palette,
        ),
        StageSpec(
            name="finish",
            description="Optional 1 px outline in a palette colour.",
            inputs=StageInputs(settings=["palette"]),
            params=(
                ParamSpec(name="outline", type="bool", description="Draw an outline.", default=False),
                ParamSpec(name="outline_colour", type="int", description="Palette index.", default=0, minimum=0),
            ),
            checks=(CheckSpec(code="palette.off_palette", description="Every opaque pixel is a palette colour."),),
            available_from="M2",
            image="finish.png",
            run=_finish,
            check=_check_finish,
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
            checks=(
                CheckSpec(code="prop.no_origin", description="An origin is set."),
                CheckSpec(code="prop.origin_outside", description="The origin is inside the image."),
                CheckSpec(code="prop.footprint_too_small", description="The polygon has 0 or 3 or more points."),
            ),
            owner_input="Draws the footprint and the origin.",
            available_from="M2",
            image="sprite.png",
            run=_footprint,
            needs_input=_footprint_needs_input,
            check=_check_footprint,
        ),
        StageSpec(
            name="export",
            description="Builds what the game gets: the sprite, its origin and collision shapes. `kiripix export` then "
                        "writes them into the Godot project as a Sprite2D scene.",
            inputs=StageInputs(upstream=["footprint"], settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),),
            output_root="out",
            available_from="M2",
            run=_export,
            needs_input=_export_needs_input,
            check=_check_export,
        ),
    ),
)
