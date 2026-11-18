"""A portrait set's built export (`out/export/`): the images and record its `export` Stage leaves for the Exporter."""

from typing import Any

from kiripix.core.graph import AssetGraph
from kiripix.export.built import read_built_record
from kiripix.recipes.portrait import NEUTRAL, PORTRAIT_FILE, PORTRAIT_SCHEMA_VERSION


def read_portrait(graph: AssetGraph) -> dict[str, Any]:
    return read_built_record(graph, "portrait", PORTRAIT_FILE, PORTRAIT_SCHEMA_VERSION)


def emotion_ids(portrait: dict[str, Any]) -> list[str]:
    """The emotions of the set (the neutral image is the set's own, not an emotion), in the Decisions' order."""
    return [str(e["id"]) for e in portrait["emotions"] if e["id"] != NEUTRAL]


__all__ = ["PORTRAIT_FILE", "emotion_ids", "read_portrait"]
