"""A Wearable's `export` Stage (spec §6.3 and §9, ticket 0293): what the game gets, with nothing of Godot in it. It reads
`sheet`'s `sheet.json` and atlases and `palette`'s `palette.json`, and leaves in `out/export/`:

    color.png, normal.png, depth.png   the three atlases, copied (the body's cell, pivot and frame layout)
    wearable.json                      {"schema_version": 2, "asset": "wearable.hair", "body": "character.hero", "order": 30,
                                        "files": {"color": ..., "normal": ..., "depth": "depth.png"},
                                        "cell", "pivot", "atlas", "directions", "clips",   # as character.json
                                        "parts": [{"name", "materials", "row", "shared", "indexes", "rgb"}]}

The animation `<clip>_<direction>` of a Wearable is the body's. `order` is the default stacking order over the body (0); the
game stacks by it, or by `depth.png` (16 bit, 0 nearest) for an exact result. A Wearable has no outline: the game draws it once
on the stack. `kiripix.export` turns this into the engine's files, and refuses to export it before its body (`wearable.body_not_exported`).
"""

import json
import shutil
from typing import Any

from kiripix.checks import Finding
from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.character_export import check_character_export, export_needs_input
from kiripix.recipes.character_palette import PALETTE_FILE, PALETTE_SCHEMA_VERSION
from kiripix.recipes.character_sheet import COLOR_ATLAS, NORMAL_ATLAS, SHEET_FILE, SHEET_SCHEMA_VERSION
from kiripix.recipes.wearable_sheet import DEPTH_ATLAS

# 2: each clip's frames carry an `offset` and a trimmed `rect` (ticket 0308); no migration: a Stage's rebuilt output, refused when old
WEARABLE_SCHEMA_VERSION = 2
WEARABLE_FILE = "wearable.json"

__all__ = ["WEARABLE_FILE", "WEARABLE_SCHEMA_VERSION", "check_wearable_export", "export_needs_input", "run_wearable_export"]


def _read(run: StageRun, stage: str, name: str, version: int) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads((run.upstream[stage] / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"{stage} has no {name}; run it again", fix=f"kiripix run {run.asset_id} {stage} --force") from None
    if document.get("schema_version") != version:
        raise StageFailure(f"{name} has schema_version {document.get('schema_version')}; this Kiripix reads {version}",
                           fix=f"kiripix run {run.asset_id} {stage} --force")
    return document


def run_wearable_export(run: StageRun) -> None:
    sheet = _read(run, "sheet", SHEET_FILE, SHEET_SCHEMA_VERSION)
    palette = _read(run, "palette", PALETTE_FILE, PALETTE_SCHEMA_VERSION)
    for name in (COLOR_ATLAS, NORMAL_ATLAS, DEPTH_ATLAS):
        run.check_cancel()
        shutil.copyfile(run.upstream["sheet"] / name, run.output_dir / name)
    wearable = {
        "schema_version": WEARABLE_SCHEMA_VERSION,
        "asset": run.asset_id,
        "body": str(run.asset_params["body"]),
        "order": int(sheet["order"]),
        "files": {"color": COLOR_ATLAS, "normal": NORMAL_ATLAS, "depth": DEPTH_ATLAS},
        "cell": sheet["cell"],
        "pivot": sheet["pivot"],
        "atlas": sheet["atlas"],
        "directions": sheet["directions"],
        "clips": sheet["clips"],
        "parts": [{"name": p["name"], "materials": p["materials"], "row": p["row"], "shared": p["shared"],
                   "indexes": p["indexes"], "rgb": p["rgb"]} for p in sorted(palette["parts"], key=lambda p: int(p["row"]))],
    }
    (run.output_dir / WEARABLE_FILE).write_text(json.dumps(wearable, indent=2) + "\n", encoding="utf-8")


def check_wearable_export(run: StageRun) -> list[Finding]:
    return check_character_export(run)
