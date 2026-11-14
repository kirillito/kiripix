"""A frame Loop's kit, as the `loops` Stage sees it (ticket 0193, route (c) of 0183).

A kit is a folder of PNGs the Owner paints at target size, one per frame of a Loop's region box (`kiripix loop kit`).
`kiripix import <asset> <png...> --loop <loop>` stores frames 1 to N-1 as `src/loops/<loop>/<hash>.png` and records a `kit`
Decision in the `loops` journal:

    {"loop": "neon", "box": [x, y, w, h], "frames": ["<hash>", ...], "fit": "<hash>", "palette": "<hash>"}

`frames` are the stored frames' names, in order, for frames 1 to N-1 (frame 0 is always the room's). `fit` is the hash of
the fitted room (`fit.png`) and `palette` the hash of the palette's colours, both as the frames were painted on them.
The latest `kit` Decision of a Loop counts.

- A refit changes `fit.png`: the kit is `needs-input` ("painted on another fit"), because the frames no longer sit on
  the room's pixels.
- A palette change keeps the kit: ticket 0194 remaps the frames to the new palette (`needs-review`). `palette_moved` is
  what it asks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.ops import mask_box
from kiripix.recipes.base import CurrentDecision, DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.common import palette_rgb
from kiripix.recipes.regions import OWNER_ID, EditRoom, paint_region
from kiripix.recipes.regions import decisions_of as _decisions_of

KIT_DIR = "src/loops"  # in the Asset folder: `src/loops/<loop>/<hash>.png`
KIT_GLOB = f"{KIT_DIR}/**/*.png"
HASH_LENGTH = 16  # hex digits, as a Variant's name
HASH = f"^[0-9a-f]{{{HASH_LENGTH}}}$"
KIT_COMMAND = "kiripix loop kit"
KIT_FRAMES = 4  # the frame count `next` suggests


def _kit_decision() -> DecisionSpec:
    integer: dict[str, Any] = {"type": "integer", "minimum": 0}
    return DecisionSpec(
        name="kit",
        description="The frames painted on a Loop's kit, as `kiripix import <asset> <png...> --loop <loop>` records them: "
                    "`box` ([x, y, w, h] in target px, the region's box the frames fill), `frames` (the stored frames' "
                    "names, for frames 1 to N-1: frame 0 is always the room's), `fit` (the hash of the fitted room they "
                    "were painted on) and `palette` (the hash of the palette's colours). A refit puts them in "
                    "needs-input; a palette change keeps them, and they are remapped. `remap` (optional) is true once the "
                    "Owner has accepted that remap (`accept` re-records the kit on the new palette): the frames stay as "
                    "painted and are remapped on every build, not reported off the palette. Written by `import` and "
                    "`accept`, not by hand. "
                    "The latest Decision of a Loop counts.",
        entry_schema={
            "type": "object",
            "properties": {
                "loop": {"type": "string", "pattern": OWNER_ID},
                "box": {"type": "array", "items": integer, "minItems": 4, "maxItems": 4},
                "frames": {"type": "array", "items": {"type": "string", "pattern": HASH}, "minItems": 1},
                "fit": {"type": "string", "pattern": HASH},
                "palette": {"type": "string", "pattern": HASH},
                "remap": {"type": "boolean"},
            },
            "required": ["loop", "box", "frames", "fit", "palette"],
            "additionalProperties": False,
        },
    )


KIT_DECISION = _kit_decision()


# what a kit was painted on


def fit_hash(fit_png: Path) -> str:
    """The identity of the fitted room: the start of the hash of `fit.png`'s bytes."""
    return hashlib.sha256(fit_png.read_bytes()).hexdigest()[:HASH_LENGTH]


def palette_hash(rgb: Any) -> str:
    """The identity of a palette: its colours, sorted (their order doesn't matter to a painted frame)."""
    colours = sorted({(int(r), int(g), int(b)) for r, g, b in np.asarray(rgb).reshape(-1, 3)})
    return hashlib.sha256(bytes(v for colour in colours for v in colour)).hexdigest()[:HASH_LENGTH]


def frame_name(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:HASH_LENGTH]


def frame_path(loop: str, name: str) -> str:
    """A stored frame, relative to the Asset folder (the key of `StageRun.files`)."""
    return f"{KIT_DIR}/{loop}/{name}.png"


# reading the record


def kit_of(run: StageRun, loop: str) -> dict[str, Any] | None:
    """The Loop's latest `kit` Decision's data, or None."""
    found: list[CurrentDecision] = _decisions_of(run, "loop", loop, "kit")
    return dict(found[-1].data) if found else None


def palette_moved(run: StageRun, kit: dict[str, Any]) -> bool:
    """Whether the kit's frames are remapped to the palette rather than checked against it: the palette differs from
    the one the kit was recorded on, or the Owner accepted an earlier remap (`remap`; the frames are still as painted)."""
    return bool(kit.get("remap")) or palette_hash(palette_rgb(run)) != str(kit["palette"])


def kits_moved(run: StageRun) -> list[tuple[CurrentDecision, dict[str, Any]]]:
    """For `StageSpec.review`: each Loop's latest `kit` Decision painted on another palette than the current one, with
    its data re-recorded on the current palette, with `remap` so the next build keeps remapping the frames as painted
    rather than reporting them off the palette. A kit the Loop no longer takes its frames from is left alone."""
    try:
        current = palette_hash(palette_rgb(run))
    except StageFailure:
        return []
    latest: dict[str, CurrentDecision] = {}
    for decision in run.decisions:
        if decision.name == "kit":
            latest[str(decision.data["loop"])] = decision
    moved = []
    for loop, decision in sorted(latest.items()):
        chosen = _decisions_of(run, "loop", loop, "frames")
        if chosen and chosen[-1].data.get("source") != "kit":
            continue  # the frames come from an Op or edits: the kit isn't built, so nothing was remapped
        if str(decision.data["palette"]) != current:
            moved.append((decision, {**decision.data, "palette": current, "remap": True}))
    return moved


KIT_REVIEW_REASON = "the palette changed since a kit was painted: its frames were remapped to the new palette"


def kit_command(asset: str, loop: str, frames: int = KIT_FRAMES) -> str:
    return f"{KIT_COMMAND} {asset} {loop} kits/{loop} --frames {frames}"


def kit_needs_input(run: StageRun, loop: str) -> NeedsInput | None:
    """Why a frame Loop's kit holds the Stage, or None.

    - No `frames` Decision and no imported kit: the Loop has no frames; `next` suggests writing a kit.
    - A kit whose frame file is gone, or that was painted on another fit.
    A kit is ignored when the Loop's `frames` Decision (ticket 0192) takes its frames from somewhere else.
    """
    asset = run.asset_id
    chosen = _decisions_of(run, "loop", loop, "frames")
    if chosen and chosen[-1].data.get("source") != "kit":
        return None
    kit = kit_of(run, loop)
    if kit is None:
        if chosen:
            return None  # a kit is chosen and nothing is imported: 0192's and 0194's to report
        return NeedsInput(f"the Loop {loop} is a frame Loop with no frames", command=kit_command(asset, loop))
    undo = f"kiripix undo {asset} loops"
    for name in kit["frames"]:
        if frame_path(loop, str(name)) not in run.files:
            return NeedsInput(f"a frame of the kit of {loop} ({name}.png) is gone from the Asset",
                              owner_action=f"Import the frames again: kiripix import {asset} <png...> --loop {loop}.")
    fit = run.upstream["fit"] / "fit.png"
    if fit.is_file() and fit_hash(fit) != str(kit["fit"]):
        return NeedsInput(f"the kit frames of {loop} were painted on another fit",
                          owner_action=f"Write a new kit ({kit_command(asset, loop)} --force), paint it and import it, "
                                       f"or undo the import ({undo}).")
    return None


# the region, for the kit and the import


def kit_region(run: StageRun, room: EditRoom, loop: str, layer: str | None) -> tuple[Any, tuple[int, int, int, int] | None]:
    """The Loop's region on the fitted room (cut to a Layer's alpha when `layer` names one) and its box (x, y, w, h)."""
    region = paint_region(run, "loop", loop, room.fit.shape[:2], room.fit, None)
    if layer is not None:
        alpha = dict(room.layers).get(layer)
        if alpha is None:
            return np.zeros_like(region), None
        region = region & alpha
    return region, mask_box(region)
