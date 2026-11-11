"""A character's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

import json
from typing import Any

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.export.room import EXPORT_STAGE, built_dir
from kiripix.recipes.character_export import CHARACTER_FILE, CHARACTER_SCHEMA_VERSION

COLOR_FILE = "color.png"
NORMAL_FILE = "normal.png"


def read_character(graph: AssetGraph) -> dict[str, Any]:
    character: dict[str, Any] = json.loads((built_dir(graph) / CHARACTER_FILE).read_text(encoding="utf-8"))
    if character.get("schema_version") != CHARACTER_SCHEMA_VERSION:
        raise fail("export.character_invalid", f"{graph.asset.id}'s {CHARACTER_FILE} has schema_version "
                   f"{character.get('schema_version')}; this Kiripix reads {CHARACTER_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    return character
