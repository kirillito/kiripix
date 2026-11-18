"""A Wearable's `palette` and `finish` Stages (spec §6.3, ticket 0292).

`palette` is the character's (`character_palette.py`: the Wearable's render frames mapped once, parts with ramps of their own),
with one more rule: nothing the Wearable uses is a colour of its body's palette (the body's fixed colours and the ramps of its
parts), so recolouring a Wearable touches nothing else. The body's `palette.json` is read, so `palette` waits for the body's
`palette` to be built. A part taken from the Project's ramp table that the body's palette already has (same colours) is refused:
`wearable.ramp_shared`.

`finish` is the character's with no outline (the game draws one on the stack): its `outline`, `outline_colour`, `placement` and
eye parameters aren't the Wearable's. The normal pass is aligned to the colour frames and quantised as the body's, never
palette-mapped.
"""

import json
from dataclasses import replace
from typing import Any

from kiripix.ops.lazy import lazy_module
from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.character_finish import FINISH_FILE, run_character_finish
from kiripix.recipes.character_palette import palette_stage_excluding

np = lazy_module("numpy")

# What `finish` fixes for a Wearable: no outline, no stamped eyes (the character's parameters, off).
FINISH_FIXED: dict[str, Any] = {"outline": False, "outline_colour": 0, "placement": "outside", "eyes": "render"}
# `normal_levels` is the body's (read from its built `finish`), so the stacked normals quantise alike.
DROPPED_FINISH = ("outline", "outline_colour", "placement", "eyes", "eye_colour", "eye_white", "eye_gap", "normal_levels")


def body_colours(run: StageRun) -> Any:
    """Every colour of the body's palette, as an (N, 3) array: its fixed subset and the ramps of its parts."""
    body = run.body
    if body is None or "palette" not in body.built:
        raise StageFailure("this Wearable has no built body palette", code="wearable.body_unknown")
    try:
        document = json.loads((body.built["palette"] / "palette.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"the palette of {body.asset_id} can't be read", fix=f"kiripix run {body.asset_id} palette") from None
    colours = [c["rgb"] for c in document.get("colors", [])] + [rgb for p in document.get("parts", []) for rgb in p["rgb"]]
    return np.array(colours, dtype=np.uint8).reshape(-1, 3)


def _run(run: StageRun) -> None:
    taken = {tuple(int(v) for v in c) for c in body_colours(run)}
    for row in run.settings.get("character.ramps") or []:
        if row.get("rgb") is not None and taken & {tuple(int(v) for v in c) for c in row["rgb"]}:
            names = str(run.params.get("parts", ""))
            if any(part.split("=")[0].split(":")[0].strip() == row["name"] for part in names.split(",")):
                raise StageFailure(
                    f"part {row['name']!r} of the Project's ramp table has colours that the palette of its body "
                    f"{run.body.asset_id if run.body else ''} uses, so recolouring it would recolour the body",
                    code="wearable.ramp_shared",
                    owner_action=f"Give the Wearable's part another row of the ramp table, or take {row['name']!r} out of the "
                                 f"body's palette parts.")
    palette_stage_excluding(body_colours)(run)


run_wearable_palette = _run


def body_normal_levels(run: StageRun) -> int:
    """The body's `normal_levels`, from its built `finish`: a Wearable's normals are quantised as the body's."""
    body = run.body
    if body is None or "finish" not in body.built:
        raise StageFailure("this Wearable has no built body finish", code="wearable.body_unknown")
    drawn = json.loads((body.built["finish"] / FINISH_FILE).read_text(encoding="utf-8"))
    return int(drawn["normal_levels"])


def run_wearable_finish(run: StageRun) -> None:
    fixed = {**FINISH_FIXED, "normal_levels": body_normal_levels(run)}
    run_character_finish(replace(run, params={**run.params, **fixed}))
