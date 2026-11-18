"""A room's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

from typing import Any

from kiripix.checks import Position
from kiripix.core.errors import ExitCode, fail
from kiripix.core.graph import AssetGraph
from kiripix.export.built import EXPORT_STAGE, built_dir, read_built_record
from kiripix.recipes.room import ROOM_SCHEMA_VERSION

ROOM_FILE = "room.json"
PLATE_FILE = "plate.png"


def read_room(graph: AssetGraph) -> dict[str, Any]:
    room = read_built_record(graph, "room", ROOM_FILE, ROOM_SCHEMA_VERSION)
    for layer in room["layers"]:
        # `place`'s check `layer.no_ysort` refuses this before an export; this keeps the status of such a room readable
        if not layer["above"] and layer["y"] is None:
            raise fail("layer.no_ysort", f"the Layer '{layer['id']}' has no y-sort line and isn't always above",
                       owner_action=f"Place a ysort Marker with layer {layer['id']}, or mark it always above: see "
                                    f"kiripix check {graph.asset.id}",
                       position=Position(asset=graph.asset.id, stage="place", file=str(layer["file"])),
                       exit_code=ExitCode.CHECK_FAILED)
    return room
