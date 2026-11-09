"""The `reach` Probe's work (spec §10.1, ticket 0078): what the `reach` Stage reports, from the Masks as built (ones
awaiting review too) and the Markers the `place` journal holds now. Nothing is recorded, no status changes and no lock is
taken, and `reach` itself stays stopped until the Owner accepts. The computation is the Stage's own, from its
`ReachHooks`."""

from typing import Any

from kiripix.checks import Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.recipes.base import StageFailure


def reach_report(project: Project, asset: Asset) -> dict[str, Any]:
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec, hooks = graph.stage_with(lambda s: s.reach, "floods the Body over the Masks")
    run = graph.stage_run(spec, graph.output_dir(spec))
    unsupported = hooks.unsupported(run)
    if unsupported is not None:
        raise fail("probe.not_ready", unsupported, owner_action=f"{unsupported}.",
                   position=Position(asset=asset.id, stage=spec.name))
    masks = graph.spec(hooks.masks_stage)
    if graph.built_hash(masks) is None:
        raise fail("probe.not_ready", f"{asset.id} {masks.name} has no output yet, and {spec.name} floods over it",
                   fix=f"kiripix run {asset.id} {masks.name}", position=Position(asset=asset.id, stage=masks.name))
    targets = hooks.targets(graph.replay(hooks.marker_stage).current)
    if not targets:
        example = '{"decision": "marker", "data": {"id": "spawn.main", "type": "spawn", "x": 0, "y": 0}}'
        raise fail("probe.no_markers", "no Spawn or Exit is placed, so the Body has nowhere to start from",
                   fix=f"kiripix decide {asset.id} {hooks.marker_stage} --decision '{example}'",
                   position=Position(asset=asset.id, stage=hooks.marker_stage))
    try:
        report = hooks.report(run, targets)
    except StageFailure as failure:
        raise fail("probe.not_ready", str(failure), owner_action=f"{failure}.",
                   position=Position(asset=asset.id, stage=spec.name)) from None
    masks_status = graph.state(masks.name).status
    return {"stage": spec.name, "status": graph.state(spec.name).status, "masks_status": masks_status,
            "awaiting_review": masks_status == "needs-review", "report": report}
