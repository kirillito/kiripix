"""The things a character's clips hold (ticket 0300, 0238): what `decide` checks of a `clip` Decision's `attach` before it is
recorded. A held thing is on the Asset (or its base) when `src/things/<id>/` holds a `.glb` or `.blend` Variant (ticket 0301 imports them there), and a socket
is a bone of the built `rig.json`. The `clips` Stage checks the same when it runs (`recipes.clips`), so a thing taken away
or a rig changed later fails there too. The caller holds the Asset lock."""

import json
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.recipes import clips

CHARACTER = "character"
CLIPS_STAGE = "clips"


def asset_things(asset: Asset, base: Asset | None = None) -> set[str]:
    """The IDs of the Asset's held things (and its base's): the folders of `src/things/` that hold a Variant, the one rule
    the Stages use (`recipes.clips.held_things_of`)."""
    return clips.thing_ids(clips.folder_files(asset.dir), clips.folder_files(base.dir) if base is not None else None)


def rig_bones(graph: AssetGraph) -> list[str] | None:
    """The bones of the built rig, or None while `rig` is not built (so no socket can be checked yet). A character made from
    a base whose own `rig` isn't built yet has the base's skeleton (`rig.base_mismatch` holds it to that), so the base's rig
    stands in."""
    for each in (graph, graph.base):
        if each is None:
            continue
        path: Path = each.output_dir(each.spec("rig")) / "rig.json"
        try:
            document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return list(document["parents"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def attach_edit_findings(project: Project, asset: Asset, stage: str, edits: list[tuple[str, dict[str, Any]]]
                         ) -> list[Finding]:
    """What refuses a `clip` Decision's `attach`: a thing the Asset doesn't have (`clips.unknown_thing`) and, once `rig` is
    built, a socket that is no bone of it (`clips.unknown_socket`, the bones named in the message). A thing held
    twice is a Decision problem, caught by the schema."""
    if asset.kind != CHARACTER or stage != CLIPS_STAGE:
        return []
    wanted = [data for name, data in edits if name == clips.CLIP.name and data.get("attach")]
    if not wanted:
        return []
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    known, bones = asset_things(asset, graph.base_asset), rig_bones(graph)
    found: list[Finding] = []
    for data in wanted:
        attach = list(data["attach"])
        position = Position(asset=asset.id, stage=CLIPS_STAGE, field="clip.attach")
        if lost := clips.unknown_things(attach, known):
            found.append(Finding(
                code="clips.unknown_thing", position=position,
                message=f"the clip {data['name']} holds {', '.join(lost)}, and {asset.id} has no such thing "
                        f"(its things are {', '.join(sorted(known)) or 'none'})",
                owner_action=f"Import the thing: kiripix import {asset.id} <file> --role thing --thing {lost[0]}"))
        if bones is not None and (wrong := clips.unknown_sockets(attach, bones)):
            found.append(Finding(
                code="clips.unknown_socket", position=position,
                message=f"the clip {data['name']}: {clips.socket_message(wrong, bones)}",
                fix=f"kiripix describe {asset.kind} --stage {CLIPS_STAGE}"))
    return found
