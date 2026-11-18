"""An icon's built export (`out/export/`): the texture and record its `export` Stage leaves for the Exporter."""

from typing import Any

from kiripix.core.graph import AssetGraph
from kiripix.export.built import read_built_record
from kiripix.recipes.icon import ICON_FILE, ICON_RECORD, ICON_SCHEMA_VERSION


def read_icon(graph: AssetGraph) -> dict[str, Any]:
    return read_built_record(graph, "icon", ICON_RECORD, ICON_SCHEMA_VERSION)


__all__ = ["ICON_FILE", "ICON_RECORD", "read_icon"]
