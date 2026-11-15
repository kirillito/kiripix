"""The `look-difference` Probe's work (ticket 0205, spec §10.5): the region a `difference` Decision would add to a Look.

It calls what the `looks` Stage calls (`kiripix.recipes.looks.fitted_look`, then the Op `difference_region` with the
Decision's defaults), on the Stage's own inputs as built, so the answer can't differ from the build. Nothing is recorded.
"""

from __future__ import annotations

from typing import Any

from kiripix.checks import Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.ops import difference_region
from kiripix.recipes.base import BoxCorners, StageFailure
from kiripix.recipes.common import box_problem
from kiripix.recipes.looks import LOOKS_STAGE, current_source, edit_path, fitted_look, picked_edits
from kiripix.recipes.regions import DIFFERENCE_SPECKS, DIFFERENCE_TOLERANCE, EditRoom


def look_difference(project: Project, asset: Asset, look: str, box: BoxCorners, tolerance: float | None,
                    specks: int | None) -> Any:
    """The region (a Mask on the target grid) a `difference` over `box` would add to `look`."""
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec = next((stage for stage in graph.kind.stages if stage.name == LOOKS_STAGE), None)
    where = Position(asset=asset.id, stage=LOOKS_STAGE)
    if spec is None:
        raise fail("probe.not_supported", f"a {asset.kind} has no Looks", fix="kiripix describe project")
    run = graph.stage_run(spec, graph.output_dir(spec))
    edit = picked_edits(run).get(look)
    if edit is None:
        raise fail("probe.look_not_picked", f"the Look {look} of {asset.id} has no picked edit", position=where,
                   fix=f"kiripix pick {asset.id} <variant> --look {look}")
    # only this Look's own reasons refuse it: another Look waiting for its edit doesn't stop this one being measured
    if edit[1] != current_source(run):
        raise fail("probe.look_not_ready", f"the edit of the Look {look} was made on another Source", position=where,
                   owner_action=f"Re-make the edit from the new Source (kiripix import {asset.id} <png> --look {look}, then "
                                f"kiripix pick {asset.id} <variant> --look {look}).")
    if edit_path(look, edit[0]) not in run.files:
        raise fail("probe.look_not_ready", f"the picked edit {edit[0]} of the Look {look} was deleted", position=where,
                   owner_action=f"Import an edit again (kiripix import {asset.id} <png> --look {look}) and pick it.")
    unbuilt = [name for name in spec.inputs.upstream if graph.built_hash(graph.spec(name)) is None]
    if unbuilt:
        raise fail("probe.not_ready", f"{asset.id} has no built {', '.join(unbuilt)} to measure the edit against yet",
                   position=where, fix=f"kiripix run {asset.id} {LOOKS_STAGE}")
    try:
        room = EditRoom(run)
        problem = box_problem(box, room.grid.width, room.grid.height, room.grid.pad_right, room.grid.pad_bottom)
        if problem is not None:
            raise fail("input.invalid", f"the box ({box[0]}, {box[1]}) to ({box[2]}, {box[3]}) {problem}", position=where,
                       fix=f"kiripix probe look-difference {asset.id} {look} 0,0,{room.grid.width - 1},"
                           f"{room.grid.height - 1}")
        fitted, _ = fitted_look(run, room, look, edit[0])
        return difference_region(room.fit, fitted, box, DIFFERENCE_TOLERANCE if tolerance is None else tolerance,
                                 DIFFERENCE_SPECKS if specks is None else specks)
    except StageFailure as error:
        raise fail("probe.look_not_ready", str(error), position=where, fix=f"kiripix run {asset.id} {LOOKS_STAGE}") from None
