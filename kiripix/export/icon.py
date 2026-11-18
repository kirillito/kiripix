"""An icon's built export (`out/export/`): the texture and record its `export` Stage leaves for the Exporter."""

import json
from typing import Any

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.export.room import EXPORT_STAGE, built_dir
from kiripix.recipes.icon import ICON_FILE, ICON_RECORD, ICON_SCHEMA_VERSION


def read_icon(graph: AssetGraph) -> dict[str, Any]:
    icon: dict[str, Any] = json.loads((built_dir(graph) / ICON_RECORD).read_text(encoding="utf-8"))
    if icon.get("schema_version") != ICON_SCHEMA_VERSION:
        raise fail("export.icon_invalid", f"{graph.asset.id}'s {ICON_RECORD} has schema_version "
                   f"{icon.get('schema_version')}; this Kiripix reads {ICON_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    return icon


__all__ = ["ICON_FILE", "ICON_RECORD", "read_icon"]
