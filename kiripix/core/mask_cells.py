"""The `half-cells` Probe's work (ticket 0346): the cells of a room's areas that one Mask, as built, half covers (a quarter
to three quarters). It is the band `area.ambiguous_cells` uses for `solid` and `pit`, here for any painted Mask, so the
mask screen highlights whole cells to paint without counting pixels itself (ADR 0008). Nothing is recorded."""

from typing import Any

from kiripix.checks import Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba
from kiripix.core.project import Project
from kiripix.recipes.room import ambiguous_cells, cell_areas


def half_cells(project: Project, asset: Asset, mask: str) -> dict[str, Any]:
    if asset.kind != "room":
        raise fail("input.invalid", f"{asset.id} is a {asset.kind}; half-cells is for a room's Masks",
                   fix="kiripix probe half-cells <room> <mask>")
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    masks = graph.spec("masks")
    if graph.built_hash(masks) is None:
        raise fail("probe.not_ready", f"{asset.id} masks has no output yet", fix=f"kiripix run {asset.id} masks",
                   position=Position(asset=asset.id, stage="masks"))
    path = graph.output_dir(masks) / f"{mask}.png"
    areas = cell_areas(graph.decisions(graph.spec("place")))
    if not path.is_file():
        return {"mask": mask, "cells": []}  # a Mask with nothing painted covers no cell
    covered = load_rgba(path, str(path))[..., 0] > 0
    cells = [{"x": x, "y": y, "cell": int(area["cell"])}
             for area in areas
             for x, y in ambiguous_cells(covered, (int(area["x"]), int(area["y"]), int(area["x2"]), int(area["y2"])),
                                         int(area["cell"]))]
    return {"mask": mask, "cells": cells}
