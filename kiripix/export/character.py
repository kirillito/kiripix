"""A character's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter."""

import json
from typing import Any

from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.export.room import EXPORT_STAGE, built_dir
from kiripix.recipes.character_export import CHARACTER_FILE, CHARACTER_SCHEMA_VERSION

COLOR_FILE = "color.png"
NORMAL_FILE = "normal.png"


RAMPS_FILE = "ramps.png"


def ramp_rows(character: dict[str, Any]) -> list[str]:
    """The part names in `ramps.png`'s row order, which `metadata/kiripix_parts` lists: `character.json`'s `rows`, the Project
    ramp table's parts in its order, so the same list on every character (ticket 0169); with no table, the character's own
    parts. Rows are written from these names, never by position."""
    return [str(row["name"]) for row in character.get("rows", [])]


def ramps_png(character: dict[str, Any], rows: list[str]) -> bytes:
    """`ramps.png`: one row per name in `rows`, one pixel per ramp step, dark to light, the row padded with transparent pixels
    to the longest ramp of the character's parts and of `character.json`'s `rows` (the table's lengths). A name the character
    has no part for is a fully transparent row."""
    from io import BytesIO

    from PIL import Image

    ramps = {str(part["name"]): part["rgb"] for part in character.get("parts", [])}
    lengths = {str(row["name"]): int(row["length"]) for row in character.get("rows", [])}
    width = max([len(ramps.get(name, [])) for name in rows] + [lengths.get(name, 0) for name in rows] + [1])
    pixels = bytearray(len(rows) * width * 4)
    for row, name in enumerate(rows):
        for step, (red, green, blue) in enumerate(ramps.get(name, [])):
            start = (row * width + step) * 4
            pixels[start:start + 4] = bytes((red, green, blue, 255))
    image = Image.frombytes("RGBA", (width, len(rows)), bytes(pixels))
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def read_character(graph: AssetGraph) -> dict[str, Any]:
    character: dict[str, Any] = json.loads((built_dir(graph) / CHARACTER_FILE).read_text(encoding="utf-8"))
    if character.get("schema_version") != CHARACTER_SCHEMA_VERSION:
        raise fail("export.character_invalid", f"{graph.asset.id}'s {CHARACTER_FILE} has schema_version "
                   f"{character.get('schema_version')}; this Kiripix reads {CHARACTER_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    return character
