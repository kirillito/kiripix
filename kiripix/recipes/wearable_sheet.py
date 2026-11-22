"""A Wearable's `sheet` Stage (spec §6.3, ticket 0293).

The character's `sheet` (`character_sheet.py`) on the Wearable's `finish` frames: the body's cell and pivot (they are the
render's, which is the body's), the same packing (a cell that repeats is packed once, ticket 0375), a colour atlas and a normal atlas. This adds a third
atlas of the same layout, `depth.png` (`character_sheet.run_sheet_with_depth`, which the body's `sheet` uses too): the render's
depth pass, 16 bit gray, 0 nearest and 65535 farthest, in the body's depth scale, so that the game can stack the body and its Wearables by depth. Where a cell has no frame pixel the depth is
65535. `sheet.json` is the character's, with `files.depth` and the default stacking `order` added.

`order` is the Wearable's default stacking order over the body (which is 0): the game stacks by it, or by depth for an exact
result. The trial's order is body, legs, jacket or coat, pack, hair, so 10, 20 and so on leave room between. Equal orders are
stacked by Asset ID.
"""

from kiripix.recipes.base import ParamSpec, StageRun
from kiripix.recipes.character_sheet import DEPTH_ATLAS, check_character_sheet, run_sheet_with_depth

DEFAULT_ORDER = 10  # above the body (0)

ORDER = ParamSpec(
    name="order", type="int", default=DEFAULT_ORDER, minimum=-1000, maximum=1000,
    description="The default stacking order over the body, which is 0: a higher one is drawn over a lower one. The trial's "
                "order is legs, jacket or coat, pack, hair. The game stacks by it, or by depth for an exact result. Equal "
                "orders go by Asset ID.")


def run_wearable_sheet(run: StageRun) -> None:
    run_sheet_with_depth(run, int(run.params.get("order", DEFAULT_ORDER)))


__all__ = ["DEFAULT_ORDER", "DEPTH_ATLAS", "ORDER", "check_wearable_sheet", "run_wearable_sheet"]
check_wearable_sheet = check_character_sheet
