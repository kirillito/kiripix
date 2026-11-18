"""Any Kind's built export (`out/export/`): the folder its `export` Stage leaves for the Exporter, and its record."""

import json
from pathlib import Path
from typing import Any

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph

EXPORT_STAGE = "export"


def built_dir(graph: AssetGraph) -> Path:
    return graph.output_dir(graph.spec(EXPORT_STAGE))


def read_built_record(graph: AssetGraph, kind: str, file: str, version: int) -> dict[str, Any]:
    """The JSON record `file` of the Asset's built export, refused with `export.<kind>_invalid` and the rebuild when its
    `schema_version` isn't `version`."""
    record: dict[str, Any] = json.loads((built_dir(graph) / file).read_text(encoding="utf-8"))
    if record.get("schema_version") != version:
        raise fail(f"export.{kind}_invalid", f"{graph.asset.id}'s {file} has schema_version "
                   f"{record.get('schema_version')}; this Kiripix reads {version}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    return record
