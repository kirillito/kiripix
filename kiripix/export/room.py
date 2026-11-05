"""A room's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

import json
from pathlib import Path
from typing import Any

from kiripix.checks import Position
from kiripix.core.errors import ExitCode, fail
from kiripix.core.graph import AssetGraph
from kiripix.recipes.room import ROOM_SCHEMA_VERSION

ROOM_FILE = "room.json"
PLATE_FILE = "plate.png"
EXPORT_STAGE = "export"


def built_dir(graph: AssetGraph) -> Path:
    return graph.output_dir(graph.spec(EXPORT_STAGE))


def read_room(graph: AssetGraph) -> dict[str, Any]:
    room: dict[str, Any] = json.loads((built_dir(graph) / ROOM_FILE).read_text(encoding="utf-8"))
    if room.get("schema_version") != ROOM_SCHEMA_VERSION:
        raise fail("export.room_invalid", f"{graph.asset.id}'s {ROOM_FILE} has schema_version "
                   f"{room.get('schema_version')}; this Kiripix reads {ROOM_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    for layer in room["layers"]:
        # `place`'s check `layer.no_ysort` refuses this before an export; this keeps the status of such a room readable
        if not layer["above"] and layer["y"] is None:
            raise fail("layer.no_ysort", f"the Layer '{layer['id']}' has no y-sort line and isn't always above",
                       owner_action=f"Place a ysort Marker with layer {layer['id']}, or mark it always above: see "
                                    f"kiripix check {graph.asset.id}",
                       position=Position(asset=graph.asset.id, stage="place", file=str(layer["file"])),
                       exit_code=ExitCode.CHECK_FAILED)
    return room
