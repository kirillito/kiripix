"""A Wearable's `sheet` Stage (spec §6.3, ticket 0293).

The character's `sheet` (`character_sheet.py`) on the Wearable's `finish` frames: the body's cell and pivot (they are the
render's, which is the body's), the same grid and rect for each frame, a colour atlas and a normal atlas. This adds a third
atlas of the same layout, `depth.png`: the render's depth pass, 16 bit gray, 0 nearest and 65535 farthest, in the body's
depth scale, so that the game can stack the body and its Wearables by depth. Where a cell has no frame pixel the depth is
65535. `sheet.json` is the character's, with `files.depth` and the default stacking `order` added.

`order` is the Wearable's default stacking order over the body (which is 0): the game stacks by it, or by depth for an exact
result. The trial's order is body, legs, jacket or coat, pack, hair, so 10, 20 and so on leave room between. Equal orders are
stacked by Asset ID.
"""

import json
from typing import Any

from kiripix.ops.lazy import lazy_module
from kiripix.recipes.base import ParamSpec, StageFailure, StageRun
from kiripix.recipes.character_palette import RENDER_FILE
from kiripix.recipes.character_sheet import SHEET_FILE, check_character_sheet, run_character_sheet

np = lazy_module("numpy")

DEPTH_ATLAS = "depth.png"
DEFAULT_ORDER = 10  # above the body (0)
FAR = 65535

ORDER = ParamSpec(
    name="order", type="int", default=DEFAULT_ORDER, minimum=-1000, maximum=1000,
    description="The default stacking order over the body, which is 0: a higher one is drawn over a lower one. The trial's "
                "order is legs, jacket or coat, pack, hair. The game stacks by it, or by depth for an exact result. Equal "
                "orders go by Asset ID.")


def _depth_frame(path: Any, asset: str) -> Any:
    from PIL import Image

    with Image.open(path) as image:
        depth = np.asarray(image, dtype=np.uint16)
    if depth.ndim != 2:
        raise StageFailure("a depth frame of render is not a 16 bit gray image; run render again",
                           fix=f"kiripix run {asset} render --force")
    return depth


def run_wearable_sheet(run: StageRun) -> None:
    from PIL import Image

    from kiripix.ops import pack_atlas

    run_character_sheet(run)
    sheet: dict[str, Any] = json.loads((run.output_dir / SHEET_FILE).read_text(encoding="utf-8"))
    document: dict[str, Any] = json.loads((run.upstream["render"] / RENDER_FILE).read_text(encoding="utf-8"))
    frames = {(c["name"], d, int(f["index"])): f for c in document["clips"] for d, listed in c["directions"].items()
              for f in listed}
    cell = (int(sheet["cell"]["width"]), int(sheet["cell"]["height"]))
    cell_pivot = (int(sheet["pivot"]["x"]), int(sheet["pivot"]["y"]))
    encoded: list[Any] = []
    pivots: list[tuple[int, int]] = []
    for clip in sheet["clips"]:
        for direction, listed in clip["directions"].items():
            for entry in listed:
                run.check_cancel()
                found = frames[(clip["name"], direction, int(entry["index"]))]
                depth = _depth_frame(run.upstream["render"] / str(found["files"]["depth"]), run.asset_id)
                rgba = np.zeros((*depth.shape, 4), dtype=np.uint8)  # the 16 bit value in two bytes; alpha marks a pixel
                rgba[..., 0], rgba[..., 1], rgba[..., 3] = depth >> 8, depth & 255, 255
                encoded.append(rgba)
                pivots.append((int(np.floor(found["pivot"][0] + 0.5)), int(np.floor(found["pivot"][1] + 0.5))))
    atlas, rects = pack_atlas(encoded, pivots, cell, int(sheet["columns"]), cell_pivot)
    expected = [(e["rect"]["x"], e["rect"]["y"], e["rect"]["width"], e["rect"]["height"])
                for c in sheet["clips"] for listed in c["directions"].values() for e in listed]
    if rects != expected:
        raise StageFailure("the depth atlas doesn't share the colour atlas's layout")  # can't happen
    depth_atlas = (atlas[..., 0].astype(np.uint16) << 8) | atlas[..., 1].astype(np.uint16)
    depth_atlas[atlas[..., 3] == 0] = FAR
    Image.fromarray(depth_atlas).save(run.output_dir / DEPTH_ATLAS)
    sheet["files"]["depth"] = DEPTH_ATLAS
    sheet["order"] = int(run.params.get("order", DEFAULT_ORDER))
    (run.output_dir / SHEET_FILE).write_text(json.dumps(sheet, indent=1) + "\n", encoding="utf-8")


check_wearable_sheet = check_character_sheet
