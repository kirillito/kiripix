"""An NPC's built export (`out/export/`) and the one file the game gets (ticket 0358, ADR 0015).

The `export` Stage leaves `choose`'s `npc.json` in `out/export/`. The game's `npc/<name>/npc.json` is made from it here, because
the paths of the base's and the Wearables' exports depend on the export root, which only the Exporter knows:

    {"schema_version": 1, "asset": "npc.guard",
     "base": "character.body_m", "base_path": "res://kiripix/character/body_m/body_m.tscn",
     "wearables": [{"id": "wearable.hair_a", "order": 10, "path": "res://kiripix/wearable/hair_a/hair_a.tscn"}, ...],  # bottom to top
     "colours": {"hair": {"choice": "auburn", "rgb": [[r, g, b], ...]}}}                                               # by Part

No images: the game draws the base's and the Wearables' own exports. It is refused until each of them is in the game.
"""

import json
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core.errors import ExitCode, KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.export.built import EXPORT_STAGE, read_built_record
from kiripix.export.manifest import read_manifest
from kiripix.export.target import GodotTarget
from kiripix.recipes.npc import NPC_FILE, NPC_SCHEMA_VERSION

GAME_SCHEMA_VERSION = 1  # the game's own `npc.json`, written by this Exporter


def read_npc(graph: AssetGraph) -> dict[str, Any]:
    return read_built_record(graph, "npc", NPC_FILE, NPC_SCHEMA_VERSION)


def scene_path(target: GodotTarget, asset_id: str) -> str:
    """Where the game has an exported Asset's scene: `<root>/<kind>/<name>/<name>.tscn`."""
    kind, name = asset_id.split(".", 1)
    return f"{target.root}/{kind}/{name}/{name}.tscn"


def _exported(target: GodotTarget, asset_id: str, planned: dict[str, bytes] | None) -> bool:
    """Whether the Asset is in the game: its Manifest lists it as exported, or the same export call is about to write its scene."""
    if scene_path(target, asset_id) in (planned or {}):
        return True
    shown = target.manifest(asset_id)
    manifest = read_manifest(target.path(shown), shown)
    return manifest is not None and manifest.exported


def exported_files(npc: dict[str, Any], target: GodotTarget, asset: str, planned: dict[str, bytes] | None = None) -> bytes:
    """The game's `npc.json`, or the refusal (every missing export named): `npc.base_not_exported` and
    `npc.wearable_not_exported`. `planned` is the files, by `res://` path, that the same call is about to write."""
    position = Position(asset=asset, stage=EXPORT_STAGE)
    base = str(npc["base"])
    refused: list[Finding] = []
    if not _exported(target, base, planned):
        refused.append(Finding(code="npc.base_not_exported", message=f"{asset}'s base {base} hasn't been exported to the game",
                               position=position, fix=f"kiripix export {base}"))
    for wearable in npc["wearables"]:
        if not _exported(target, str(wearable["id"]), planned):
            refused.append(Finding(
                code="npc.wearable_not_exported",
                message=f"{asset}'s Wearable {wearable['id']} hasn't been exported to the game",
                position=position, fix=f"kiripix export {wearable['id']}"))
    if refused:
        raise KiripixError(refused, ExitCode.ERROR)
    record = {
        "schema_version": GAME_SCHEMA_VERSION,
        "asset": asset,
        "base": base,
        "base_path": scene_path(target, base),
        "wearables": [{"id": str(w["id"]), "order": int(w["order"]), "path": scene_path(target, str(w["id"]))}
                      for w in npc["wearables"]],
        "colours": npc["colours"],
    }
    return (json.dumps(record, indent=2) + "\n").encode("utf-8")


__all__ = ["GAME_SCHEMA_VERSION", "exported_files", "read_npc", "scene_path"]
