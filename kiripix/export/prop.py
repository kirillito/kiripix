"""A prop's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

import json
from typing import Any

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.export.room import EXPORT_STAGE, built_dir
from kiripix.recipes.prop import PROP_SCHEMA_VERSION

PROP_FILE = "prop.json"
SPRITE_FILE = "sprite.png"


def read_prop(graph: AssetGraph) -> dict[str, Any]:
    prop: dict[str, Any] = json.loads((built_dir(graph) / PROP_FILE).read_text(encoding="utf-8"))
    if prop.get("schema_version") != PROP_SCHEMA_VERSION:
        raise fail("export.prop_invalid", f"{graph.asset.id}'s {PROP_FILE} has schema_version "
                   f"{prop.get('schema_version')}; this Kiripix reads {PROP_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    return prop
