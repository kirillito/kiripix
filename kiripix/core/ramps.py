"""The Project ramp table against what the characters built (ticket 0167, spec §6.3).

`kiripix.toml`'s `[[character.ramps]]` fixes each part's name, ramp length and row for every character. This module reads a
character's built `palette.json` and its exported `character.json` as files (core sits above `recipes` but never runs its Stages)
and registers the Project check `palette.parts_differ`, run by `check --all`. Nothing here writes.
"""

import json
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.core.project_checks import register_project_check
from kiripix.core.settings import RampSpec

PALETTE_STAGE = "palette"
EXPORT_STAGE = "export"
PALETTE_FILE = "palette.json"
CHARACTER_FILE = "character.json"
CHARACTER_KIND = "character"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _stage_dir(graph: AssetGraph, stage: str) -> Path | None:
    specs = [s for s in graph.kind.stages if s.name == stage]
    return graph.output_dir(specs[0]) if specs else None


def built_palette(graph: AssetGraph) -> dict[str, Any] | None:
    """The character's built `palette.json`, or None when its `palette` Stage has no complete output."""
    specs = [s for s in graph.kind.stages if s.name == PALETTE_STAGE]
    if not specs or graph.built_hash(specs[0]) is None:
        return None
    return _read(graph.output_dir(specs[0]) / PALETTE_FILE)


def exported_character(graph: AssetGraph) -> dict[str, Any] | None:
    """The character's exported `character.json`, or None when there is none."""
    folder = _stage_dir(graph, EXPORT_STAGE)
    return _read(folder / CHARACTER_FILE) if folder else None


def part_findings(table: list[RampSpec], document: dict[str, Any], asset: str, stage: str, file: str,
                  fix: str) -> list[Finding]:
    """One `palette.parts_differ` per part of `document` that doesn't match the table: its name isn't in it, or its length, row
    (its `row`, else its place in the list) or, when the table has `rgb`, its colours differ."""
    rows = {ramp.name: (row, ramp) for row, ramp in enumerate(table)}
    found: list[Finding] = []
    for place, part in enumerate(document.get("parts", [])):
        if not isinstance(part, dict) or not (part.get("materials") or part.get("rgb")):
            continue
        name = str(part.get("name"))
        where = Position(asset=asset, stage=stage, file=file, field=f"parts.{name}")
        if name not in rows:
            found.append(Finding(
                code="palette.parts_differ", position=where,
                message=f"{asset}'s {file} has the part '{name}', which the Project's ramp table doesn't",
                owner_action=f"Add it to the table with `kiripix ramps-add {asset} --parts {name}`, or take it out of the "
                             f"character's parts."))
            continue
        row, ramp = rows[name]
        differs: list[str] = []
        rgb = part.get("rgb", [])
        if len(rgb) != ramp.length:
            differs.append(f"length is {len(rgb)}, the table's is {ramp.length}")
        have_row = part.get("row", place)
        if have_row != row:
            differs.append(f"row is {have_row}, the table's is {row}")
        if ramp.rgb is not None and [list(c) for c in ramp.rgb] != [list(c) for c in rgb]:
            differs.append("rgb are not the table's colours")
        if differs:
            fields = [d.split(" ")[0] for d in differs]
            found.append(Finding(
                code="palette.parts_differ", position=where.model_copy(update={"field": f"parts.{name}.{','.join(fields)}"}),
                message=f"{asset}'s {file} part '{name}' differs from the Project's ramp table: {'; '.join(differs)}",
                fix=fix))
    return found


@register_project_check
def _check_parts_differ(project: Project, assets: list[Asset]) -> list[Finding]:
    """`palette.parts_differ` for every character whose `palette` is built, and every exported `character.json`."""
    table = project.settings.character.ramps
    if not table:
        return []
    found: list[Finding] = []
    cache = HashCache(project.state_dir)
    for asset in assets:
        if asset.kind != CHARACTER_KIND:
            continue
        try:
            graph = AssetGraph(project, asset, cache)
            palette = built_palette(graph)
            character = exported_character(graph)
        except KiripixError:
            continue
        if palette is not None:
            found.extend(part_findings(table, palette, asset.id, PALETTE_STAGE, PALETTE_FILE,
                                       f"kiripix run {asset.id} {PALETTE_STAGE}"))
        if character is not None:
            found.extend(part_findings(table, character, asset.id, EXPORT_STAGE, CHARACTER_FILE,
                                       f"kiripix run {asset.id} {EXPORT_STAGE}"))
    return found
