"""The room's `looks` Stage (ADR 0009, tickets 0129 and 0130): a room's other appearances, each cut from an edit.

A Look is an edit of the room's Source (an image model's, or painted by hand), picked with `pick --look` (0129). The
build treats each picked edit like the room itself, then keeps only what the Look changes:

1. resize it to the Source, and `register` it (scale and shift, estimated outside the Look's own region) and lay it on
   the Source;
2. `fit` it through the room's Grid transform, and `regrade` its light when asked;
3. work out the region: `polygon`, `brush` and `difference` Decisions replayed in order on the Look's Mask. A
   `difference` picks out what the edit really redrew, on the fitted images *before the palette* (trial 0128: the
   palette's steps are as big as the model's noise, so a difference of mapped pixels would find noise everywhere);
4. map the whole fitted edit once with the `palette` Stage's parameters, and cut the region from it: the Look's image,
   cropped to the region's box, in one piece for the Plate and one per foreground Layer the region meets (the pixels in
   that Layer's alpha), so the pieces together are the mapped edit inside the region. A Look may also have its own
   `solid` Mask.

A Look exists once it has a Pick. The `look` Decision is optional: it gives the Look a Condition, a label the game
reads and Kiripix doesn't (`circuit.hall:off`). A Look with a Pick and no region builds nothing and is warned about
(`look.no_region`). A Decision that names a Look with no Pick holds the Stage back (needs-input). The Stage calls no
Runner and never reads a Decision of the room's: `export` doesn't read it yet (ticket 0131).

Output, in the Stage's folder: `looks.json` (what was built, per Look, with the registration and the drift), and per
Look a folder `<look>/` holding `plate.png`, `layer.<id>.png` and `solid.png` as there are.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
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

from kiripix.checks import Finding, Position, check_alpha
from kiripix.ops import conformance, cut_by_alpha, drift_boxes, mask_box, regrade, resize_nearest
from kiripix.recipes.base import (
    BoxCorners,
    CheckSpec,
    CurrentDecision,
    DecisionSpec,
    NeedsInput,
    ParamSpec,
    StageFailure,
    StageRun,
)
from kiripix.recipes.common import box_problem, map_to_palette, palette_rgb, read_grid, read_rgba, write_rgba
from kiripix.recipes.layers import layer_file
from kiripix.recipes.regions import (
    DIFFERENCE_SPECKS,
    DIFFERENCE_TOLERANCE,
    MASKS_STAGE,
    PALETTE_STAGE,
    EditRoom,
    brush_decision,
    decision_box,
    difference_decision,
    paint_region,
    polygon_decision,
    read_mask,  # noqa: F401
    registered,
    write_mask,
)
from kiripix.recipes.regions import decisions_of as _decisions_of
from kiripix.recipes.regions import fitted as fitted_edit

LOOKS_STAGE = "looks"
LOOKS_DIR = "src/looks"  # an Asset's Looks: `src/looks/<look>/<hash>.png`
LOOK_ID = "^[a-z0-9_]+(\\.[a-z0-9_]+)*$"
SOURCE_STAGE = "source"
LOOKS_FILE = "looks.json"
LOOKS_SCHEMA_VERSION = 1

# From trial 0128 (ΔE is the OKLab distance times 100, on the 3x3 mean of the fitted difference). The tolerances of a
# `difference` and the registration's limits are in `regions`.
DRIFT_TOLERANCE = 8.0  # redraw outside the region that `look.drift` reports
DRIFT_MIN_PIECE = 16  # pixels
DRIFT_LISTED = 5  # boxes a `look.drift` message names, the largest first

LOOK_PROPERTY: dict[str, Any] = {"type": "string", "pattern": LOOK_ID}
_POINTS: dict[str, Any] = {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                       "minItems": 2, "maxItems": 2}}

LOOK_PICK = DecisionSpec(
    name="pick",
    description="Choose one edit Variant of a Look (`src/looks/<look>/<variant>.png`). `source` is the room's Source "
                "(its Variant name) the edit was made on: a pick whose `source` isn't the room's current Source "
                "doesn't apply (needs-input), because an edit of the old picture must never be cut into the new one. "
                "`kiripix pick <asset> <variant> --look <look>` records it with the right `source`.",
    entry_schema={
        "type": "object",
        "properties": {
            "look": {"type": "string", "pattern": LOOK_ID},
            "variant": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["look", "variant", "source"],
        "additionalProperties": False,
    },
)

PARAMS = (
    ParamSpec(
        name="register",
        type="bool",
        description="Lay each edit on the Source before fitting it: estimate its scale (0.985 to 1.015 on each axis) and "
                    "shift (4 target px at most) from textured tiles outside the Look's region, which an image model "
                    "sometimes gets wrong by a percent. An edit beyond the limits isn't moved and is reported "
                    "(`look.misaligned`).",
        default=True,
    ),
    ParamSpec(
        name="regrade",
        type="choice",
        description="Match each edit's light to the room's before the palette: `none`, or `outside`, a gain and offset "
                    "per OKLab channel fitted outside the Look's polygon and brush regions. `none` is right unless the "
                    "model shifted the whole room's light (trial 0128: it didn't).",
        default="none",
        choices=["none", "outside"],
    ),
    ParamSpec(
        name="drift_tolerance",
        type="float",
        description="How much redraw outside a Look's region `look.drift` allows: the OKLab distance times 100, on the "
                    "3x3 mean of the fitted difference, in pieces of 16 target px or more.",
        default=DRIFT_TOLERANCE,
        minimum=0,
    ),
)

LOOK_DECISION = DecisionSpec(
    name="look",
    description="Name a Look's Condition, the label the game shows it under (`circuit.hall:off`): Kiripix doesn't "
                "read it. Optional: a Look exists once an edit is picked for it. The latest Decision of a Look counts.",
    entry_schema={
        "type": "object",
        "properties": {"look": LOOK_PROPERTY, "condition": {"type": "string", "minLength": 1}},
        "required": ["look"],
        "additionalProperties": False,
    },
)

POLYGON_DECISION = polygon_decision("look", "Look", "A Look shows the edit only inside its region.")
BRUSH_DECISION = brush_decision("look", "Look")

SOLID_DECISION = DecisionSpec(
    name="solid",
    description="Edit the Look's own `solid` Mask, which starts as the room's and is what the game uses while the Look "
                "shows: a polygon (`points`, at least three) or, with a `radius`, a brush stroke along `points`; `erase` "
                "clears. A Look with no `solid` Decision has no `solid.png` and uses the room's. The `masks` Stage's "
                "`snap_cell` applies.",
    entry_schema={
        "type": "object",
        "properties": {"look": LOOK_PROPERTY, "erase": {"type": "boolean"}, "radius": {"type": "integer", "minimum": 0},
                       "points": _POINTS},
        "required": ["look", "points"],
        "additionalProperties": False,
    },
    problem=lambda data: (f"a polygon needs at least three points, got {len(data['points'])}; give a `radius` for a "
                          "brush stroke" if "radius" not in data and len(data["points"]) < 3 else None),
)


DIFFERENCE_DECISION = difference_decision(
    "look",
    "Add to a Look's region what the edit redrew inside a box, from (x0, y0) to (x1, y1) in target "
    "pixels, both included: the pixels where the fitted edit differs from the fitted room by at least "
    f"`tolerance` ΔE (OKLab distance times 100, on the 3x3 mean; default {DIFFERENCE_TOLERANCE:g}, which "
    "picks out a shut gate or a broken turnstile whole), with pieces under `specks` pixels (default "
    f"{DIFFERENCE_SPECKS}) dropped. Measured before the palette. A lamp's glass comes with its light "
    "pool; the box limits it. Made on the room's Plate: a refit or a Layer change puts it in "
    "needs-review.")


DECISIONS = (LOOK_PICK, LOOK_DECISION, POLYGON_DECISION, BRUSH_DECISION, DIFFERENCE_DECISION, SOLID_DECISION)

CHECKS = (
    CheckSpec(code="look.off_palette", description="Every pixel of a Look's pieces is a palette colour."),
    CheckSpec(code="look.misaligned", description="The edit lies on the Source within the registration's limits."),
    CheckSpec(code="look.drift", description="The edit redrew nothing outside the Look's region (warning)."),
    CheckSpec(code="look.unchanged", description="The Look's region holds a pixel that differs from the room (warning)."),
    CheckSpec(code="look.no_region", description="The Look has a region (warning)."),
)


# the edits

def edit_path(look: str, variant: str) -> str:
    """Where an edit Variant is, relative to the Asset folder (the key of `StageRun.files`)."""
    return f"{LOOKS_DIR}/{look}/{variant}.png"


def current_source(run: StageRun) -> str | None:
    """The Variant the room's Source Stage has picked now, from its journal; None without a Pick."""
    picks = [d for d in run.upstream_decisions.get(SOURCE_STAGE, ()) if d.name == "pick"]
    return str(picks[-1].data["variant"]) if picks else None


def picked_edits(run: StageRun) -> dict[str, tuple[str, str]]:
    """Each Look's current Pick, as (edit Variant, the Source it was made on); the latest Pick of a Look counts."""
    found: dict[str, tuple[str, str]] = {}
    for decision in run.decisions:
        if decision.name == "pick":
            found[str(decision.data["look"])] = (str(decision.data["variant"]), str(decision.data["source"]))
    return found


def decisions_of(run: StageRun, look: str, *names: str) -> list[CurrentDecision]:
    """The Look's current Decisions of these kinds, in order."""
    return _decisions_of(run, "look", look, *names)


def named_looks(run: StageRun) -> set[str]:
    """Every Look any current Decision names."""
    return {str(d.data["look"]) for d in run.decisions}


def conditions(run: StageRun) -> dict[str, str | None]:
    """Each Look's Condition: the latest `look` Decision that gives one; None for a Look with none."""
    found: dict[str, str | None] = {}
    for decision in run.decisions:
        if decision.name == "look":
            found[str(decision.data["look"])] = decision.data.get("condition")
    return found


def looks_needs_input(run: StageRun) -> NeedsInput | None:
    source = current_source(run)
    if source is None:
        return None  # `source` says that itself
    edits = picked_edits(run)
    other = [look for look, (_, made_on) in edits.items() if made_on != source]
    if other:
        remake = "; ".join(f"kiripix import {run.asset_id} <png> --look {look}, then kiripix pick {run.asset_id} "
                           f"<variant> --look {look}" for look in other)
        return NeedsInput("the edit was made on another Source",
                          owner_action=f"Re-make the edit of {', '.join(other)} from the new Source ({remake}).")
    for look, (variant, _) in edits.items():
        if edit_path(look, variant) not in run.files:
            return NeedsInput(f"the picked edit {variant} of Look {look} was deleted",
                              owner_action=f"Import an edit again (kiripix import {run.asset_id} <png> --look {look}) "
                                           f"and pick it (kiripix pick {run.asset_id} <variant> --look {look}).")
    for look in sorted(named_looks(run) - set(edits)):
        found = sorted(Path(name).stem for name in run.files if name.startswith(f"{LOOKS_DIR}/{look}/"))
        reason = f"no edit is picked for the Look {look}"
        if len(found) == 1:
            return NeedsInput(reason, command=f"kiripix pick {run.asset_id} {found[0]} --look {look}")
        return NeedsInput(reason, owner_action=(f"Pick one of the edits {', '.join(found)} (kiripix pick {run.asset_id} "
                                                f"<variant> --look {look})" if found else f"Import an edit of {look} "
                                                f"(kiripix import {run.asset_id} <png> --look {look}) and pick it")
                          + f", or undo the Decisions that name {look} (kiripix undo {run.asset_id} {LOOKS_STAGE}).")
    read = read_grid(run)
    if read is not None:
        for decision in run.decisions:
            if decision.name != "difference":
                continue
            box = decision_box(decision)
            problem = box_problem(box, read[0].width, read[0].height, read[0].pad_right, read[0].pad_bottom)
            if problem is not None:
                return NeedsInput(f"the difference box ({box[0]}, {box[1]}) to ({box[2]}, {box[3]}) of "
                                  f"{decision.data['look']} {problem}",
                                  owner_action=f"Undo it: kiripix undo {run.asset_id} {LOOKS_STAGE}.")
    return None


# the build


def _build_look(run: StageRun, room: EditRoom, look: str, variant: str, condition: str | None) -> dict[str, Any]:
    path = run.files[edit_path(look, variant)]
    if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(variant):
        raise StageFailure(f"the edit {path.name} of {look} was changed after it was imported, and edits are "
                           "immutable; import the changed image as a new Variant and pick that")
    source_height, source_width = room.source.shape[:2]
    edit = resize_nearest(read_rgba(path), source_width, source_height)
    shape = room.fit.shape[:2]
    static = paint_region(run, "look", look, shape, room.fit, None)
    edit, registration = registered(run, room.source, edit, static, room.grid)
    run.check_cancel()
    fitted = fitted_edit(room.record, room.grid, edit)
    if str(run.params["regrade"]) == "outside":
        fitted = regrade(room.fit, fitted, static if static.any() else None)
    region = paint_region(run, "look", look, shape, room.fit, fitted)
    drift = drift_boxes(room.fit, fitted, region, float(run.params["drift_tolerance"]), DRIFT_MIN_PIECE)
    run.check_cancel()
    mapped = map_to_palette(room.mapping, fitted, f"edit of {look}")
    folder = run.output_dir / look
    record: dict[str, Any] = {
        "id": look, "condition": condition, "edit": variant, "box": None, "plate": None, "layers": [], "solid": None,
        "changed": 0, "registration": registration,
        "drift": [{"x": d.x, "y": d.y, "width": d.width, "height": d.height, "pixels": d.pixels} for d in drift],
    }
    solid = room.own_solid(decisions_of(run, look, "solid"))
    if solid is not None:
        folder.mkdir(parents=True, exist_ok=True)
        write_mask(folder / "solid.png", solid)
        record["solid"] = f"{look}/solid.png"
    box = mask_box(region)
    if box is None:
        return record
    x, y, width, height = box
    crop = (slice(y, y + height), slice(x, x + width))
    folder.mkdir(parents=True, exist_ok=True)
    covered = np.zeros(shape, dtype=np.bool_)
    for layer, alpha in room.layers:
        covered |= alpha
        part = region & alpha
        if part.any():
            file = layer_file(layer)
            write_rgba(folder / file, cut_by_alpha(mapped, part)[crop])
            record["layers"].append({"id": layer, "file": f"{look}/{file}"})
    plate = region & ~covered
    if plate.any():
        write_rgba(folder / "plate.png", cut_by_alpha(mapped, plate)[crop])
        record["plate"] = f"{look}/plate.png"
    record["box"] = [x, y, width, height]
    record["changed"] = int((region & (mapped != room.composite).any(axis=2)).sum())
    return record


def run_looks(run: StageRun) -> None:
    edits = picked_edits(run)
    built: list[dict[str, Any]] = []
    if edits:
        room = EditRoom(run)
        names = conditions(run)
        for index, look in enumerate(sorted(edits)):
            run.check_cancel()
            run.progress(index, len(edits), f"Look {look}")
            built.append(_build_look(run, room, look, edits[look][0], names.get(look)))
        run.progress(len(edits), len(edits), "Looks")
    document = {"schema_version": LOOKS_SCHEMA_VERSION, "looks": built}
    (run.output_dir / LOOKS_FILE).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


# the Checks


def read_looks(folder: Path, asset: str) -> list[dict[str, Any]]:
    """The Looks a built `looks.json` in `folder` lists, in order. An older file is refused, naming the rebuild."""
    built = json.loads((folder / LOOKS_FILE).read_text(encoding="utf-8"))
    if built.get("schema_version") != LOOKS_SCHEMA_VERSION:
        raise StageFailure(f"{LOOKS_FILE} has schema_version {built.get('schema_version')}; this Kiripix reads "
                           f"{LOOKS_SCHEMA_VERSION}. Rebuild it: kiripix run {asset} {LOOKS_STAGE} --force")
    listed: list[dict[str, Any]] = built["looks"]
    return listed


def check_looks(run: StageRun) -> list[Finding]:
    asset = run.asset_id
    findings: list[Finding] = []
    try:
        palette = palette_rgb(run)
    except StageFailure:
        palette = None  # the palette's own Checks report it
    for look in read_looks(run.output_dir, asset):
        name = str(look["id"])
        where = Position(asset=asset, stage=LOOKS_STAGE)
        if look["box"] is None:
            findings.append(Finding(
                code="look.no_region", severity="warning",
                message=f"the Look {name} has no region, so it shows nothing of its edit",
                position=where,
                owner_action=f"Mark where {name} changes the room: a polygon or a brush, or a difference over a box "
                             f"(kiripix decide {asset} {LOOKS_STAGE} --help).",
            ))
        else:
            x, y, width, height = (int(v) for v in look["box"])
            box = Position(asset=asset, stage=LOOKS_STAGE, x=x, y=y, width=width, height=height)
            if not look["changed"]:
                findings.append(Finding(
                    code="look.unchanged", severity="warning",
                    message=f"the Look {name} shows the room as it is: no pixel of its region differs from the "
                            "mapped room",
                    position=box,
                    owner_action=f"Check that the edit is of this room and that the region covers what changed; if "
                                 f"the edit changed nothing there, make it again (kiripix import {asset} <png> --look "
                                 f"{name}).",
                ))
            files = ([str(look["plate"])] if look["plate"] else []) + [str(e["file"]) for e in look["layers"]]
            for file in files:
                if palette is None:
                    break
                report = conformance(read_rgba(run.output_dir / file), palette)
                findings += [replace_position(f, asset, file) for f in check_alpha(report, file)]
                if report.off_palette:
                    px, py = report.first_off_palette[0]
                    findings.append(Finding(
                        code="look.off_palette",
                        message=f"{file} has {report.off_palette} pixels off the palette, the first at ({px}, {py})",
                        position=Position(asset=asset, stage=LOOKS_STAGE, file=file, x=px, y=py),
                        fix=f"kiripix run {asset} {LOOKS_STAGE} --force",
                    ))
        registration = look.get("registration")
        if registration and registration["problems"]:
            findings.append(Finding(
                code="look.misaligned",
                message=f"the edit of {name} doesn't lie on the Source: " + "; ".join(registration["problems"]),
                position=where,
                owner_action=f"Make the edit again so it keeps the Source's size and framing (kiripix import {asset} "
                             f"<png> --look {name}, then pick it), or draw the Look by hand over the Source.",
            ))
        drift = look["drift"]
        if drift:
            total = sum(int(d["pixels"]) for d in drift)
            listed = ", ".join(f"{d['width']}x{d['height']} at ({d['x']}, {d['y']}) [{d['pixels']} px]"
                               for d in drift[:DRIFT_LISTED])
            more = f", and {len(drift) - DRIFT_LISTED} smaller" if len(drift) > DRIFT_LISTED else ""
            first = drift[0]
            findings.append(Finding(
                code="look.drift", severity="warning",
                message=f"the edit of {name} redrew {total} px in {len(drift)} places outside its region: "
                        f"{listed}{more}",
                position=Position(asset=asset, stage=LOOKS_STAGE, x=int(first["x"]), y=int(first["y"]),
                                  width=int(first["width"]), height=int(first["height"])),
                owner_action=f"If the redraw belongs to the Look (a light pool, a shadow), grow its region over it "
                             f"(a polygon, a brush or a difference); if not, it is the model's noise outside the "
                             f"Look and is never shown. Largest first, at (x, y) of the boxes above.",
            ))
    return findings


def replace_position(finding: Finding, asset: str, file: str) -> Finding:
    """A finding from an Op's report, placed at the Look's file."""
    assert finding.position is not None
    finding.position.asset, finding.position.stage, finding.position.file = asset, LOOKS_STAGE, file
    return finding
