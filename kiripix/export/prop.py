"""A prop's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

from typing import Any

from kiripix.core.graph import AssetGraph
from kiripix.export.built import read_built_record
from kiripix.recipes.prop import PROP_SCHEMA_VERSION

PROP_FILE = "prop.json"
SPRITE_FILE = "sprite.png"


def read_prop(graph: AssetGraph) -> dict[str, Any]:
    return read_built_record(graph, "prop", PROP_FILE, PROP_SCHEMA_VERSION)
