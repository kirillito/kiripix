"""The body's Check `wearable.stack_differs` (ticket 0294): its Wearables' built `render` frames stacked over its own by a fixed
order and by depth, and the pixels where the two differ.

The order is the Wearables' `order` (a `sheet` parameter, ticket 0293, default 10), the lowest first, ties by ID, all above the body. The depth pass is
the render's own (16 bit, 0 nearest, the body's depth scale in every Wearable). Nothing here is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    from PIL import Image
else:  # `describe` and `status` import this through the character's recipe: no numpy or PIL until it runs (0163, 0277)
    np = lazy_module("numpy")
    Image = lazy_module("PIL.Image")

from kiripix.checks import Finding, StackFrame, check_stack_differs
from kiripix.ops import stack_by_depth, stack_by_order, stack_difference
from kiripix.ops.looks import mask_box
from kiripix.recipes.base import StageRun


def _frames(folder: Path) -> dict[tuple[str, str, int], dict[str, str]]:
    """The files of each frame of a built `render`, by (clip, direction, index); empty when it can't be read."""
    try:
        document: dict[str, Any] = json.loads((folder / "render.json").read_text(encoding="utf-8"))
        return {(clip["name"], d, f["index"]): f["files"]
                for clip in document["clips"] for d, frames in clip["directions"].items() for f in frames}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def _read(folder: Path, files: dict[str, str]) -> tuple[np.ndarray, np.ndarray] | None:
    try:
        with Image.open(folder / files["color"]) as colour, Image.open(folder / files["depth"]) as depth:
            return np.asarray(colour.convert("RGBA"), dtype=np.uint8), np.asarray(depth, dtype=np.uint16)
    except (OSError, ValueError):
        return None


def check_render_stack(run: StageRun) -> list[Finding]:
    """`wearable.stack_differs`, on the body's `render`, once at least one of its Wearables' `render` is built."""
    if not run.wearing:
        return []
    body = _frames(run.output_dir)
    worn = {name: _frames(folder) for name, folder in sorted(run.wearing.items(), key=lambda i: (run.wearing_order.get(i[0], 0), i[0]))}
    worn = {name: frames for name, frames in worn.items() if frames}
    if not body or not worn:
        return []
    results: list[StackFrame] = []
    for key in sorted(body):
        clip, direction, index = key
        pairs = [_read(run.output_dir, body[key])]
        for name, frames in worn.items():
            if key in frames:
                pairs.append(_read(run.wearing[name], frames[key]))
        stacked = [p for p in pairs if p is not None]
        if len(stacked) < 2 or any(p[0].shape != stacked[0][0].shape for p in stacked):
            continue  # a Wearable built for another cell is stale: `status` says so
        colours, depths = [p[0] for p in stacked], [p[1] for p in stacked]
        by_depth = stack_by_depth(colours, depths)
        difference = stack_difference(stack_by_order(colours), by_depth)
        shown = by_depth[..., 3] > 0
        results.append(StackFrame(clip=clip, direction=direction, index=index, differing=int(difference.sum()),
                                  box=mask_box(difference), visible=int(shown.sum())))
        run.check_cancel()
    return check_stack_differs(results, run.asset_id, list(worn), fix=f"kiripix show {run.asset_id} render")
