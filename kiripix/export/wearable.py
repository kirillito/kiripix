"""A Wearable's built export (`out/export/`): the engine-free files its `export` Stage leaves for the Exporter (ticket 0293)."""

import json
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.core.errors import ExitCode, KiripixError
from kiripix.core.settings import migrate_character_record
from kiripix.core.graph import AssetGraph
from kiripix.export.manifest import read_manifest
from kiripix.export.built import EXPORT_STAGE, read_built_record
from kiripix.export.target import GodotTarget
from kiripix.recipes.wearable_export import WEARABLE_FILE, WEARABLE_SCHEMA_VERSION

COLOR_FILE = "color.png"
NORMAL_FILE = "normal.png"
DEPTH_FILE = "depth.png"


def read_wearable(graph: AssetGraph) -> dict[str, Any]:
    return read_built_record(graph, "wearable", WEARABLE_FILE, WEARABLE_SCHEMA_VERSION)


def body_exported(wearable: dict[str, Any], target: GodotTarget, planned: dict[str, bytes] | None = None) -> None:
    """Refuse unless the Wearable's body is in the game, exported with the same cell and pivot: the game stacks the two
    pixel for pixel. The body's Manifest must list it as exported, and its `character.json` in the game (the file the game
    reads) must have the Wearable's cell and pivot. `planned` is the files, by `res://` path, that the same export call is
    about to write: the body exported in the same `--all` counts, with the `character.json` it will write."""
    body, asset = str(wearable["body"]), str(wearable["asset"])
    kind, name = body.split(".", 1)
    shown = target.manifest(body)
    manifest = read_manifest(target.path(shown), shown)
    record = f"{target.root}/{kind}/{name}/character.json"
    coming = (planned or {}).get(record)
    position = Position(asset=asset, stage=EXPORT_STAGE)
    if coming is None and (manifest is None or not manifest.exported):
        raise KiripixError([Finding(
            code="wearable.body_not_exported", message=f"{asset}'s body {body} hasn't been exported to the game",
            position=position, fix=f"kiripix export {body}")], ExitCode.ERROR)
    problem, fix = "", f"kiripix export {body}"
    try:
        theirs = migrate_character_record(json.loads(
            coming.decode("utf-8") if coming is not None else target.path(record).read_text(encoding="utf-8")))
        if theirs["cell"] != wearable["cell"] or theirs["pivot"] != wearable["pivot"]:
            problem = f"({wearable['cell']['width']} x {wearable['cell']['height']} px)"
        else:  # each clip's own cell and pivot, and the same clips (ticket 0311)
            body_clips = {str(c["name"]): c for c in theirs["clips"]}
            mine = {str(c["name"]) for c in wearable["clips"]}
            for clip in wearable["clips"]:
                found = body_clips.get(str(clip["name"]))
                if found is None or found["cell"] != clip["cell"] or found["pivot"] != clip["pivot"]:
                    problem = f"(clip {clip['name']}: {clip['cell']['width']} x {clip['cell']['height']} px)"
                    break
            missing = sorted(set(body_clips) - mine)
            if not problem and missing:
                problem, fix = f"(clip {missing[0]} is the body's and not the Wearable's)", f"kiripix run {asset}"
    except (OSError, ValueError, KeyError, TypeError, KiripixError):  # UnicodeDecodeError is a ValueError; KiripixError: too old
        problem = f"({wearable['cell']['width']} x {wearable['cell']['height']} px)"
    if problem:
        raise KiripixError([Finding(
            code="wearable.body_not_exported",
            message=f"{asset}'s body {body} was exported with another cell or pivot than the Wearable's "
                    f"{problem}, or its character.json is missing, so the two wouldn't lie on each other",
            position=position, fix=fix)], ExitCode.ERROR)
