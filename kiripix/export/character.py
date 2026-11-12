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
    """The part names in `ramps.png`'s row order, which `metadata/kiripix_parts` lists. For now `character.json`'s order (dark
    to light is within a ramp, not between them); rows are written from these names, never by position (ticket 0169)."""
    return [str(part["name"]) for part in character.get("parts", [])]


def ramps_png(character: dict[str, Any], rows: list[str]) -> bytes:
    """`ramps.png`: one row per name in `rows`, one pixel per ramp step, dark to light, the row padded to the longest ramp with
    transparent pixels. A name the character has no part for is a fully transparent row."""
    from io import BytesIO

    from PIL import Image

    ramps = {str(part["name"]): part["rgb"] for part in character.get("parts", [])}
    width = max([len(ramps.get(name, [])) for name in rows] + [1])
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
