"""A room's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

import json
from pathlib import Path
from typing import Any

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph

ROOM_FILE = "room.json"
PLATE_FILE = "plate.png"
ROOM_SCHEMA_VERSION = 1
EXPORT_STAGE = "export"


def built_dir(graph: AssetGraph) -> Path:
    return graph.output_dir(graph.spec(EXPORT_STAGE))


def read_room(graph: AssetGraph) -> dict[str, Any]:
    room: dict[str, Any] = json.loads((built_dir(graph) / ROOM_FILE).read_text(encoding="utf-8"))
    if room.get("schema_version") != ROOM_SCHEMA_VERSION:
        raise fail("export.room_invalid", f"{graph.asset.id}'s {ROOM_FILE} has schema_version "
                   f"{room.get('schema_version')}; this Kiripix reads {ROOM_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    return room
