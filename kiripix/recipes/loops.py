"""The room's `loops` Stage (ticket 0189, ADR 0009's sibling for things that always play): colour cycles.

A Loop is a part of the room that plays by itself, over and over, cut to a region. Where a Look is shown by game state
and cut from an edit, a Loop needs no edit here: a colour cycle steps chosen palette colours through a list inside the
region, on the room's own mapped pixels. Its first frame is the room, pixel for pixel. A character clip's `loop` flag
is something else.

Decisions, in target pixels, each naming its Loop in `loop`:

- `loop`: the Loop's ID, `form` (`cycle` or `frames`), `layer` (`plate`
  or a foreground Layer's ID), `light` (a light Marker's ID, optional) and `phase` (ticks);
- the region: `polygon`, `brush`, `flood` and `difference` (`regions`, shared with `looks`);
- `cycle`: `colours` (hex, on the palette), `mode` `rotate` or `pulse` (with `depth` and `steps`) and, for a pulse, the
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
    even_sequence,
    flash_count,
    flicker_sequence,
    mask_box,
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
    PULSE_DEPTH,
    PULSE_STEPS,
)
from kiripix.recipes.base import CheckSpec, CurrentDecision, DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.common import box_problem, palette_rgb, read_grid, read_rgba, write_rgba
from kiripix.recipes.kit_record import KIT_DECISION, frame_path, kit_command, kit_needs_input, kit_of, palette_moved
from kiripix.recipes.layers import LAYERS_FILE, layer_file, read_layers
from kiripix.recipes.looks import read_looks
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
)
from kiripix.recipes.regions import decisions_of as _decisions_of

LOOPS_STAGE = "loops"
LOOPS_FILE = "loops.json"
LOOPS_SCHEMA_VERSION = 1
PLATE = "plate"  # a Loop's `layer` when it sits on the Plate
STRIP_WIDTH = 4096  # px: a strip wraps into rows past this
SEAM_LIMIT = 3.0  # `loop.seam` warns over this ratio (confirmed by 0184: its Loops measured 0.94 to 1.6)
PULSE_REACH = 2  # px: a pulse region beyond this from the pixels of its picked colours is `loop.pulse_spills` (kept: 0184 didn't measure it)
KIT_OFF_PALETTE_ERROR = 0.01  # a kit frame with more than this share of its region off the palette is an error (kept)
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
                    "follows the Loop) and its `phase` in ticks (default 0). The latest Decision of a Loop counts. "
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
                    "`steps` frames (default: one per colour). `pulse` moves each region pixel up to `depth` places "
                    f"lighter along its own colour ramp and back, over `steps` frames (defaults {PULSE_DEPTH} and "
                    f"{PULSE_STEPS}); `colours` then limits the pulse to the pixels of those colours, and is optional. "
                    "`emissive` (default true, pulse only) tells the game that the pulse lights what is around it. "
                    "Frame 0 is the room's own pixels. The latest Decision of a Loop counts.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "colours": {"type": "array", "items": {"type": "string", "pattern": HEX}, "uniqueItems": True},
                "mode": {"enum": ["rotate", "pulse"]},
                "depth": {"type": "integer", "minimum": 1},
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
    if data.get("source", "op") == "kit":
        return None  # held back by the Stage until ticket 0194
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
                    "the Plate's fill. A Loop with no `frames` Decision and an imported kit is the same. The latest "
                    "Decision of a Loop counts.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "source": {"enum": ["op", "kit"]},
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
                    "The latest Decision of a Loop counts.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": LOOP_PROPERTY,
                "ticks": {"oneOf": [ticks, {"type": "array", "items": ticks, "minItems": 1}]},
                "pingpong": {"type": "boolean"},
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


DECISIONS = (
    _loop_decision(),
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
    _timing_decision(),
)

CHECKS = (
    CheckSpec(code="loop.off_palette", description="Every pixel of a Loop's strips, and each colour of its cycle, is a "
                                                   "palette colour."),
    CheckSpec(code="loop.outside_region", description="A kit frame changes the room only inside the Loop's region; what it "
                                                       "changes outside is cut away (warning, one per patch)."),
    CheckSpec(code="loop.partial_alpha", description="A kit frame's alpha is 0 or 255."),
    CheckSpec(code="loop.frame0",description="Frame 0 of a Loop's strips is the room inside its region, pixel for pixel."),
    CheckSpec(code="loop.seam", description=f"The loop's wrap is no rougher than {SEAM_LIMIT:g} times the change "
                                            "between its other frames (warning)."),
    CheckSpec(code="loop.still", description="A Loop's frames differ from frame 0 somewhere (warning)."),
    CheckSpec(code="loop.flash", description=f"A Loop flashes no more than {FLASH_PER_SECOND} times a second "
                                             "(WCAG 2.3.1)."),
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
    ids = list(range(frames))
    if "flicker" in timing:
        flicker = timing["flicker"]
        return flicker_sequence(int(flicker["seed"]), ids, int(flicker.get("mean_ticks", FLICKER_MEAN_TICKS)),
                                float(flicker.get("spread", FLICKER_SPREAD)),
                                int(flicker.get("length_ticks", FLICKER_LENGTH_TICKS)))
    ticks = timing.get("ticks", EVEN_TICKS)
    order = even_sequence(ids, 1, bool(timing.get("pingpong", False)))
    if isinstance(ticks, list):
        if len(ticks) != frames:
            raise ValueError(f"ticks lists {len(ticks)} numbers for {frames} frames")
        return [(frame, int(ticks[frame])) for frame, _ in order]
    return [(frame, int(ticks)) for frame, _ in order]


def _layer_ids(run: StageRun) -> list[str] | None:
    folder = run.upstream.get("layers")
    if folder is None or not (folder / LAYERS_FILE).is_file():
        return None
    try:
        return [str(entry["id"]) for entry in read_layers(folder, run.asset_id)]
    except StageFailure:
        return None


def _look_ids(run: StageRun) -> set[str]:
    return {str(d.data["look"]) for d in run.upstream_decisions.get(LOOKS_STAGE, ())}


def is_kit(frame: dict[str, Any] | None, kit: dict[str, Any] | None) -> bool:
    """Whether a frame Loop takes its frames from its kit: a `frames` Decision with source kit, or, with no `frames`
    Decision, an imported kit."""
    if frame is None:
        return kit is not None
    return str(frame.get("source", "op")) == "kit"


def _frames_needs_input(run: StageRun, name: str, frame: dict[str, Any] | None,
                        timing: dict[str, Any] | None) -> NeedsInput | None:
    asset = run.asset_id
    undo = f"kiripix undo {asset} {LOOPS_STAGE}"
    kept = kit_needs_input(run, name)  # no frames at all: `next` suggests `loop kit`; a kit painted on another fit (0193)
    if kept is not None:
        return kept
    kit = kit_of(run, name)
    if frame is None and kit is None:
        return NeedsInput(f"the Loop {name} is a frame Loop with no `frames` Decision",
                          owner_action=f"Say where its frames come from (kiripix decide {asset} {LOOPS_STAGE} --help, "
                                       "the `frames` Decision).")
    if is_kit(frame, kit) and kit is None:
        return NeedsInput(f"the Loop {name} takes its frames from a kit, and none is imported",
                          command=kit_command(asset, name))
    if decisions_of(run, name, "difference"):
        return NeedsInput(f"the Loop {name} builds its frames by an Op or a kit, and a `difference` compares an edit with "
                          "the room",
                          owner_action=f"Undo it ({undo}) and mark the region with a flood, a polygon or a brush.")
    try:
        count = 1 + len(kit["frames"]) if is_kit(frame, kit) and kit is not None else frame_op_count(frame)
        if count is not None:
            sequence_of(timing, count)
    except ValueError as error:
        return NeedsInput(f"the timing of {name}: {error}",
                          owner_action=f"Give one number per frame, or a single number ({undo}).")
    return None


def loops_needs_input(run: StageRun) -> NeedsInput | None:
    asset = run.asset_id
    undo = f"kiripix undo {asset} {LOOPS_STAGE}"
    loops = declared(run)
    cycles, timings, frames = _latest(run, "cycle"), _latest(run, "timing"), _latest(run, "frames")
    for decision in run.decisions:
        name = str(decision.data["loop"])
        if name not in loops:
            return NeedsInput(f"the Decision {decision.name} names the Loop {name}, which is not declared",
                              owner_action=f"Declare it first (kiripix decide {asset} {LOOPS_STAGE} --decision "
                                           f"'{{\"decision\": \"loop\", \"data\": {{\"loop\": \"{name}\"}}}}'), or undo: {undo}.")
    clash = sorted(set(loops) & _look_ids(run))
    if clash:
        return NeedsInput(f"the Loop {clash[0]} has the ID of a Look",
                          owner_action=f"A Look's and a Loop's IDs are one set. Give the Loop another ID: undo its "
                                       f"Decisions ({undo}) and declare it again.")
    layers = _layer_ids(run)
    read = read_grid(run)
    for name, loop in sorted(loops.items()):
        layer = str(loop.get("layer", PLATE))
        if layer != PLATE and layers is not None and layer not in layers:
            return NeedsInput(f"the Loop {name} sits on the Layer {layer}, which the room doesn't have",
                              owner_action=f"Declare the Loop again on the Plate or on one of "
                                           f"{', '.join(layers) or 'no Layers'} (kiripix decide {asset} {LOOPS_STAGE} --help).")
        if loop.get("form", "cycle") == "frames":
            held = _frames_needs_input(run, name, frames.get(name), timings.get(name))
            if held is not None:
                return held
            continue
        if name in frames:
            return NeedsInput(f"the Loop {name} is a cycle, and a `frames` Decision gives a frame Loop its frames",
                              owner_action=f"Declare the Loop again with form frames, or undo the Decision ({undo}).")
        cycle = cycles.get(name)
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
            sequence_of(timings.get(name), int(frame_count(cycle) or 0))
        except ValueError as error:
            return NeedsInput(f"the timing of {name}: {error}",
                              owner_action=f"Give one number per frame, or a single number ({undo}).")
        if decisions_of(run, name, "difference"):
            return NeedsInput(f"the Loop {name} is a cycle, and a `difference` compares an edit with the room",
                              owner_action=f"Undo it ({undo}) and mark the region with a flood, a polygon or a brush.")
    if read is not None:
        for decision in run.decisions:
            if decision.name == "difference":
                box = decision_box(decision)
                problem = box_problem(box, read[0].width, read[0].height, read[0].pad_right, read[0].pad_bottom)
                if problem is not None:
                    return NeedsInput(f"the difference box of {decision.data['loop']} {problem}",
                                      owner_action=f"Undo it: {undo}.")
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
        image = read_rgba(run.asset_dir / frame_path(name, str(stored)))
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


def _build_loop(run: StageRun, room: EditRoom, palette: Any, name: str, loop: dict[str, Any], cycle: dict[str, Any] | None,
                timing: dict[str, Any] | None, frame: dict[str, Any] | None = None) -> dict[str, Any]:
    shape = room.fit.shape[:2]
    layer = str(loop.get("layer", PLATE))
    framed = loop.get("form", "cycle") == "frames"
    kit = kit_of(run, name) if framed and (frame is None or str(frame.get("source", "op")) == "kit") else None
    if framed and frame is None and kit is None:
        raise StageFailure(f"the Loop {name} is a frame Loop with no `frames` Decision")
    if framed and frame is not None and str(frame.get("source", "op")) == "kit" and kit is None:
        raise StageFailure(f"the Loop {name} takes its frames from a kit, and none is imported")
    op = str(frame.get("op")) if framed and frame is not None and kit is None else None
    mode = str(cycle.get("mode", "rotate")) if cycle is not None and not framed else ""
    colours = [str(c).lower() for c in cycle.get("colours", [])] if cycle is not None and not framed else []
    steps = frame_count(cycle) if not framed else (1 + len(kit["frames"]) if kit is not None else frame_op_count(frame))
    assert framed or steps is not None
    region = paint_region(run, "loop", name, shape, room.fit, None)
    alphas = dict(room.layers)
    if layer != PLATE:
        if layer not in alphas:
            raise StageFailure(f"the Loop {name} sits on the Layer {layer}, which the room doesn't have")
        if op == "sway" and not decisions_of(run, name, "polygon", "brush", "flood"):
            region = alphas[layer].copy()  # no region drawn: a sway moves the whole Layer
        region &= alphas[layer]
    source = "kit" if kit is not None else (str(frame.get("source", "op")) if framed and frame else None)
    record: dict[str, Any] = {
        "id": name, "form": "frames" if framed else "cycle", "layer": layer, "light": loop.get("light"),
        "phase": int(loop.get("phase", 0)), "source": source,
        "op": op, "params": dict(frame.get("params", {})) if framed and frame and kit is None else None, "no_fill": False,
        "kit": None,
        "mode": mode or None, "colours": colours, "depth": None, "steps": steps, "emissive": None,
        "box": None, "frames": steps or 0, "columns": 0, "rows": 0, "plate": None, "layers": [], "index": None,
        "timing": {"ticks": EVEN_TICKS} if timing is None else {k: v for k, v in timing.items() if k != "loop"},
        "sequence": [], "ticks": 0, "pixels": int(region.sum()), "moving": 0, "seam": None, "seam_infinite": False,
        "flash": 0.0, "flash_fix": None, "pulse_spill": 0, "overlaps": [],
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
    elif framed:
        assert frame is not None
        frames = _op_frames(run, name, frame, image, area, (x, y, width, height), y)
        steps = int(frames.shape[0])
        record["steps"] = record["frames"] = steps
    elif mode == "pulse":
        assert cycle is not None and steps is not None
        depth = int(cycle.get("depth", PULSE_DEPTH))
        record["depth"], record["emissive"] = depth, bool(cycle.get("emissive", True))
        picked = (index > 0) & area if index is not None else area
        frames = cycle_pulse(image, picked, palette, depth, steps)
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
    changed = (frames != frames[0]).any(axis=3).any(axis=0)
    record["moving"] = int((changed if op == "sway" else changed & area).sum())
    if framed and "flicker" not in (timing or {}):
        ratio = seam_ratio(frames, sequence)
    elif mode == "rotate" and "flicker" not in (timing or {}):
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


def run_loops(run: StageRun) -> None:
    loops = declared(run)
    built: list[dict[str, Any]] = []
    if loops:
        room = EditRoom(run)
        palette = palette_rgb(run)
        cycles, timings, frame_sources = _latest(run, "cycle"), _latest(run, "timing"), _latest(run, "frames")
        for index, name in enumerate(sorted(loops)):
            run.check_cancel()
            run.progress(index, len(loops), f"Loop {name}")
            built.append(_build_loop(run, room, palette, name, loops[name], cycles.get(name), timings.get(name),
                                     frame_sources.get(name)))
        run.progress(len(loops), len(loops), "Loops")
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
        if not loop["moving"]:
            findings.append(Finding(
                code="loop.still", severity="warning",
                message=f"no frame of the Loop {name} differs from frame 0: it shows the room as it is", position=box,
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
