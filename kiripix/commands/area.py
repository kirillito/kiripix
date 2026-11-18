"""`area-settle`: settle the ambiguous cells of a room's area, `polygon` Decisions on `masks`, one per cell and Mask (ticket 0279)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import editing
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba
from kiripix.core.project import find_project
from kiripix.recipes.room import ambiguous_cells, current_area

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

COLLISION_MASKS = ("solid", "pit")


class SettleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The room, such as room.laneway.")
    area: str = Field(description="The area Marker's ID, such as battle.yard. It needs a `cell`.")
    rule: Literal["majority"] = Field("majority", description="How a cell is settled: `majority` fills a cell that "
                                                             "`solid` or `pit` covers by at least half, and clears the others.")
    dry_run: bool = Field(False, description="Write nothing; list what each cell would get.")


class CellSettled(BaseModel):
    x: int
    y: int
    mask: str = Field(description="The Mask filled (the one covering the cell most), or, for a clear, the Mask cleared.")
    coverage: float = Field(description="The share of the cell that `solid` and `pit` cover together, 0 to 1.")
    action: Literal["fill", "clear"]


class SettleData(BaseModel):
    asset: str
    area: str
    rule: str
    dry_run: bool
    cell: int
    cells: list[CellSettled]
    decisions: int = Field(description="How many `polygon` Decisions were recorded on `masks` (a cleared cell takes one per "
                                       "Mask that covers it); 0 with --dry-run.")

    def text(self) -> str:
        verb = "would settle" if self.dry_run else "settled"
        lines = [f"{self.asset} {self.area}: {verb} {len(self.cells)} cells by {self.rule}"]
        lines += [f"  ({c.x}, {c.y}) {c.mask} {c.coverage:.0%} -> {c.action}" for c in self.cells]
        return "\n".join(lines)


def _asset_lock(arguments: SettleInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


def _square(x: int, y: int, cell: int, mask: str, erase: bool) -> editing.DecisionDocument:
    points = [[x, y], [x + cell - 1, y], [x + cell - 1, y + cell - 1], [x, y + cell - 1]]
    return editing.DecisionDocument(decision="polygon", data={"mask": mask, "erase": erase, "points": points})


@command(
    "area-settle",
    summary="Settle an area's ambiguous cells by majority: a cell half or more covered by solid or pit is filled on the Mask "
            "covering it most, the others are cleared on every Mask that touches them, with one `polygon` Decision on `masks` per cell and Mask. An agent may run it: the rule "
            "is the Owner's standing choice (ticket 0134), and `undo` on `masks` takes it back one Decision at a time.",
    input=SettleInput,
    output=SettleData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "area")),
    locks=LockNeeds(asset=_asset_lock),
)
def area_settle(arguments: SettleInput, context: Context) -> Outcome[SettleData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if asset.kind != "room":
        raise fail("input.invalid", f"{asset.id} is a {asset.kind}; areas are on rooms")
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    area = current_area(graph.decisions(graph.spec("place")), arguments.area)
    if area is None:
        raise fail("area.unknown", f"{asset.id} has no area '{arguments.area}'",
                   fix=f"kiripix show {asset.id} place")
    cell = area.get("cell")
    if cell is None:
        raise fail("area.no_cell", f"the area '{arguments.area}' has no `cell`, so it has no cells to settle",
                   fix=f"kiripix decide {asset.id} place --help")
    if graph.state("masks").status != "done":
        raise fail("area.masks_not_built", f"the masks of {asset.id} are not built and current, so their coverage isn't known",
                   fix=f"kiripix run {asset.id} masks")
    folder = graph.output_dir(graph.spec("masks"))
    masks: dict[str, np.ndarray] = {}
    for name in COLLISION_MASKS:
        if (folder / f"{name}.png").is_file():
            path = folder / f"{name}.png"
            masks[name] = load_rgba(path, str(path))[..., 0] > 0
    if "solid" not in masks:
        raise fail("area.masks_not_built", f"{asset.id} has no `solid` Mask yet", fix=f"kiripix run {asset.id} masks")
    blocked = np.logical_or.reduce(list(masks.values()))
    box = (int(area["x"]), int(area["y"]), int(area["x2"]), int(area["y2"]))
    cells: list[CellSettled] = []
    documents: list[editing.DecisionDocument] = []
    for x, y in ambiguous_cells(blocked, box, int(cell)):
        share = float(blocked[y:y + cell, x:x + cell].mean())
        covers = {name: float(mask[y:y + cell, x:x + cell].mean()) for name, mask in masks.items()}
        if share >= 0.5:
            best = max(covers, key=lambda name: (covers[name], name == "solid"))
            cells.append(CellSettled(x=x, y=y, mask=best, coverage=share, action="fill"))
            documents.append(_square(x, y, int(cell), best, erase=False))
        else:
            for name in covers:
                if covers[name] > 0:
                    cells.append(CellSettled(x=x, y=y, mask=name, coverage=share, action="clear"))
                    documents.append(_square(x, y, int(cell), name, erase=True))
    if documents and not arguments.dry_run:
        editing.record_decisions(project, asset, "masks", documents)
    return Outcome(SettleData(asset=asset.id, area=arguments.area, rule=arguments.rule, dry_run=arguments.dry_run,
                              cell=int(cell), cells=cells, decisions=0 if arguments.dry_run else len(documents)))
