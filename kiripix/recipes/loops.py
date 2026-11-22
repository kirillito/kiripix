"""The room's `loops` Stage (ticket 0189, ADR 0009's sibling for things that always play): colour cycles.

A Loop is a part of the room that plays by itself, over and over, cut to a region. Where a Look is shown by game state
and cut from an edit, a Loop needs no edit here: a colour cycle steps chosen palette colours through a list inside the
region, on the room's own mapped pixels. Its first frame is the room, pixel for pixel. A character clip's `loop` flag
is something else.

Decisions, in target pixels, each naming its Loop in `loop`:

- `loop`: the Loop's ID, `form` (`cycle` or `frames`), `layer` (`plate`
  or a foreground Layer's ID), `light` (a light Marker's ID, optional) and `phase` (ticks);
- the region: `polygon`, `brush`, `flood` and `difference` (`regions`, shared with `looks`);
- `cycle`: `colours` (hex, on the palette), `mode` `rotate` or `pulse` (with `lift` and `steps`) and, for a pulse, the
  `emissive` flag;
- `frames` (a frame Loop, ticket 0192): `source` `op` with the Op's name (`sway`, `shimmer`, `scroll`) and `params`, or
  `source` `kit` (ticket 0194: the frames imported with `import --loop`, `kit` Decision; no `frames` Decision and an
  imported kit is the same), taken as painted, off-palette pixels mapped to the nearest colour (`loop.off_palette`, an error
  above 1 % of the region), strokes outside the region cut away (`loop.outside_region`);
- `timing`: `ticks` (one number or one per frame), `pingpong`, or `flicker` (`seed`, `mean_ticks`, `spread`,
  `length_ticks`), expanded into the Loop's `sequence` at build time by the Ops of `ops/cycle.py`.

Output, in the Stage's folder: `loops.json`, and per Loop a folder `<loop>/` holding `plate.png` and `layer.<id>.png` (the
distinct frames as one strip, side by side, wrapping into rows past 4096 px; cut by the Layer's alpha) and, for a cycle
with colours, `index.png` (8-bit: 0 outside the cycle's pixels, else 1 plus the colour's place in `colours`). Everything
is cropped to the region's box. Frame 0 of the strips together is the mapped room inside the region.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, replace
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
from kiripix.ops import (
    conformance,
    connected_regions,
    cut_by_alpha,
    cycle_index,
    cycle_pulse,
    cycle_rotate,
    cycle_seam_ratio,
    dilate,
    drift_boxes,
    even_sequence,
    fill_polygon,
    flash_count,
    flicker_sequence,
    mask_box,
    paint_stroke,
    quantize,
    scroll,
    scroll_period,
    seam_ratio,
    shimmer,
    sway,
)
from kiripix.ops.frames import (
    SHIMMER_AMPLITUDE,
    SHIMMER_FRAMES,
    SHIMMER_WAVELENGTH,
    SWAY_AMPLITUDE,
    SWAY_FRAMES,
)
from kiripix.ops.cycle import (
    EVEN_TICKS,
    FLASH_PER_SECOND,
    FLICKER_LENGTH_TICKS,
    FLICKER_MEAN_TICKS,
    FLICKER_SPREAD,
    PULSE_LIFT,
    PULSE_STEPS,
)
from kiripix.recipes.base import CheckSpec, CurrentDecision, DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.common import box_problem, map_to_palette, palette_rgb, read_grid, read_rgba, write_rgba
from kiripix.recipes.kit_record import (
    HASH,
    KIT_DECISION,
    KIT_DIR,
    frame_path,
    kit_command,
    kit_needs_input,
    kit_of,
    palette_moved,
)
from kiripix.recipes.layers import LAYERS_FILE, layer_file, read_layers
from kiripix.recipes.looks import DRIFT_MIN_PIECE, EditFit, current_source, fitted_edit_file, look_ids, read_looks
from kiripix.recipes.regions import (
    LOOKS_STAGE,
    OWNER_ID,
    EditRoom,
    brush_decision,
    decision_box,
    difference_decision,
    flood_decision,
    paint_region,
    polygon_decision,
    write_mask,
)
from kiripix.recipes.regions import decisions_of as _decisions_of

LOOPS_STAGE = "loops"
LOOPS_FILE = "loops.json"
REGION_FILE = "region.png"  # a held Loop's region, in its folder
HOLD_FILE = "hold.png"  # an edits Loop's held pixels, in its folder
LOOPS_SCHEMA_VERSION = 2  # 2: `held`, `lift` for `depth`, and an edits Loop's `edits`, `flicker`, `holds`, `past_layer` (0206, 0220, 0223)
PLATE = "plate"  # a Loop's `layer` when it sits on the Plate
STRIP_WIDTH = 4096  # px: a strip wraps into rows past this
SEAM_LIMIT = 3.0  # `loop.seam` warns over this ratio (confirmed by 0184: its Loops measured 0.94 to 1.6)
PULSE_REACH = 2  # px: a pulse region beyond this from the pixels of its picked colours is `loop.pulse_spills` (kept: 0184 didn't measure it)
KIT_OFF_PALETTE_ERROR = 0.01  # a kit frame with more than this share of its region off the palette is an error (kept)
FLICKER_SHARE = 0.30  # `loop.flicker` warns when more than this share of the region outside every `hold` changes between edit frames (trial 0184: a boiling TV measured 0.48 to 0.64, held 0)
SLOWER = (2, 3, 4, 6, 8, 12, 16)  # the factors `loop.flash` tries for the timing it suggests
HEX = "^#[0-9A-Fa-f]{6}$"

LOOP_PROPERTY: dict[str, Any] = {"type": "string", "pattern": OWNER_ID}
STAGE_TEXT = (
    "A Loop always plays, over and over, cut to a region; a Look is shown by game state. A character clip's `loop` flag "
    "(whether a clip repeats) is something else."
)


def _loop_decision() -> DecisionSpec:
    return DecisionSpec(
        name="loop",
        description="Declare a Loop: its ID (the Marker ID rule, unique among the room's Looks and Loops), its `form` "
                    "(`cycle`: chosen palette colours step through a list; `frames`: its frames come from a `frames` "
                    "Decision), the `layer` it sits on (`plate`, the default, or a foreground Layer's ID: the "
                    "region is then cut to that Layer's alpha), an optional `light` (the ID of a light Marker that "
                    "follows the Loop) and its `phase` in ticks (default 0). The latest Decision of a Loop replaces the whole "
                    "Decision before it, so it must carry every field. A Loop that can't be built yet (no `cycle`, no "
                    "frames, an ID a Look has) is held and shown as its region; the others are built. "
                    + STAGE_TEXT,
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "form": {"enum": ["cycle", "frames"]},
                "layer": {"type": "string", "pattern": OWNER_ID},
                "light": {"type": "string", "pattern": OWNER_ID},
                "phase": {"type": "integer", "minimum": 0},
            },
            "required": ["loop"],
            "additionalProperties": False,
        },
    )


def _cycle_decision() -> DecisionSpec:
    return DecisionSpec(
        name="cycle",
        description="A Loop's colour cycle. `rotate` (the default) steps each pixel of the region whose colour is in "
                    "`colours` (hex, in order, at least two, each on the palette) to the next colour in the list, "
                    "`steps` frames (default: one per colour). `pulse` lightens each region pixel by `lift` "
                    f"(OKLab L) along its own colour ramp and back, over `steps` frames (defaults {PULSE_LIFT} and "
                    f"{PULSE_STEPS}); `colours` then limits the pulse to the pixels of those colours, and is optional. "
                    "`emissive` (default true, pulse only) tells the game that the pulse lights what is around it. "
                    "Frame 0 is the room's own pixels. The latest Decision of a Loop replaces the whole Decision before it, so it "
                    "must carry every field.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "colours": {"type": "array", "items": {"type": "string", "pattern": HEX}, "uniqueItems": True},
                "mode": {"enum": ["rotate", "pulse"]},
                "lift": {"type": "number", "exclusiveMinimum": 0},
                "depth": {"type": "integer", "minimum": 1, "description": "Refused: use `lift`, depth x 0.075."},
                "steps": {"type": "integer", "minimum": 2},
                "emissive": {"type": "boolean"},
            },
            "required": ["loop"],
            "additionalProperties": False,
        },
    )


FRAME_OPS = ("sway", "shimmer", "scroll")
FRAME_PARAMS: dict[str, tuple[str, ...]] = {
    "sway": ("anchor_row", "amplitude", "frames"),
    "shimmer": ("amplitude", "wavelength", "frames"),
    "scroll": ("dx", "dy", "frames"),
}


def _frames_problem(data: dict[str, Any]) -> str | None:
    if data.get("source", "op") in ("kit", "edits"):
        return None  # a kit's frames and edit frames are imported, not named here
    op = data.get("op")
    if op not in FRAME_OPS:
        return f"a `frames` Decision with source op names an `op`: one of {', '.join(FRAME_OPS)}"
    extra = sorted(set(data.get("params", {})) - set(FRAME_PARAMS[str(op)]))
    if extra:
        return f"{op} takes {', '.join(FRAME_PARAMS[str(op)])}, not {', '.join(extra)}"
    params = data.get("params", {})
    if op == "scroll" and not (params.get("dx", 0) or params.get("dy", 0)):
        return "scroll needs a dx or a dy that isn't zero"
    return None


def _frames_decision() -> DecisionSpec:
    number: dict[str, Any] = {"type": "number", "minimum": 0}
    whole: dict[str, Any] = {"type": "integer"}
    return DecisionSpec(
        name="frames",
        description="Where a frame Loop's frames come from. `source` `op` (the default) builds them from the room's own "
                    "pixels by an Op, named in `op`, with `params`: `sway` (`anchor_row`, a row of the room, default the "
                    f"bottom of the region; `amplitude` {SWAY_AMPLITUDE} px at the far end; `frames` {SWAY_FRAMES}) "
                    "shears a foreground Layer from its anchor, and needs the Loop's `layer` to be that Layer (on the "
                    "Plate it has no fill and is `loop.no_fill`); `shimmer` (`amplitude` "
                    f"{SHIMMER_AMPLITUDE}, `wavelength` {SHIMMER_WAVELENGTH} rows, `frames` {SHIMMER_FRAMES}) shifts the "
                    "region's rows sideways in a wave; `scroll` (`dx`, `dy` px a frame, `frames` default the period of the "
                    "wrap) moves the region's pixels, wrapping within its box. Frame 0 is the room. `source` `kit` (frames "
                    "the Owner imported with `import --loop`) takes them as painted: an off-palette pixel maps to the "
                    "nearest colour, strokes outside the region are cut away, and on a Layer a transparent pixel shows "
                    "the Plate's fill. A Loop with no `frames` Decision and an imported kit is the same. `source` `edits` "
                    "takes each frame from an edit of the room's Source (`import --loop <loop> --frame <n>`, then "
                    "`pick --loop <loop> --frame <n>`, the `pick` Decision): each edit is made from the Source, never from "
                    "another edit. A frame Loop's frames come from one source only. The latest Decision of a Loop counts.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "source": {"enum": ["op", "kit", "edits"]},
                "op": {"enum": list(FRAME_OPS)},
                "params": {
                    "type": "object",
                    "properties": {
                        "anchor_row": {"type": "integer", "minimum": 0},
                        "amplitude": number,
                        "wavelength": {"type": "number", "exclusiveMinimum": 0},
                        "dx": whole,
                        "dy": whole,
                        "frames": {"type": "integer", "minimum": 2},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["loop"],
            "additionalProperties": False,
        },
        problem=_frames_problem,
    )


def _timing_decision() -> DecisionSpec:
    ticks: dict[str, Any] = {"type": "integer", "minimum": 1}
    return DecisionSpec(
        name="timing",
        description="A Loop's timing, in whole game ticks (60 a second). `ticks` is one number (every frame for that long; "
                    f"default {EVEN_TICKS}) or a list with one per frame; `pingpong` plays 0 1 ... n-1 ... 1 so the loop's "
                    "wrap repeats no frame. Or `flicker`: a fixed, seeded sequence over the frames "
                    f"(`seed`, `mean_ticks` {FLICKER_MEAN_TICKS}, `spread` {FLICKER_SPREAD:g}, `length_ticks` "
                    f"{FLICKER_LENGTH_TICKS}), the same on every platform; it takes neither `ticks` nor `pingpong`. "
                    "`rest` (default false) makes frame 0, the room, a rest frame the sequence never plays: it plays frames "
                    "1 on (`ticks` as a list gives one number per played frame; `pingpong` and `flicker` use frames 1 on), "
                    "so a screen that is off in the room doesn't go dark on every loop; it needs at least 3 frames. "
                    "The latest Decision of a Loop replaces the whole Decision before it, so it must carry every field.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "ticks": {"oneOf": [ticks, {"type": "array", "items": ticks, "minItems": 1}]},
                "pingpong": {"type": "boolean"},
                "rest": {"type": "boolean"},
                "flicker": {
                    "type": "object",
                    "properties": {"seed": {"type": "integer", "minimum": 0}, "mean_ticks": ticks,
                                   "spread": {"type": "number", "minimum": 0, "maximum": 1}, "length_ticks": ticks},
                    "required": ["seed"],
                    "additionalProperties": False,
                },
            },
            "required": ["loop"],
            "additionalProperties": False,
        },
        problem=lambda data: ("`flicker` takes neither `ticks` nor `pingpong`" if "flicker" in data
                              and ("ticks" in data or "pingpong" in data) else None),
    )


def _pick_decision() -> DecisionSpec:
    return DecisionSpec(
        name="pick",
        description="Choose one edit Variant of a frame of a Loop whose frames are edits of the room's Source "
                    "(`src/loops/<loop>/edits/<frame>/<variant>.png`, `kiripix import <asset> <png> --loop <loop> --frame "
                    "<n>`). `frame` counts from 1: frame 0 is the room. `source` is the room's Source (its Variant name) "
                    "the edit was made on: a pick whose `source` isn't the room's current Source puts the Loop in "
                    "needs-input, because an edit of the old picture must never be cut into the new one. `was` (set by "
                    "Kiripix, not by hand) is the ID the edit's folder is named for, after a `rename`. "
                    "`kiripix pick <asset> <variant> --loop <loop> --frame <n>` records it. The latest Pick of a frame "
                    "counts.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "frame": {"type": "integer", "minimum": 1},
                "variant": {"type": "string", "pattern": HASH},
                "source": {"type": "string"},
                "was": {"type": "string", "pattern": OWNER_ID},
            },
            "required": ["loop", "frame", "variant", "source"],
            "additionalProperties": False,
        },
    )


def _hold_decision() -> DecisionSpec:
    return DecisionSpec(
        name="hold",
        description="Keep a part of an edit-frame Loop still: `points` are a polygon (at least three corners) or, with a "
                    "`radius`, a brush stroke, in target pixels, cut to the Loop's region (what falls outside it is "
                    "reported, `loop.hold_outside_region`). In every frame from 1 on, the held part takes the pixels of "
                    "edit frame `frame` (1 or more), so only the rest of the region moves: the ticker under a still "
                    "news picture. Frame 0 stays the room. A later `hold` over the same pixels wins; `erase` gives pixels "
                    "back to the frames. The frames are edits of the Source, not of each other: a boiling picture is "
                    "held from one edit.",
        entry_schema={
            "type": "object",
            "properties": {"loop": LOOP_PROPERTY, "frame": {"type": "integer", "minimum": 1},
                           "erase": {"type": "boolean"}, "radius": {"type": "integer", "minimum": 0},
                           "points": {"type": "array", "items": {"type": "array", "items": {"type": "integer"},
                                                                 "minItems": 2, "maxItems": 2}}},
            "required": ["loop", "frame", "points"],
            "additionalProperties": False,
        },
        problem=lambda data: (f"a polygon needs at least three points, got {len(data['points'])}; give a `radius` for a "
                              "brush stroke" if "radius" not in data and len(data["points"]) < 3 else None),
    )


def _remove_decision() -> DecisionSpec:
    return DecisionSpec(
        name="remove",
        description="Take a Loop away: the Loop and every Decision before this one that names it stop applying (the "
                    "Decisions after it start a new Loop). Refused for a Loop the game's Manifest lists (its ID is frozen). "
                    "Undo brings the Loop back.",
        entry_schema={"type": "object", "properties": {"loop": LOOP_PROPERTY}, "required": ["loop"],
                      "additionalProperties": False},
    )


def _rename_decision() -> DecisionSpec:
    return DecisionSpec(
        name="rename",
        description="Give a Loop another ID, `to` (the Marker ID rule, free among the room's Looks and Loops). The "
                    "Decisions before this one that name `loop` apply to `to`, and the ones after it name `to`. A kit "
                    "Loop keeps its imported frames. Refused for a Loop the game's Manifest lists (its ID is frozen). "
                    "Undo brings the old ID back.",
        entry_schema={"type": "object", "properties": {"loop": LOOP_PROPERTY, "to": LOOP_PROPERTY},
                      "required": ["loop", "to"], "additionalProperties": False},
    )


DECISIONS = (
    _loop_decision(),
    _remove_decision(),
    _rename_decision(),
    polygon_decision("loop", "Loop", "A Loop plays only inside its region."),
    brush_decision("loop", "Loop"),
    flood_decision("loop", "Loop"),
    difference_decision(
        "loop",
        "Add to a Loop's region what a frame of the Loop redrew inside a box (frame Loops, ticket 0192). A colour cycle "
        "has no edit to compare, so a cycle Loop that has one is held back (needs-input)."),
    _cycle_decision(),
    _frames_decision(),
    KIT_DECISION,
    _pick_decision(),
    _hold_decision(),
    _timing_decision(),
)

CHECKS = (
    CheckSpec(code="loop.held", description="A Loop can be built: it has what it needs (a cycle, frames, a Layer of the "
                                            "room, an ID of its own). A held Loop shows its region and plays nothing; "
                                            "`export` refuses the room while one is held (error)."),
    CheckSpec(code="loop.off_palette", description="Every pixel of a Loop's strips, and each colour of its cycle, is a "
                                                   "palette colour."),
    CheckSpec(code="loop.outside_region", description="A kit frame changes the room only inside the Loop's region; what it "
                                                       "changes outside is cut away (warning, one per patch)."),
    CheckSpec(code="loop.partial_alpha", description="A kit frame's alpha is 0 or 255."),
    CheckSpec(code="loop.frame0",description="Frame 0 of a Loop's strips is the room inside its region, pixel for pixel."),
    CheckSpec(code="loop.stale_size", description="A Loop's region lies inside the palette image; when the palette image "
                                                  "changed size, frame 0 isn't compared until a rebuild."),
    CheckSpec(code="loop.seam", description=f"The loop's wrap is no rougher than {SEAM_LIMIT:g} times the change "
                                            "between its other frames (warning)."),
    CheckSpec(code="loop.still", description="A Loop's frames differ from frame 0 somewhere (warning)."),
    CheckSpec(code="loop.flash", description=f"A Loop flashes no more than {FLASH_PER_SECOND} times a second "
                                             "(WCAG 2.3.1)."),
    CheckSpec(code="loop.misaligned", description="Each edit frame lies on the Source within the registration's limits, as a "
                                                  "Look's edit does (error)."),
    CheckSpec(code="loop.drift", description="An edit frame redrew nothing outside the Loop's region, within a Look's limit "
                                             "(warning)."),
    CheckSpec(code="loop.flicker", description=f"Between consecutive edit frames, no more than {FLICKER_SHARE:.0%} of the "
                                               "region outside every `hold` changes (warning)."),
    CheckSpec(code="loop.past_layer", description="On a Layer, no edit frame changes pixels outside the Layer's alpha, where "
                                                  "it is cut (warning)."),
    CheckSpec(code="loop.hold_outside_region", description="A `hold` lies inside the Loop's region; what falls outside it is "
                                                           "cut away (info)."),
    CheckSpec(code="loop.overlaps_look", description="A Loop's region doesn't overlap a Look's (warning)."),
    CheckSpec(code="loop.pulse_spills", description=f"A pulse's region reaches no more than {PULSE_REACH} px beyond the "
                                                    "pixels of its picked colours (info)."),
    CheckSpec(code="loop.no_fill", description="A `sway` Loop sits on a foreground Layer: on the Plate there is no fill "
                                              "for what it uncovers."),
    CheckSpec(code="loop.no_region", description="A Loop has a region (warning)."),
    CheckSpec(code="loop.texture", description="How many frames and bytes the room's Loops take (info)."),
)

# `loop.light_unknown` (a `light` that names no light Marker) is checked by `export`, which sees the Markers.


# reading the Decisions


def apply_edits(decisions: tuple[CurrentDecision, ...]) -> tuple[CurrentDecision, ...]:
    """The Decisions with each `remove` and `rename` replayed in order (`StageSpec.decisions_view`): a `remove` drops the
    Loop's earlier Decisions, a `rename` gives them the new ID, and neither is in the result. A renamed `kit` or `pick`
    keeps the folder its frames were stored in under `was`."""
    kept: list[CurrentDecision] = []
    for decision in decisions:
        if decision.name == "remove":
            kept = [d for d in kept if d.data.get("loop") != decision.data["loop"]]
        elif decision.name == "rename":
            old, new = decision.data["loop"], decision.data["to"]
            kept = [replace(d, data={**d.data, "loop": new, **({"was": d.data.get("was", old)} if d.name in ("kit", "pick") else {})})
                    if d.data.get("loop") == old else d for d in kept]
        else:
            kept.append(decision)
    return tuple(kept)


def former_ids(decisions: tuple[CurrentDecision, ...], loop: str) -> list[str]:
    """The IDs a Loop has had, its own last, from the `rename` Decisions in the journal as recorded: the folders its files
    may be stored under. The same rules as `apply_edits`."""
    known: dict[str, list[str]] = {}
    for decision in decisions:
        if decision.name == "remove":
            known.pop(str(decision.data["loop"]), None)
        elif decision.name == "rename":
            old, new = str(decision.data["loop"]), str(decision.data["to"])
            known[new] = [*(i for i in known.pop(old, [old]) if i != new), new]
    return known.get(loop, [loop])


def edit_problems(asset: str, decisions: tuple[CurrentDecision, ...], documents: list[tuple[str, dict[str, Any]]],
                  looks: set[str]) -> tuple[list[Finding], list[str]]:
    """What refuses a `remove` or `rename` of a Loop before it is recorded, by the rules of `apply_edits`: a Loop the room
    doesn't declare, a rename to its own ID, or to an ID a Look (`looks`) or another Loop has. `decisions` are the `loops`
    Decisions as recorded; `documents` the (Decision, data) pairs about to be recorded, in order, where a `loop` declares
    its Loop for the ones after it. Also gives the Loops removed or renamed, for the ID freeze."""
    loops = set(declared_ids(decisions))
    where = Position(asset=asset, stage=LOOPS_STAGE)
    found: list[Finding] = []
    edited: list[str] = []
    for name, data in documents:
        if not isinstance(data.get("loop"), str):
            continue  # the Decision's schema refuses it
        loop = str(data["loop"])
        if name == "loop":
            loops.add(loop)
        if name not in LOOP_EDITS:
            continue
        if loop not in loops:
            found.append(Finding(
                code="loop.unknown", message=f"{asset} has no Loop {loop}, so it can't be {name}d"
                                             + (f"; its Loops are {', '.join(sorted(loops))}" if loops else ""),
                position=where, fix=f"kiripix describe room --stage {LOOPS_STAGE}"))
            continue
        edited.append(loop)
        loops.discard(loop)
        if name == "rename":
            new = str(data.get("to"))
            if new == loop:
                found.append(Finding(code="loop.rename_same", message=f"the Loop {loop} is renamed to its own ID",
                                     position=where, owner_action="Give the Loop another ID, or leave it."))
            elif new in loops or new in looks:
                found.append(Finding(
                    code="loop.id_taken", message=f"{asset} already has a {'Look' if new in looks else 'Loop'} {new}; "
                                                  "a Look's and a Loop's IDs are one set",
                    position=where, owner_action=f"Rename {loop} to an ID that no Look or Loop of the room has."))
            loops.add(new)
    return found, edited


LOOP_EDITS = ("remove", "rename")  # the `loops` Decisions that take a Loop's ID away


def declared_ids(decisions: tuple[CurrentDecision, ...]) -> list[str]:
    """The IDs of the Loops the Stage declares once the journal is replayed (what the ID freeze compares), sorted."""
    return sorted({str(d.data["loop"]) for d in apply_edits(decisions) if d.name == "loop"})


def decisions_of(run: StageRun, loop: str, *names: str) -> list[CurrentDecision]:
    """The Loop's current Decisions of these kinds, in order."""
    return _decisions_of(run, "loop", loop, *names)


def _latest(run: StageRun, name: str) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for decision in run.decisions:
        if decision.name == name:
            found[str(decision.data["loop"])] = dict(decision.data)
    return found


def declared(run: StageRun) -> dict[str, dict[str, Any]]:
    """Each Loop, by ID, with its latest `loop` Decision's data."""
    return _latest(run, "loop")


def hex_rgb(colours: list[str]) -> Any:
    return np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in colours], dtype=np.uint8).reshape(-1, 3)


def hex_of(rgb: Any) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(v) for v in rgb))


def frame_count(cycle: dict[str, Any] | None) -> int | None:
    """How many distinct frames a `cycle` Decision gives, or None without one."""
    if cycle is None:
        return None
    if cycle.get("mode", "rotate") == "pulse":
        return int(cycle.get("steps", PULSE_STEPS))
    return int(cycle.get("steps", len(cycle.get("colours", []))))


def frame_op_count(frame: dict[str, Any] | None) -> int | None:
    """How many frames a `frames` Decision (source op) gives, or None when it isn't known before the region is."""
    if frame is None:
        return None
    params = frame.get("params", {})
    if "frames" in params:
        return int(params["frames"])
    return {"sway": SWAY_FRAMES, "shimmer": SHIMMER_FRAMES}.get(str(frame.get("op")))


def sequence_of(timing: dict[str, Any] | None, frames: int) -> list[tuple[int, int]]:
    """The Loop's `sequence` (frame, ticks), from its `timing` Decision, by the Ops of `ops/cycle.py`."""
    timing = timing or {}
    rest = bool(timing.get("rest", False))
    if rest and frames < 3:
        raise ValueError(f"`rest` needs at least 3 frames (frame 0 rests, two or more play), and there are {frames}")
    ids = list(range(1 if rest else 0, frames))
    if "flicker" in timing:
        flicker = timing["flicker"]
        return flicker_sequence(int(flicker["seed"]), ids, int(flicker.get("mean_ticks", FLICKER_MEAN_TICKS)),
                                float(flicker.get("spread", FLICKER_SPREAD)),
                                int(flicker.get("length_ticks", FLICKER_LENGTH_TICKS)))
    ticks = timing.get("ticks", EVEN_TICKS)
    order = even_sequence(ids, 1, bool(timing.get("pingpong", False)))
    if isinstance(ticks, list):
        if len(ticks) != len(ids):
            raise ValueError(f"ticks lists {len(ticks)} numbers for {len(ids)} played frames"
                             if rest else f"ticks lists {len(ticks)} numbers for {frames} frames")
        return [(frame, int(ticks[frame - ids[0]])) for frame, _ in order]
    return [(frame, int(ticks)) for frame, _ in order]


def _layer_ids(run: StageRun) -> list[str] | None:
    folder = run.upstream.get("layers")
    if folder is None or not (folder / LAYERS_FILE).is_file():
        return None
    try:
        return [str(entry["id"]) for entry in read_layers(folder, run.asset_id)]
    except StageFailure:
        return None


def source_of(frame: dict[str, Any] | None, kit: dict[str, Any] | None, picks: dict[int, dict[str, Any]]) -> str | None:
    """Where a frame Loop's frames come from: its `frames` Decision's `source` (`op`, `kit` or `edits`); with none, `kit`
    when a kit is imported, else `edits` when an edit is picked; None when nothing says."""
    if frame is not None:
        return str(frame.get("source", "op"))
    if kit is not None:
        return "kit"
    return "edits" if picks else None


def is_kit(frame: dict[str, Any] | None, kit: dict[str, Any] | None) -> bool:
    """Whether a frame Loop takes its frames from its kit."""
    return source_of(frame, kit, {}) == "kit"


@dataclass(frozen=True)
class LoopInputs:
    """One Loop and what was decided about it: what each held reason below looks at. `look_ids` is the set of Look IDs."""

    run: StageRun
    name: str
    loop: dict[str, Any]
    cycle: dict[str, Any] | None
    timing: dict[str, Any] | None
    frames: dict[str, Any] | None
    layers: list[str] | None  # the room's Layer IDs, or None when they can't be read
    look_ids: frozenset[str]
    kit: dict[str, Any] | None  # the Loop's imported kit
    picks: dict[int, dict[str, Any]]  # its edit Picks by frame

    @property
    def framed(self) -> bool:
        return self.loop.get("form", "cycle") == "frames"

    @property
    def source(self) -> str | None:
        """Where its frames come from (`source_of`)."""
        return source_of(self.frames, self.kit, self.picks)

    @property
    def undo(self) -> str:
        return f"kiripix undo {self.run.asset_id} {LOOPS_STAGE}"


# a Loop whose frames are edits of the Source (ticket 0219)


def edit_path(folder: str, frame: int, variant: str) -> str:
    """An edit frame's Variant, relative to the Asset folder (the key of `StageRun.files`); `folder` is the ID the Loop's
    files are stored under (a renamed Loop's `was`, else its ID)."""
    return f"{KIT_DIR}/{folder}/edits/{frame}/{variant}.png"


def edit_picks(run: StageRun, loop: str) -> dict[int, dict[str, Any]]:
    """The Loop's current edit Picks by frame number (from 1); the latest Pick of a frame counts."""
    return {int(d.data["frame"]): dict(d.data) for d in decisions_of(run, loop, "pick")}


def is_edits(frame: dict[str, Any] | None, picks: dict[int, dict[str, Any]], kit: dict[str, Any] | None) -> bool:
    """Whether a frame Loop takes its frames from edits of the Source."""
    return source_of(frame, kit, picks) == "edits"


def frames_source(run: StageRun, loop: str) -> str | None:
    """Where a frame Loop's frames come from as far as it is decided (`source_of`)."""
    chosen = decisions_of(run, loop, "frames")
    return source_of(dict(chosen[-1].data) if chosen else None, kit_of(run, loop), edit_picks(run, loop))


def _held_mixed(one: LoopInputs) -> NeedsInput | None:
    """A frame Loop's frames come from one source only: picked edit frames beside a kit, or beside a `frames` Decision
    that takes them from an Op or a kit, are refused rather than one of them dropped without a word."""
    if not one.framed or not one.picks or one.source == "edits" and one.kit is None:
        return None
    other = "an imported kit" if one.kit is not None else f"its `frames` Decision's source {one.source}"
    return NeedsInput(f"the Loop {one.name} has picked edit frames and {other}; a frame Loop's frames come from one source "
                      "only",
                      owner_action=f"Keep one: undo the Decisions of the other ({one.undo}), or declare the edit frames on "
                                   "a Loop of their own.")


def _held_edits(one: LoopInputs) -> NeedsInput | None:
    """An edits Loop's reasons: an edit made on another Source, a frame with no Pick, a Pick whose image is gone."""
    if not one.framed or one.source != "edits":
        return None
    run, name, picks = one.run, one.name, one.picks
    asset = run.asset_id
    source = current_source(run)
    old = sorted(frame for frame, pick in picks.items() if source is not None and str(pick["source"]) != source)
    if old:
        again = "; ".join(f"kiripix import {asset} <png> --loop {name} --frame {n}, then kiripix pick {asset} <variant> "
                          f"--loop {name} --frame {n}" for n in old)
        return NeedsInput(f"the edit frames of {name} were made on another Source",
                          owner_action=f"Re-make frame{'s' if len(old) > 1 else ''} {', '.join(str(n) for n in old)} from "
                                       f"the new Source, each from the Source and not from another edit ({again}).")
    wanted = max(picks, default=0) + (0 if picks else 1)
    for number in range(1, wanted + 1):
        if number in picks:
            continue
        stored = sorted(Path(file).stem for file in run.files if file.startswith(f"{KIT_DIR}/") and
                        file.endswith(".png") and f"/edits/{number}/" in file)
        if len(stored) == 1:
            return NeedsInput(f"frame {number} of {name} has no picked edit", command=f"kiripix pick {asset} {stored[0]} "
                                                                                     f"--loop {name} --frame {number}")
        return NeedsInput(f"frame {number} of {name} has no picked edit",
                          owner_action=(f"Pick one of its edits {', '.join(stored)} (kiripix pick {asset} <variant> --loop "
                                        f"{name} --frame {number})" if stored else f"Import an edit of the Source for frame "
                                        f"{number} (kiripix import {asset} <png> --loop {name} --frame {number}) and pick it"))
    for number, pick in sorted(picks.items()):
        if edit_path(str(pick.get("was", name)), number, str(pick["variant"])) not in run.files:
            return NeedsInput(f"the picked edit {pick['variant']} of frame {number} of {name} was deleted",
                              owner_action=f"Import an edit again (kiripix import {asset} <png> --loop {name} --frame "
                                           f"{number}) and pick it.")
    return None


def _held_hold(one: LoopInputs) -> NeedsInput | None:
    """A `hold` belongs to a Loop of edit frames and names one of its frames."""
    holds = decisions_of(one.run, one.name, "hold")
    if not holds:
        return None
    run, name, picks = one.run, one.name, one.picks
    if not one.framed or one.source != "edits":
        return NeedsInput(f"the Loop {name} has a `hold`, which keeps a part of an edit frame still; its frames aren't edits",
                          owner_action=f"Undo it ({one.undo}).")
    last = max(picks, default=0)
    for hold in holds:
        if int(hold.data["frame"]) > last:
            return NeedsInput(f"a `hold` of {name} names frame {hold.data['frame']}, and the Loop's last edit frame is {last}",
                              owner_action=f"Decide it again with one of frames 1 to {last}, or pick frame {hold.data['frame']} "
                                           f"(kiripix pick {run.asset_id} <variant> --loop {name} --frame {hold.data['frame']}).")
    return None


def _held_id_clash(one: LoopInputs) -> NeedsInput | None:
    if one.name not in one.look_ids:
        return None
    asset = one.run.asset_id
    return NeedsInput(
        f"the Loop {one.name} has the ID of a Look",
        owner_action=f"A Look's and a Loop's IDs are one set. Either give the Loop another ID (a `rename` Decision: "
                     f"kiripix decide {asset} {LOOPS_STAGE} --decision '{{\"decision\": \"rename\", \"data\": "
                     f"{{\"loop\": \"{one.name}\", \"to\": \"<new id>\"}}}}'), or give the Look another ID (undo its "
                     f"`pick` in `looks`: kiripix undo {asset} looks, and pick it again under another ID).")


def _held_layer(one: LoopInputs) -> NeedsInput | None:
    layer = str(one.loop.get("layer", PLATE))
    if layer == PLATE or one.layers is None or layer in one.layers:
        return None
    return NeedsInput(f"the Loop {one.name} sits on the Layer {layer}, which the room doesn't have",
                      owner_action=f"Declare the Loop again on the Plate or on one of "
                                   f"{', '.join(one.layers) or 'no Layers'} "
                                   f"(kiripix decide {one.run.asset_id} {LOOPS_STAGE} --help).")


def _held_frames(one: LoopInputs) -> NeedsInput | None:
    """A frame Loop's reasons: no frames at all, a kit that isn't there or was painted on another fit, a `difference`, a
    timing of the wrong length."""
    if not one.framed:
        return None
    run, name, frame, timing, picks, kit = one.run, one.name, one.frames, one.timing, one.picks, one.kit
    asset, undo = run.asset_id, one.undo
    edits = one.source == "edits"
    kept = None if edits else kit_needs_input(run, name)  # no frames at all: `next` suggests `loop kit`; a kit painted on another fit (0193)
    if kept is not None:
        return kept
    if frame is None and kit is None and not edits:
        return NeedsInput(f"the Loop {name} is a frame Loop with no `frames` Decision",
                          owner_action=f"Say where its frames come from (kiripix decide {asset} {LOOPS_STAGE} --help, "
                                       "the `frames` Decision).")
    if not edits and is_kit(frame, kit) and kit is None:
        return NeedsInput(f"the Loop {name} takes its frames from a kit, and none is imported",
                          command=kit_command(asset, name))
    if decisions_of(run, name, "difference"):
        return NeedsInput(f"the Loop {name} builds its frames by an Op, a kit or several edits, and a `difference` compares "
                          "one edit with the room",
                          owner_action=f"Undo it ({undo}) and mark the region with a flood, a polygon or a brush.")
    try:
        count = (1 + max(picks, default=0) if edits else
                 1 + len(kit["frames"]) if is_kit(frame, kit) and kit is not None else frame_op_count(frame))
        if count is not None:
            sequence_of(timing, count)
    except ValueError as error:
        return NeedsInput(f"the timing of {name}: {error}", owner_action=_ticks_advice(timing, undo))
    return None


def _ticks_advice(timing: dict[str, Any] | None, undo: str) -> str:
    each = "per played frame (frame 0 rests and isn't played)" if (timing or {}).get("rest") else "per frame"
    return f"Give one number {each}, or a single number ({undo})."


DEPTH_TO_LIFT = 0.075  # a pulse's old `depth` in ramp places, in OKLab L on the 283-colour palette (ticket 0223)


def _held_cycle(one: LoopInputs) -> NeedsInput | None:
    """A colour cycle's reasons: a `frames` Decision, no cycle, too few or repeated colours, a timing of the wrong length,
    a `difference`."""
    if one.loop.get("form", "cycle") == "frames":
        return None
    run, name, cycle = one.run, one.name, one.cycle
    asset, undo = run.asset_id, one.undo
    if one.frames is not None:
        return NeedsInput(f"the Loop {name} is a cycle, and a `frames` Decision gives a frame Loop its frames",
                          owner_action=f"Declare the Loop again with form frames, or undo the Decision ({undo}).")
    if cycle is None:
        return NeedsInput(f"the Loop {name} has no cycle",
                          owner_action=f"Give it one (kiripix decide {asset} {LOOPS_STAGE} --help, the `cycle` Decision).")
    colours = [str(c).lower() for c in cycle.get("colours", [])]
    if cycle.get("mode", "rotate") == "rotate" and len(colours) < 2:
        return NeedsInput(f"the rotating cycle of {name} lists {len(colours)} colours; it needs at least two",
                          owner_action=f"Give it its colours (kiripix decide {asset} {LOOPS_STAGE} --help).")
    if len(set(colours)) != len(colours):
        return NeedsInput(f"the cycle of {name} lists a colour twice", owner_action=f"List each colour once: {undo}.")
    try:
        sequence_of(one.timing, int(frame_count(cycle) or 0))
    except ValueError as error:
        return NeedsInput(f"the timing of {name}: {error}", owner_action=_ticks_advice(one.timing, undo))
    if "depth" in cycle:
        lift = round(float(cycle["depth"]) * DEPTH_TO_LIFT, 4)
        return NeedsInput(f"the pulse of {name} gives a `depth` in ramp places, which a pulse no longer takes; it takes a "
                          f"`lift` in OKLab lightness (`lift` = depth x {DEPTH_TO_LIFT} = {lift})",
                          owner_action=f"Decide the cycle again with `lift` {lift} in place of `depth` ({undo}).")
    if decisions_of(run, name, "difference"):
        return NeedsInput(f"the Loop {name} is a cycle, and a `difference` compares an edit with the room",
                          owner_action=f"Undo it ({undo}) and mark the region with a flood, a polygon or a brush.")
    return None


def _held_difference_box(one: LoopInputs) -> NeedsInput | None:
    read = read_grid(one.run)
    if read is None:
        return None
    for decision in decisions_of(one.run, one.name, "difference"):
        problem = box_problem(decision_box(decision), read[0].width, read[0].height, read[0].pad_right, read[0].pad_bottom)
        if problem is not None:
            return NeedsInput(f"the difference box of {one.name} {problem}", owner_action=f"Undo it: {one.undo}.")
    return None


# What can hold one Loop, in the order they are tried: the first that answers holds it, and the Stage builds the others.
# A new reason is a function of `LoopInputs` returning a `NeedsInput` (a `command` an agent can run, or an `owner_action`),
# added here; nothing else changes (the build, `loops.json`, `loop.held` and `next` take it from here).
HELD_REASONS: tuple[Callable[[LoopInputs], NeedsInput | None], ...] = (
    _held_id_clash, _held_layer, _held_mixed, _held_edits, _held_hold, _held_frames, _held_cycle, _held_difference_box)


def held_loops(run: StageRun) -> dict[str, NeedsInput]:
    """Each Loop that can't be built yet, by ID, with why."""
    loops = declared(run)
    cycles, timings, frames = _latest(run, "cycle"), _latest(run, "timing"), _latest(run, "frames")
    layers, looks = _layer_ids(run), frozenset(look_ids(run.upstream_decisions.get(LOOKS_STAGE, ())))
    held: dict[str, NeedsInput] = {}
    for name, loop in sorted(loops.items()):
        one = LoopInputs(run, name, loop, cycles.get(name), timings.get(name), frames.get(name), layers, looks,
                         kit_of(run, name), edit_picks(run, name))
        for reason in HELD_REASONS:
            found = reason(one)
            if found is not None:
                held[name] = found
                break
    return held


def loops_needs_input(run: StageRun) -> NeedsInput | None:
    """What holds the whole Stage: a Decision for a Loop nobody declared. What concerns one Loop holds only that Loop
    (`held_loops`)."""
    asset = run.asset_id
    loops = declared(run)
    for decision in run.decisions:
        name = str(decision.data["loop"])
        if name not in loops:
            return NeedsInput(f"the Decision {decision.name} names the Loop {name}, which is not declared",
                              owner_action=f"Declare it first (kiripix decide {asset} {LOOPS_STAGE} --decision "
                                           f"'{{\"decision\": \"loop\", \"data\": {{\"loop\": \"{name}\"}}}}'), or undo: "
                                           f"kiripix undo {asset} {LOOPS_STAGE}.")
    return None


# the build


def _strip(tiles: list[Any]) -> tuple[Any, int, int]:
    """The tiles side by side, wrapping into rows past `STRIP_WIDTH` px: the image, its columns and its rows."""
    height, width = tiles[0].shape[:2]
    columns = max(1, min(len(tiles), STRIP_WIDTH // width))
    rows = -(-len(tiles) // columns)
    image = np.zeros((rows * height, columns * width, 4), dtype=np.uint8)
    for n, tile in enumerate(tiles):
        row, column = divmod(n, columns)
        image[row * height:(row + 1) * height, column * width:(column + 1) * width] = tile
    return image, columns, rows


def _screen_area(run: StageRun) -> int:
    width, height = run.settings["project.resolution"]
    return int(width) * int(height)


def _slowed(timing: dict[str, Any], factor: int) -> dict[str, Any]:
    """The `timing` Decision's data, every hold `factor` times longer."""
    if "flicker" in timing:
        flicker = dict(timing["flicker"])
        flicker["mean_ticks"] = int(flicker.get("mean_ticks", FLICKER_MEAN_TICKS)) * factor
        flicker["length_ticks"] = int(flicker.get("length_ticks", FLICKER_LENGTH_TICKS)) * factor
        return {**timing, "flicker": flicker}
    ticks = timing.get("ticks", EVEN_TICKS)
    return {**timing, "ticks": [t * factor for t in ticks] if isinstance(ticks, list) else ticks * factor}


def _look_overlaps(run: StageRun, region: Any) -> list[dict[str, Any]]:
    """The Looks whose region shares a pixel with `region`, from their built pieces."""
    folder = run.upstream[LOOKS_STAGE]
    found = []
    for look in read_looks(folder, run.asset_id):
        if look["box"] is None:
            continue
        x, y, width, height = (int(v) for v in look["box"])
        covered = np.zeros(region.shape, dtype=np.bool_)
        for file in ([str(look["plate"])] if look["plate"] else []) + [str(e["file"]) for e in look["layers"]]:
            covered[y:y + height, x:x + width] |= read_rgba(folder / file)[..., 3] > 0
        shared = int((covered & region).sum())
        if shared:
            found.append({"look": str(look["id"]), "pixels": shared})
    return sorted(found, key=lambda entry: str(entry["look"]))


def _op_frames(run: StageRun, name: str, frame: dict[str, Any], composite: Any, region: Any, box: tuple[int, int, int, int],
               crop_y: int) -> Any:
    """The frames of a frame Loop from its Op, on the crop of the room: (frames, h, w, 4). A `sway` moves the pixels of the
    region (the Layer's), alpha with them; the others move the room's pixels inside the region."""
    op, params = str(frame.get("op")), dict(frame.get("params", {}))
    try:
        if op == "sway":
            anchor = int(params.get("anchor_row", box[1] + box[3] - 1))
            return sway(cut_by_alpha(composite, region), anchor - crop_y, float(params.get("amplitude", SWAY_AMPLITUDE)),
                        int(params.get("frames", SWAY_FRAMES)))
        if op == "shimmer":
            return shimmer(composite, region, float(params.get("amplitude", SHIMMER_AMPLITUDE)),
                           float(params.get("wavelength", SHIMMER_WAVELENGTH)), int(params.get("frames", SHIMMER_FRAMES)))
        if op == "scroll":
            count = params.get("frames")
            return scroll(composite, region, int(params.get("dx", 0)), int(params.get("dy", 0)),
                          None if count is None else int(count))
    except ValueError as error:
        raise StageFailure(f"the {op} of the Loop {name}: {error}") from None
    raise StageFailure(f"the Loop {name} names the Op {op}, which Kiripix doesn't have")


def _kit_frames(run: StageRun, name: str, kit: dict[str, Any], palette: Any, composite: Any, region: Any,
                box: tuple[int, int, int, int], on_layer: bool) -> tuple[Any, list[dict[str, Any]]]:
    """The frames of a frame Loop from its kit, on the crop of the room: (frames, h, w, 4), and per imported frame what
    was found in it. Frame 0 is the room. A kit frame is taken as painted, on the target grid already:

    - a pixel of the region with alpha 0 stays the room's (on the Plate) or is left empty (on a Layer: the Plate's fill
      shows there); a partial alpha counts as opaque from 128 and is reported, never rounded in silence;
    - a pixel off the palette takes the nearest palette colour in OKLab and is counted (a palette that moved since the
      kit was painted remaps without being reported: `remapped`);
    - a pixel outside the region that differs from the room is cut away; its patches' boxes are reported.
    """
    _, _, width, height = box
    moved = palette_moved(run, kit)
    packed = palette.astype(np.uint32) @ np.array([1 << 16, 1 << 8, 1], dtype=np.uint32)
    frames = [composite]
    found: list[dict[str, Any]] = []
    for number, stored in enumerate(kit["frames"], start=1):
        run.check_cancel()
        image = read_rgba(run.asset_dir / frame_path(str(kit.get("was", name)), str(stored)))  # `was`: a renamed Loop's frames stay in their folder
        if image.shape[:2] != (height, width):
            raise StageFailure(f"the kit frame {number} of the Loop {name} is {image.shape[1]}x{image.shape[0]}, the region "
                               f"is now {width}x{height}: write a new kit ({kit_command(run.asset_id, name)} --force)")
        alpha = image[..., 3]
        partial = (alpha != 0) & (alpha != 255)
        seen = alpha >= 128
        changed = seen & ((image[..., :3] != composite[..., :3]).any(axis=2) | (composite[..., 3] == 0))
        outside = changed & ~region
        patches = [[int(r[:, 1].min()), int(r[:, 0].min()), int(r[:, 1].max() - r[:, 1].min() + 1),
                    int(r[:, 0].max() - r[:, 0].min() + 1)] for r in connected_regions(outside, eight=True)]
        inside = seen & region
        rgba = image.copy()
        rgba[..., 3] = np.where(seen, 255, 0)
        colour = rgba[..., :3].astype(np.uint32) @ np.array([1 << 16, 1 << 8, 1], dtype=np.uint32)
        off = inside & ~np.isin(colour, packed)
        if off.any():
            rgba[off] = quantize(rgba, palette, 0, 0.0)[off]  # nearest in OKLab; ties to the lowest palette index
        first = np.argwhere(off)[0] if off.any() else None
        out = composite.copy()
        out[inside] = rgba[inside]
        if on_layer:
            out[region & ~seen] = 0  # the frame leaves it empty: the Plate's fill shows
        frames.append(out)
        found.append({
            "frame": number, "file": f"{stored}.png",
            "off_palette": 0 if moved else int(off.sum()), "remapped": int(off.sum()) if moved else 0,
            "first_off_palette": None if first is None or moved else [int(first[1]) + box[0], int(first[0]) + box[1]],
            "region_pixels": int(region.sum()), "partial_alpha": int(partial.sum()),
            "outside": [[x + box[0], y + box[1], w, h] for x, y, w, h in patches],
            "outside_pixels": int(outside.sum()),
        })
    return np.stack(frames), found


def _hold_masks(run: StageRun, name: str, shape: tuple[int, int], region: Any) -> tuple[Any, int]:
    """Each `hold` replayed in order: the frame every held pixel takes (0: not held), cut to the region, and how many held
    pixels fell outside the region."""
    taken = np.zeros(shape, dtype=np.int32)
    outside = np.zeros(shape, dtype=np.bool_)
    for decision in decisions_of(run, name, "hold"):
        data = decision.data
        points = [(int(x), int(y)) for x, y in data["points"]]
        empty = np.zeros(shape, dtype=np.bool_)
        part = (paint_stroke(empty, points, int(data["radius"])) if "radius" in data else fill_polygon(empty, points))
        outside |= part & ~region
        taken[part & region] = 0 if data.get("erase") else int(data["frame"])
    return taken, int(outside.sum())


def _edit_frames(run: StageRun, room: EditRoom, name: str, picks: dict[int, dict[str, Any]], drawn: Any, region: Any,
                 layer: str, box: tuple[int, int, int, int]) -> tuple[Any, dict[str, Any]]:
    """The frames of a Loop whose frames are edits of the Source, on the crop of the room: (frames, h, w, 4), frame 0 the
    room, and what the build found. Each picked edit goes through the path a Look's edit does (`fitted_edit_file`, with the
    `looks` Stage's parameters), the whole edit is mapped once, and the region is cut from it. `drawn` is the region before
    a Layer's alpha cut it; `region` is the Loop's. Frames 1 on take a `hold`'s pixels from the frame it names."""
    x, y, width, height = box
    crop = (slice(y, y + height), slice(x, x + width))
    fit = EditFit.of(run.upstream_params[LOOKS_STAGE])  # an edit frame is laid on the room as a Look's edit is
    frames = [room.composite[crop]]
    found: list[dict[str, Any]] = []
    past = np.zeros(region.shape, dtype=np.bool_)
    alpha = dict(room.layers).get(layer)
    for number in sorted(picks):
        run.check_cancel()
        pick = picks[number]
        variant = str(pick["variant"])
        path = run.files[edit_path(str(pick.get("was", name)), number, variant)]
        fitted, registration = fitted_edit_file(run, room, path, f"frame {number} of {name}", drawn, fit)
        drift = drift_boxes(room.fit, fitted, drawn, fit.drift_tolerance, DRIFT_MIN_PIECE)
        mapped = map_to_palette(room.mapping, fitted, f"edit frame {number} of {name}")
        empty = mapped[..., 3] == 0  # an edit has no alpha of its own: the room's stays
        mapped[empty] = room.composite[empty]
        if alpha is not None:
            past |= drawn & ~alpha & (mapped != room.composite).any(axis=2)
        frames.append(mapped[crop])
        found.append({"frame": number, "file": f"{variant}.png", "registration": registration,
                      "drift": [{"x": d.x, "y": d.y, "width": d.width, "height": d.height, "pixels": d.pixels}
                                for d in drift]})
    taken, outside = _hold_masks(run, name, region.shape, region)
    held = taken[crop] > 0
    stack = np.stack(frames)
    base = stack.copy()
    for number in range(1, len(frames)):
        for source in sorted(int(v) for v in np.unique(taken[crop]) if v):
            part = taken[crop] == source
            stack[number][part] = base[source][part]
    area = region[crop]
    last = len(frames) - 1
    pairs = [(a, a + 1) for a in range(1, last)] + ([(last, 1)] if last > 2 else [])
    flicker = [{"from": a, "to": b, "share": float(((stack[a] != stack[b]).any(axis=2) & area & ~held).sum() / max(1, int(area.sum())))}
               for a, b in pairs]
    holds = None
    if decisions_of(run, name, "hold"):
        # the held pixels as the build replays them, room size and 1-bit, so a screen shows them without drawing them again
        (run.output_dir / name).mkdir(parents=True, exist_ok=True)
        write_mask(run.output_dir / name / HOLD_FILE, (taken > 0) & region)
        holds = {"pixels": int((held & area).sum()), "outside": outside, "file": f"{name}/{HOLD_FILE}"}
    return stack, {"edits": found, "flicker": flicker, "past_layer": int(past.sum()), "holds": holds}


def _build_loop(run: StageRun, room: EditRoom, palette: Any, name: str, loop: dict[str, Any], cycle: dict[str, Any] | None,
                timing: dict[str, Any] | None, frame: dict[str, Any] | None = None) -> dict[str, Any]:
    shape = room.fit.shape[:2]
    layer = str(loop.get("layer", PLATE))
    framed = loop.get("form", "cycle") == "frames"
    picks = edit_picks(run, name) if framed else {}
    edits = framed and is_edits(frame, picks, kit_of(run, name))
    kit = kit_of(run, name) if framed and not edits and (frame is None or str(frame.get("source", "op")) == "kit") else None
    if framed and frame is None and kit is None and not edits:
        raise StageFailure(f"the Loop {name} is a frame Loop with no `frames` Decision")
    if framed and not edits and frame is not None and str(frame.get("source", "op")) == "kit" and kit is None:
        raise StageFailure(f"the Loop {name} takes its frames from a kit, and none is imported")
    op = str(frame.get("op")) if framed and frame is not None and kit is None and not edits else None
    mode = str(cycle.get("mode", "rotate")) if cycle is not None and not framed else ""
    colours = [str(c).lower() for c in cycle.get("colours", [])] if cycle is not None and not framed else []
    steps = (frame_count(cycle) if not framed else 1 + max(picks) if edits else
             1 + len(kit["frames"]) if kit is not None else frame_op_count(frame))
    assert framed or steps is not None
    region = paint_region(run, "loop", name, shape, room.fit, None)
    alphas = dict(room.layers)
    drawn = region.copy()  # before the Layer's alpha cuts it: what an edit frame may change and registration leaves out
    if layer != PLATE:
        if layer not in alphas:
            raise StageFailure(f"the Loop {name} sits on the Layer {layer}, which the room doesn't have")
        if op == "sway" and not decisions_of(run, name, "polygon", "brush", "flood"):
            region = alphas[layer].copy()  # no region drawn: a sway moves the whole Layer
        region &= alphas[layer]
    source = "edits" if edits else "kit" if kit is not None else (str(frame.get("source", "op")) if framed and frame else None)
    record: dict[str, Any] = {
        "id": name, "form": "frames" if framed else "cycle", "layer": layer, "light": loop.get("light"),
        "phase": int(loop.get("phase", 0)), "source": source,
        "op": op, "params": dict(frame.get("params", {})) if framed and frame and kit is None and not edits else None,
        "no_fill": False, "kit": None, "edits": [], "flicker": [], "holds": None, "past_layer": 0,
        "mode": mode or None, "colours": colours, "lift": None, "steps": steps, "emissive": None,
        "box": None, "frames": steps or 0, "columns": 0, "rows": 0, "plate": None, "layers": [], "index": None,
        "timing": {"ticks": EVEN_TICKS} if timing is None else {k: v for k, v in timing.items() if k != "loop"},
        "sequence": [], "ticks": 0, "pixels": int(region.sum()), "moving": 0, "seam": None, "seam_infinite": False,
        "flash": 0.0, "flash_fix": None, "pulse_spill": 0, "overlaps": [], "held": None,
    }
    if op == "sway" and layer == PLATE:
        record["no_fill"] = True  # the Plate has no fill under what a sway uncovers: `loop.no_fill`
        return record
    box = mask_box(region)
    if box is None:
        return record
    x, y, width, height = box
    if op == "sway":  # the sway's frames reach sideways beyond the region
        reach = math.ceil(float((frame or {}).get("params", {}).get("amplitude", SWAY_AMPLITUDE)))
        x0, x1 = max(0, x - reach), min(shape[1], x + width + reach)
        x, width = x0, x1 - x0
    crop = (slice(y, y + height), slice(x, x + width))
    image, area = room.composite[crop], region[crop]
    rgb = hex_rgb(colours)
    index = cycle_index(image, area, rgb) if len(colours) else None
    if framed and kit is not None:
        frames, found = _kit_frames(run, name, kit, palette, image, area, (x, y, width, height), layer != PLATE)
        steps = int(frames.shape[0])
        record["steps"] = record["frames"] = steps
        record["kit"] = {"box": [int(v) for v in kit["box"]], "frames": found, "remapped": palette_moved(run, kit)}
    elif edits:
        frames, built = _edit_frames(run, room, name, picks, drawn, region, layer, (x, y, width, height))
        steps = int(frames.shape[0])
        record["steps"] = record["frames"] = steps
        record.update(built)
    elif framed:
        assert frame is not None
        frames = _op_frames(run, name, frame, image, area, (x, y, width, height), y)
        steps = int(frames.shape[0])
        record["steps"] = record["frames"] = steps
    elif mode == "pulse":
        assert cycle is not None and steps is not None
        lift = float(cycle.get("lift", PULSE_LIFT))
        record["lift"], record["emissive"] = lift, bool(cycle.get("emissive", True))
        picked = (index > 0) & area if index is not None else area
        frames = cycle_pulse(image, picked, palette, lift, steps)
        if index is not None:
            record["pulse_spill"] = int((area & ~dilate(picked, PULSE_REACH)).sum())
    else:
        assert index is not None
        frames = cycle_rotate(image, index, rgb, steps)
    run.check_cancel()
    assert steps is not None
    try:
        sequence = sequence_of(timing, steps)
    except ValueError as error:
        raise StageFailure(f"the timing of {name}: {error}") from None
    record["sequence"] = [[int(f), int(t)] for f, t in sequence]
    record["ticks"] = sum(t for _, t in sequence)
    # what moves while the Loop plays: against frame 0, or with `rest` (frame 0 never played) among the played frames
    played = frames[sorted({int(f) for f, _ in sequence})] if (timing or {}).get("rest") else frames
    changed = (played != played[0]).any(axis=3).any(axis=0)
    record["moving"] = int((changed if op == "sway" else changed & area).sum())
    if framed and "flicker" not in (timing or {}):
        ratio = seam_ratio(frames, sequence)
    elif mode == "rotate" and "flicker" not in (timing or {}) and not (timing or {}).get("rest"):
        ratio = cycle_seam_ratio(rgb, bool((timing or {}).get("pingpong", False)))
    elif "flicker" in (timing or {}):
        ratio = 1.0  # a random sequence has no wrap to speak of
    else:
        ratio = seam_ratio(frames, sequence)
    record["seam"] = None if ratio == float("inf") else ratio
    record["seam_infinite"] = ratio == float("inf")
    screen = _screen_area(run)
    record["flash"] = flash_count(frames, sequence, int(area.sum()), screen)
    if record["flash"] > FLASH_PER_SECOND:
        for factor in SLOWER:
            slower = _slowed(timing or {"ticks": EVEN_TICKS}, factor)
            if flash_count(frames, sequence_of(slower, steps), int(area.sum()), screen) <= FLASH_PER_SECOND:
                record["flash_fix"] = factor
                break
    folder = run.output_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    covered = np.zeros(shape, dtype=np.bool_)
    parts: list[tuple[str | None, Any]] = []
    for layer_id, alpha in room.layers:
        covered |= alpha
        if layer == PLATE and (region & alpha).any():
            parts.append((layer_id, region & alpha))
    if layer != PLATE:
        parts = [(layer, region)]
    elif (region & ~covered).any():
        parts.insert(0, (None, region & ~covered))
    for piece, part in parts:
        run.check_cancel()
        cut = part[crop]
        tiles = list(frames) if op == "sway" else [cut_by_alpha(each, cut) for each in frames]  # a sway carries its alpha
        strip, record["columns"], record["rows"] = _strip(tiles)
        file = "plate.png" if piece is None else layer_file(piece)
        write_rgba(folder / file, strip)
        if piece is None:
            record["plate"] = f"{name}/{file}"
        else:
            record["layers"].append({"id": piece, "file": f"{name}/{file}"})
    if index is not None:
        Image.fromarray(index, "L").save(folder / "index.png", format="PNG")
        record["index"] = f"{name}/index.png"
    record["box"] = [x, y, width, height]
    record["overlaps"] = _look_overlaps(run, region)
    return record


def _held_record(run: StageRun, room: EditRoom, name: str, loop: dict[str, Any], why: NeedsInput) -> dict[str, Any]:
    """A held Loop as `loops.json` lists it: its region (`<loop>/region.png`, room size, 1-bit; cut to its Layer's alpha when
    the room has that Layer) and `box`, the reason in `held`, and no frames."""
    layer = str(loop.get("layer", PLATE))
    shape = room.fit.shape[:2]
    try:
        region = paint_region(run, "loop", name, shape, room.fit, None)
    except StageFailure:
        region = np.zeros(shape, dtype=np.bool_)  # a flood that can't be measured: nothing to show yet
    alphas = dict(room.layers)
    if layer != PLATE and layer in alphas:
        region &= alphas[layer]
    box = mask_box(region)
    if box is not None:
        folder = run.output_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        write_mask(folder / REGION_FILE, region)
    return {
        "id": name, "form": str(loop.get("form", "cycle")), "layer": layer, "light": loop.get("light"),
        "phase": int(loop.get("phase", 0)), "source": None, "op": None, "params": None, "no_fill": False, "kit": None,
        "edits": [], "flicker": [], "holds": None, "past_layer": 0, "mode": None, "colours": [], "lift": None, "steps": None, "emissive": None,
        "box": None if box is None else [int(v) for v in box], "frames": 0, "columns": 0, "rows": 0, "plate": None,
        "layers": [], "index": None, "timing": {}, "sequence": [], "ticks": 0, "pixels": int(region.sum()), "moving": 0,
        "seam": None, "seam_infinite": False, "flash": 0.0, "flash_fix": None, "pulse_spill": 0, "overlaps": [],
        "region": None if box is None else f"{name}/{REGION_FILE}",
        "held": why.reason, "held_fix": why.command, "held_owner_action": why.owner_action,
    }


def run_loops(run: StageRun) -> None:
    loops = declared(run)
    built: list[dict[str, Any]] = []
    if loops:
        room = EditRoom(run)
        palette = palette_rgb(run)
        held = held_loops(run)
        cycles, timings, frame_sources = _latest(run, "cycle"), _latest(run, "timing"), _latest(run, "frames")
        for index, name in enumerate(sorted(loops)):
            run.check_cancel()
            run.progress(index, len(loops), f"Loop {name}")
            if name in held:
                built.append(_held_record(run, room, name, loops[name], held[name]))
                continue
            built.append(_build_loop(run, room, palette, name, loops[name], cycles.get(name), timings.get(name),
                                     frame_sources.get(name)))
        run.progress(len(loops), len(loops), "Loops")
        if held:
            run.notes.append(f"held {len(held)} Loop{'s' if len(held) > 1 else ''}: {', '.join(sorted(held))}")
    document = {"schema_version": LOOPS_SCHEMA_VERSION, "loops": built}
    (run.output_dir / LOOPS_FILE).write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")


# the Checks


def read_loops(folder: Path, asset: str) -> list[dict[str, Any]]:
    """The Loops a built `loops.json` in `folder` lists, in order. An older file is refused, naming the rebuild."""
    built = json.loads((folder / LOOPS_FILE).read_text(encoding="utf-8"))
    if built.get("schema_version") != LOOPS_SCHEMA_VERSION:
        raise StageFailure(f"{LOOPS_FILE} has schema_version {built.get('schema_version')}; this Kiripix reads "
                           f"{LOOPS_SCHEMA_VERSION}. Rebuild it: kiripix run {asset} {LOOPS_STAGE} --force")
    listed: list[dict[str, Any]] = built["loops"]
    return listed


def piece_files(loop: dict[str, Any]) -> list[str]:
    return ([str(loop["plate"])] if loop["plate"] else []) + [str(e["file"]) for e in loop["layers"]]


def _decide(asset: str, data: dict[str, Any]) -> str:
    return f"kiripix decide {asset} {LOOPS_STAGE} --decision '{json.dumps({'decision': 'timing', 'data': data})}'"


def _kit_findings(asset: str, name: str, loop: dict[str, Any]) -> list[Finding]:
    """What the build found in a kit's frames: near-miss colours, strokes outside the region, partial alpha."""
    findings: list[Finding] = []
    if not loop.get("kit"):
        return findings
    import_again = (f"Paint it again on the palette's colours and import it (kiripix import {asset} <png...> --loop {name}).")
    for entry in loop["kit"]["frames"]:
        number, file = int(entry["frame"]), str(entry["file"])
        where = Position(asset=asset, stage=LOOPS_STAGE, file=file)
        if entry["off_palette"]:
            share = entry["off_palette"] / max(1, entry["region_pixels"])
            px, py = entry["first_off_palette"]
            findings.append(Finding(
                code="loop.off_palette", severity="error" if share > KIT_OFF_PALETTE_ERROR else "warning",
                message=f"kit frame {number} of {name} has {entry['off_palette']} pixels off the palette ({share:.1%} of "
                        f"its region), the first at ({px}, {py}); each took the nearest palette colour",
                position=Position(asset=asset, stage=LOOPS_STAGE, file=file, x=px, y=py),
                owner_action=import_again))
        if entry["partial_alpha"]:
            findings.append(Finding(
                code="loop.partial_alpha",
                message=f"kit frame {number} of {name} has {entry['partial_alpha']} partly transparent pixels; below half "
                        "opacity they are taken as empty, the rest as opaque",
                position=where, owner_action="Paint with a hard-edged tool: alpha is 0 or 255. " + import_again))
        for x, y, w, h in entry["outside"]:
            findings.append(Finding(
                code="loop.outside_region", severity="warning",
                message=f"kit frame {number} of {name} changes the room outside the Loop's region, at {w}x{h} px from "
                        f"({x}, {y}); it is cut away",
                position=Position(asset=asset, stage=LOOPS_STAGE, file=file, x=x, y=y, width=w, height=h),
                owner_action=f"Keep the strokes inside the region, or widen the region (kiripix decide {asset} "
                             f"{LOOPS_STAGE} --help) and write a new kit."))
    return findings


def _edit_findings(asset: str, name: str, loop: dict[str, Any], box: Position) -> list[Finding]:
    """What the build found in an edit-frame Loop: a misaligned or drifting frame, a boiling region, change past the
    Layer, a hold past the region. Each frame's finding sits at `field` `loop.<id>.frame.<n>`."""
    found: list[Finding] = []
    again = f"kiripix import {asset} <png> --loop {name} --frame"

    def at(number: int, x: int | None = None, y: int | None = None, width: int | None = None,
           height: int | None = None) -> Position:
        return Position(asset=asset, stage=LOOPS_STAGE, field=f"loop.{name}.frame.{number}", x=x, y=y, width=width,
                        height=height)

    for entry in loop.get("edits", []):
        number = int(entry["frame"])
        registration = entry.get("registration")
        if registration and registration["problems"]:
            found.append(Finding(
                code="loop.misaligned",
                message=f"the edit of frame {number} of {name} doesn't lie on the Source: " + "; ".join(registration["problems"]),
                position=at(number),
                owner_action=f"Make the edit again so it keeps the Source's size and framing ({again} {number}, then pick "
                             "it), or paint the frames by hand on a kit."))
        drift = entry["drift"]
        if drift:
            total = sum(int(d["pixels"]) for d in drift)
            first = drift[0]
            found.append(Finding(
                code="loop.drift", severity="warning",
                message=f"the edit of frame {number} of {name} redrew {total} px in {len(drift)} places outside the Loop's "
                        f"region, the largest {first['width']}x{first['height']} at ({first['x']}, {first['y']}); it is "
                        "never shown",
                position=at(number, x=int(first["x"]), y=int(first["y"]), width=int(first["width"]), height=int(first["height"])),
                owner_action="If the redraw belongs to the Loop, grow its region over it (kiripix decide "
                             f"{asset} {LOOPS_STAGE} --help); if not, it is the model's noise outside the Loop."))
    for pair in loop.get("flicker", []):
        if float(pair["share"]) > FLICKER_SHARE:
            found.append(Finding(
                code="loop.flicker", severity="warning",
                message=f"between edit frames {pair['from']} and {pair['to']} of {name}, {float(pair['share']):.0%} of the "
                        f"region redraws, over {FLICKER_SHARE:.0%}: the picture boils",
                position=at(int(pair["to"]), x=box.x, y=box.y, width=box.width, height=box.height),
                owner_action="Hold the part that should stay still from one frame (a `hold` Decision over it: kiripix decide "
                             f"{asset} {LOOPS_STAGE} --help), or paint the moving part on a kit. A region that changes this "
                             "much on purpose, a screen cutting between shots, keeps the warning."))
    if loop.get("past_layer"):
        found.append(Finding(
            code="loop.past_layer", severity="warning",
            message=f"the edit frames of {name} change {loop['past_layer']} px outside the Layer {loop['layer']}, where they "
                    "are cut away",
            position=box,
            owner_action=f"Keep the edit inside the Layer, or put the Loop on the Plate (kiripix decide {asset} {LOOPS_STAGE} "
                         "--help)."))
    holds = loop.get("holds")
    if holds and holds["outside"]:
        found.append(Finding(
            code="loop.hold_outside_region", severity="info",
            message=f"a `hold` of {name} covers {holds['outside']} px outside the Loop's region; they are cut away",
            position=box, owner_action="Draw the hold inside the region, or leave it: only the part inside is held."))
    return found


def check_loops(run: StageRun) -> list[Finding]:
    asset = run.asset_id
    findings: list[Finding] = []
    loops = read_loops(run.output_dir, asset)
    try:
        palette: Any | None = palette_rgb(run)
    except StageFailure:
        palette = None  # the palette's own Checks report it
    composite = read_rgba(run.upstream["palette"] / "palette.png") if loops else None
    total_frames = total_bytes = 0
    for loop in loops:
        name = str(loop["id"])
        where = Position(asset=asset, stage=LOOPS_STAGE)
        timing = {"loop": name, **loop["timing"]}
        if loop.get("held"):
            at = Position(asset=asset, stage=LOOPS_STAGE, field=f"loop.{name}")
            if loop["box"] is not None:
                at.x, at.y, at.width, at.height = (int(v) for v in loop["box"])
            findings.append(Finding(
                code="loop.held", message=f"the Loop {name} is held, and plays nothing until this is settled: {loop['held']}",
                position=at, fix=loop.get("held_fix"),
                owner_action=None if loop.get("held_fix") else loop.get("held_owner_action")))
            continue
        if loop.get("no_fill"):
            findings.append(Finding(
                code="loop.no_fill", message=f"the Loop {name} sways the Plate, which has no fill for what it uncovers",
                position=where,
                owner_action=f"Lift the object onto its own Layer (a `layers` Decision: kiripix decide {asset} layers "
                             f"--help), then declare {name} on that Layer."))
            continue
        if loop["box"] is None:
            findings.append(Finding(
                code="loop.no_region", severity="warning",
                message=f"the Loop {name} has no region, so it plays nothing", position=where,
                owner_action=f"Mark where {name} plays: a flood, a polygon or a brush "
                             f"(kiripix decide {asset} {LOOPS_STAGE} --help)."))
            continue
        x, y, width, height = (int(v) for v in loop["box"])
        box = Position(asset=asset, stage=LOOPS_STAGE, x=x, y=y, width=width, height=height)
        total_frames += int(loop["frames"])
        for file in piece_files(loop) + ([str(loop["index"])] if loop["index"] else []):
            total_bytes += (run.output_dir / file).stat().st_size
        if palette is not None:
            palette_hex = {hex_of(c) for c in palette}
            off = [c for c in loop["colours"] if c not in palette_hex]
            if off:
                findings.append(Finding(
                    code="loop.off_palette",
                    message=f"the cycle of {name} lists {', '.join(off)}, which the palette doesn't have",
                    position=where,
                    owner_action=f"Use palette colours in the cycle (kiripix decide {asset} {LOOPS_STAGE} --help), or "
                                 "add the colours to the palette."))
            for file in piece_files(loop):
                report = conformance(read_rgba(run.output_dir / file), palette)
                for finding in check_alpha(report, file):
                    assert finding.position is not None
                    finding.position.asset, finding.position.stage, finding.position.file = asset, LOOPS_STAGE, file
                    findings.append(finding)
                if report.off_palette:
                    px, py = report.first_off_palette[0]
                    findings.append(Finding(
                        code="loop.off_palette",
                        message=f"{file} has {report.off_palette} pixels off the palette, the first at ({px}, {py})",
                        position=Position(asset=asset, stage=LOOPS_STAGE, file=file, x=px, y=py),
                        fix=f"kiripix run {asset} {LOOPS_STAGE} --force"))
        assert composite is not None
        for file in piece_files(loop):
            tile = read_rgba(run.output_dir / file)[:height, :width]
            seen = tile[..., 3] > 0
            room = composite[y:y + height, x:x + width]
            if room.shape != tile.shape:  # the palette image changed (by hand, or not yet rebuilt): nothing to compare
                findings.append(Finding(
                    code="loop.stale_size",
                    message=f"the region of {name} ({width}x{height} at {x}, {y}) doesn't fit the palette image, "
                            f"{composite.shape[1]}x{composite.shape[0]}: the Loop was built from another one",
                    position=box, fix=f"kiripix run {asset} {LOOPS_STAGE} --force"))
                break
            wrong = seen & (tile != room).any(axis=2)
            if wrong.any():
                py, px = (int(v) for v in np.argwhere(wrong)[0])
                findings.append(Finding(
                    code="loop.frame0",
                    message=f"frame 0 of {file} differs from the room at {int(wrong.sum())} pixels, the first at "
                            f"({x + px}, {y + py})",
                    position=Position(asset=asset, stage=LOOPS_STAGE, file=file, x=x + px, y=y + py),
                    fix=f"kiripix run {asset} {LOOPS_STAGE} --force"))
        findings.extend(_kit_findings(asset, name, loop))
        findings.extend(_edit_findings(asset, name, loop, box))
        if not loop["moving"]:
            findings.append(Finding(
                code="loop.still", severity="warning",
                message=(f"the played frames of the Loop {name} are all the same: it shows one still picture"
                         if loop["timing"].get("rest") else
                         f"no frame of the Loop {name} differs from frame 0: it shows the room as it is"), position=box,
                owner_action=f"Check that the region holds pixels of the cycle's colours, and that the colours are "
                             f"the ones in the room (kiripix decide {asset} {LOOPS_STAGE} --help)."))
        if loop["seam_infinite"] or (loop["seam"] is not None and loop["seam"] > SEAM_LIMIT):
            ratio = "an unbounded" if loop["seam_infinite"] else f"{loop['seam']:.1f} times the"
            findings.append(Finding(
                code="loop.seam", severity="warning",
                message=f"the wrap of the Loop {name} is {ratio} step of its other frames: it jumps when it repeats",
                position=box, fix=_decide(asset, {**timing, "pingpong": True})))
        if loop["flash"] > FLASH_PER_SECOND:
            message = (f"the Loop {name} flashes {loop['flash']:g} times a second over {loop['pixels']} px, over "
                       f"{FLASH_PER_SECOND} (WCAG 2.3.1)")
            if loop["flash_fix"]:
                findings.append(Finding(code="loop.flash", message=message, position=box,
                                        fix=_decide(asset, _slowed(timing, int(loop["flash_fix"])))))
            else:
                findings.append(Finding(
                    code="loop.flash", message=message, position=box,
                    owner_action="Slowing it isn't enough: use a smaller region, or colours that differ less in "
                                 "lightness."))
        for overlap in loop["overlaps"]:
            findings.append(Finding(
                code="loop.overlaps_look", severity="warning",
                message=f"the Loop {name} and the Look {overlap['look']} share {overlap['pixels']} px: while the Look "
                        "shows, the Loop plays under it or over it as the game draws them",
                position=box,
                owner_action=f"Cut one of the regions back (kiripix decide {asset} {LOOPS_STAGE} --help)."))
        if loop["pulse_spill"]:
            findings.append(Finding(
                code="loop.pulse_spills", severity="info",
                message=f"the pulse of {name} has {loop['pulse_spill']} px of region more than {PULSE_REACH} px from the "
                        "pixels of its colours; they don't pulse",
                position=box,
                owner_action="Tighten the region round the pulsing colours, or leave it: the extra pixels stay as "
                             "they are."))
    if loops:
        findings.append(Finding(
            code="loop.texture", severity="info",
            message=f"the room's Loops hold {total_frames} frames in {total_bytes} bytes of PNG",
            position=Position(asset=asset, stage=LOOPS_STAGE),
            owner_action="Nothing to do; this is the texture memory the Loops add."))
    return findings
