"""A Marker's `look` (ticket 0314, ADR 0013): what `decide` checks of a `marker` Decision on `place` before it is recorded.
Only a light, an emitter or an interactable may name a Look, and the Look must exist (an edit is picked for it). `place`
reports the same when it runs (`recipes.room`), so a Look whose pick was undone later fails there too. The caller holds the
Asset lock."""

from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.recipes.looks import LOOKS_STAGE, look_ids
from kiripix.recipes.room import look_marker_problem


def marker_look_findings(project: Project, asset: Asset, stage: str, edits: list[tuple[str, dict[str, Any]]]
                         ) -> list[Finding]:
    """What refuses a `marker` Decision's `look`: a Marker type that may not name a Look (`marker.look_type`) and a Look the
    room doesn't have (`marker.unknown_look`)."""
    if asset.kind != "room" or stage != "place":
        return []
    wanted = [data for name, data in edits if name == "marker" and data.get("look") is not None]
    if not wanted:
        return []
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    built = look_ids(graph.replay(LOOKS_STAGE).current)
    found: list[Finding] = []
    for data in wanted:
        problem = look_marker_problem(str(data["type"]), str(data["look"]), built)
        if problem is None:
            continue
        code, message = problem
        found.append(Finding(
            code=code, message=f"the {data['type']} '{data['id']}': {message}",
            position=Position(asset=asset.id, stage="place", field="marker.look"),
            fix=f"kiripix describe {asset.kind} --stage place"))
    return found
