"""The prop Recipe (spec §6.2): brief, source, cutout, fit, palette, finish, footprint, export.

Built to the footprint (tickets 0050, 0051); `export` leaves the engine-free files the Exporter reads (ticket 0052)."""

from __future__ import annotations

import json
import re
import shutil
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    from PIL import Image
else:
    Image = lazy_module("PIL.Image")

from kiripix.checks import Finding, Position, check_alpha, check_conformance, check_chroma_cutout
from kiripix.ops import Grid, Outline, add_outline, chroma_key, collision_shapes, conformance
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
from kiripix.recipes.prop_states import (
    CHECKS as STATE_CHECKS,
    DECISIONS as STATE_DECISIONS,
    DEFAULT_STATE,
    STATE_ID,
    STATE_OFFSET,
    STATE_RECORD,
    STATES_DIR,
    STATES_OUT,
    about_state,
    apply_edits as apply_state_edits,
    check_each_state,
    each_state,
    state_ids,
    state_needs_input,
    state_offsets,
    state_size,
    state_view,
    top_files,
    write_state_sources,
)
from kiripix.runners import MATTER

_RUNNER_MAX_SIZE = 1536  # px on the longer side, to fit 8 GB of VRAM (ADR 0004)
_CHROMA = re.compile("^#[0-9A-Fa-f]{6}$")
PROP_SCHEMA_VERSION = 1  # 1: `size`, `origin` and the footprint's convex `collision` shapes (ticket 0052)
_NO_TARGET = "Set project under [export.godot] in kiripix.toml to the Godot project's folder."


# brief


def _brief(run: StageRun) -> None:
    brief = {"width": run.params["width"], "height": run.params["height"], "angle": run.params["angle"]}
    if run.params["state"] != DEFAULT_STATE:  # a Prop that names no state has the brief it always had
        brief["state"] = run.params["state"]
    (run.output_dir / "brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")


def _check_brief(run: StageRun) -> list[Finding]:
    """D8: exactly the brief's size (`fit` checks that), and no larger than the project's resolution."""
    brief = json.loads((run.output_dir / "brief.json").read_text(encoding="utf-8"))
    width, height = int(brief["width"]), int(brief["height"])
    limit_width, limit_height = (int(v) for v in run.settings["project.resolution"])
    findings: list[Finding] = []
    state = str(run.params["state"])
    if not re.fullmatch(STATE_ID, state):  # the default state's ID is a name in the game, as every other state's
        snake = re.sub(r"[^a-z0-9]+", "_", state.lower()).strip("_")
        snake = snake if re.fullmatch(STATE_ID, snake) else DEFAULT_STATE
        findings.append(Finding(
            code="brief.state_invalid",
            message=f"the default state's ID {state!r} isn't lower-case snake_case",
            position=Position(asset=run.asset_id, stage="brief", field="stages.brief.state"),
            fix=f"kiripix set {run.asset_id} brief state={snake}",
        ))
    if width <= limit_width and height <= limit_height:
        return findings
    return findings + [
        Finding(
            code="brief.larger_than_resolution",
            message=f"the brief's size {width}x{height} is larger than the project's resolution "
                    f"{limit_width}x{limit_height}",
            position=Position(asset=run.asset_id, stage="brief",
                              field="stages.brief.width" if width > limit_width else "stages.brief.height"),
            fix=f"kiripix set {run.asset_id} brief width={min(width, limit_width)} height={min(height, limit_height)}",
        )
    ]


# source: the default state's Source, from `src/<hash>.png`; a state's Variants (`src/states/`) are read by `state_needs_input`.
# From here every Stage runs for the default state, and then for each other state under `states/<id>/` of its output (0259).


def _source(run: StageRun) -> None:
    run_source(top_files(run))
    write_state_sources(run)  # each declared state's Source, under `states/<id>/`


def _source_needs_input(run: StageRun) -> NeedsInput | None:
    return source_needs_input(top_files(run)) or state_needs_input(run)


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
    """One call for the default state's Source and one for each other state's, with matting."""
    if run.params["method"] != "matting":
        return []
    folder = run.upstream["source"]
    images = [folder / "source.png", *(folder / STATES_OUT / s / "source.png" for s in state_ids(folder))]
    return [RunnerCall(runner=MATTER, image=image, params={"max_size": _RUNNER_MAX_SIZE}, decisions=[])
            for image in images if image.is_file()]


def _cutout(run: StageRun) -> None:
    each_state(run, "source", _cutout_one)


def _cutout_one(run: StageRun) -> None:
    record = run.upstream["source"] / STATE_RECORD  # a state's size goes on to `fit`
    if record.is_file():
        shutil.copyfile(record, run.output_dir / STATE_RECORD)
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
    return check_each_state(run, _check_cutout_one)


def _check_cutout_one(run: StageRun) -> list[Finding]:
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
    """The default state first; every other state is fitted at the default's scale, into its own size."""
    run_fit(run, run.upstream["cutout"] / "cutout.png", vote_alpha=True)
    grid = Grid.from_json(json.loads((run.output_dir / "grid.json").read_text(encoding="utf-8")))
    for state in state_ids(run.upstream["cutout"]):
        run.check_cancel()
        view = state_view(run, state)
        run_fit(view, view.upstream["cutout"] / "cutout.png", vote_alpha=True,
                size=state_size(run.upstream["cutout"], state), scale=(grid.scale_x, grid.scale_y), state=state, offsets=state_offsets(run, state))


def _check_fit_of(run: StageRun, state: str | None = None, size: tuple[int, int] | None = None) -> list[Finding]:
    report = conformance(read_rgba(run.output_dir / "fit.png"), np.zeros((0, 3), dtype=np.uint8))
    findings = check_alpha(report, "fit.png") + check_fit(run, state, size)
    for finding in findings:
        if finding.position is not None:
            finding.position.asset, finding.position.stage = run.asset_id, "fit"
    return findings


def _check_fit(run: StageRun) -> list[Finding]:
    findings = _check_fit_of(run)
    for state in state_ids(run.output_dir):
        view = state_view(run, state)
        try:
            size = state_size(run.upstream["cutout"], state)
        except FileNotFoundError:
            continue  # `cutout` was built again without the state: `fit` is stale, and says so
        found = _check_fit_of(view, state, size)
        findings += about_state(found, state)
    return findings


# palette: the fit image mapped to the palette once, orphans removed, transparent pixels kept.


def _palette(run: StageRun) -> None:
    each_state(run, "fit", lambda one: run_palette(one, one.upstream["fit"] / "fit.png", "fit image"))


def _check_palette(run: StageRun) -> list[Finding]:
    return check_each_state(run, check_palette)


# finish: the palette image, with an optional 1 px outline in a palette colour. Transparent pixels stay transparent.


def _finish(run: StageRun) -> None:
    each_state(run, "palette", _finish_one)


def _finish_one(run: StageRun) -> None:
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
    return check_each_state(run, _check_finish_one)


def _check_finish_one(run: StageRun) -> list[Finding]:
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


# footprint: the Owner's collision polygon and y-sort origin, in target pixels, for each state (a `state` field on the
# Decision; absent means the default state). The latest Decision of a state is the one that counts.


def _footprint_decision(run: StageRun, state: str | None = None) -> dict[str, Any] | None:
    found = [d for d in run.decisions if d.name == "footprint" and d.data.get("state") == state]
    return {k: v for k, v in found[-1].data.items() if k != "state"} if found else None


def _footprint_example(state: str | None = None) -> str:
    data: dict[str, Any] = {"polygon": [[2, 28], [29, 28], [29, 31], [2, 31]], "origin": [16, 31]}
    if state is not None:
        data["state"] = state
    return json.dumps({"decision": "footprint", "data": data})


_FOOTPRINT_EXAMPLE = _footprint_example()


def _footprint_needs_input(run: StageRun) -> NeedsInput | None:
    if _footprint_decision(run) is None:
        return NeedsInput(
            "no footprint or origin is set",
            owner_action=f"Draw the footprint and the origin, in target pixels (an empty polygon means no collision): "
                         f"kiripix decide {run.asset_id} footprint --decision '{_FOOTPRINT_EXAMPLE}'")
    for state in state_ids(run.upstream["finish"]):
        if _footprint_decision(run, state) is None:
            return NeedsInput(
                f"no footprint or origin is set for the state {state}", code="footprint.no_origin",
                owner_action=f"Draw the state's footprint and origin, in target pixels (an empty polygon means no "
                             f"collision): kiripix decide {run.asset_id} footprint --decision "
                             f"'{_footprint_example(state)}'")
    return None


def _footprint(run: StageRun) -> None:
    _footprint_of(run, None)
    for state in state_ids(run.upstream["finish"]):
        run.check_cancel()
        _footprint_of(state_view(run, state), state)


def _footprint_of(run: StageRun, state: str | None) -> None:
    decision = _footprint_decision(run, state)
    assert decision is not None  # `_footprint_needs_input` holds the Stage back until there is one
    shutil.copyfile(run.upstream["finish"] / "finish.png", run.output_dir / "sprite.png")
    record = {"polygon": decision["polygon"], "origin": decision["origin"]}
    (run.output_dir / "footprint.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _check_footprint(run: StageRun) -> list[Finding]:
    findings = _check_footprint_of(run, None)
    states = state_ids(run.output_dir)
    for state in states:
        findings += about_state(_check_footprint_of(state_view(run, state), state), state)
    for named in sorted({str(d.data["state"]) for d in run.decisions if d.name == "footprint" and "state" in d.data}
                        - set(states)):
        findings.append(Finding(
            code="prop.state_unknown", message=f"a footprint is drawn for the state {named}, which the Prop doesn't have",
            position=Position(asset=run.asset_id, stage="footprint"),
            owner_action=f"Declare the state first, or draw the footprint again without it: "
                         f"kiripix decide {run.asset_id} footprint --decision '{_FOOTPRINT_EXAMPLE}'"))
    return findings


def _check_footprint_of(run: StageRun, state: str | None) -> list[Finding]:
    position = Position(asset=run.asset_id, stage="footprint")
    decision = _footprint_decision(run, state)
    redo = f"Draw it again: kiripix decide {run.asset_id} footprint --decision '{_footprint_example(state)}'"
    if decision is None:
        if state is not None:
            return [Finding(code="footprint.no_origin", message="it has no origin, so Godot can't y-sort it",
                            position=position, owner_action=redo)]
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
                ParamSpec(
                    name="state",
                    type="str",
                    description="The default state's ID (the picked Source): lower-case snake_case. Another state of "
                                "the Prop (`state` Decision on `source`) can't have it.",
                    default=DEFAULT_STATE,
                ),
            ),
            inputs=StageInputs(settings=["project.resolution"]),
            checks=(CheckSpec(code="brief.larger_than_resolution",
                              description="The size is no larger than the project's resolution."),
                    CheckSpec(code="brief.state_invalid",
                              description="The default state's ID is lower-case snake_case.")),
            owner_input="Writes the brief.",
            available_from="M2",
            run=_brief,
            check=_check_brief,
        ),
        StageSpec(
            name="source",
            description="Generated on a flat chroma background, or imported.",
            inputs=StageInputs(files=["src/*.png", f"{STATES_DIR}/**/*.png"]),
            decisions=(PICK, *STATE_DECISIONS),
            checks=(CheckSpec(code="source.not_picked", description="A Source has been picked."), *STATE_CHECKS),
            owner_input="Picks one Variant, and one for each state it declares.",
            available_from="M2",
            image="source.png",
            run=_source,
            needs_input=_source_needs_input,
            decisions_view=apply_state_edits,
        ),
        StageSpec(
            name="cutout",
            description="Chroma key or matting on the full-size Source, for each state.",
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
            decisions=(STATE_OFFSET,),
            checks=(
                CheckSpec(code="fit.size_mismatch", description="The output has the brief's exact size."),
                CheckSpec(code="fit.padded", description="The grid output was padded up to the brief (info)."),
                CheckSpec(code="fit.scale_differs", description="Every state's grid has the default state's scale."),
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
            check=_check_palette,
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
                    description="The collision polygon and the origin, in target pixels. `state` names the Prop's other state it "
                                "is for; without it, it is the default state's.",
                    entry_schema={
                        "type": "object",
                        "properties": {
                            "polygon": {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                                   "minItems": 2, "maxItems": 2}},
                            "origin": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                            "state": {"type": "string", "pattern": STATE_ID},
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
                CheckSpec(code="footprint.no_origin", description="Every other state has an origin (needs-input)."),
                CheckSpec(code="prop.state_unknown", description="A footprint names only a state the Prop has."),
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
