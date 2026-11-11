"""The character's `export` Stage (spec §6.3 and §9, ticket 0113): what the game gets, with nothing of Godot in it. It reads
`sheet`'s `sheet.json` and atlases only, and leaves in `out/export/`:

    color.png, normal.png   the two atlases, copied
    character.json          {"schema_version": 1, "asset": "character.hero",
                             "files": {"color": "color.png", "normal": "normal.png"},
                             "cell": {"width": 78, "height": 78}, "pivot": {"x": 39, "y": 72},   # from the cell's top left
                             "atlas": {"width": 858, "height": 936},
                             "directions": ["s", "sw", ...],
                             "clips": [{"name": "idle", "fps": 12, "loop": true, "stationary": true,
                                        "directions": {"s": [{"index": 0, "rect": {"x": 0, "y": 0, "width": 78,
                                                                                     "height": 78}}, ...]}}]}

The animation `<clip>_<direction>` of the game is a clip's frames in one direction. The Exporter (`kiripix.export`) turns
this into the engine's files.
"""

import json
import shutil
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import NeedsInput, StageFailure, StageRun
from kiripix.recipes.character_sheet import COLOR_ATLAS, NORMAL_ATLAS, SHEET_FILE, SHEET_SCHEMA_VERSION

CHARACTER_SCHEMA_VERSION = 1
CHARACTER_FILE = "character.json"
_NO_TARGET = "Set project under [export.godot] in kiripix.toml to the Godot project's folder."


def export_needs_input(run: StageRun) -> NeedsInput | None:
    if run.settings["export.godot"].get("project"):
        return None
    return NeedsInput("no Godot project to export into", owner_action=_NO_TARGET)


def run_character_export(run: StageRun) -> None:
    folder = run.upstream["sheet"]
    try:
        sheet: dict[str, Any] = json.loads((folder / SHEET_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"sheet has no {SHEET_FILE}; run it again", fix=f"kiripix run {run.asset_id} sheet --force") from None
    if sheet.get("schema_version") != SHEET_SCHEMA_VERSION:
        raise StageFailure(f"{SHEET_FILE} has schema_version {sheet.get('schema_version')}; this Kiripix reads "
                           f"{SHEET_SCHEMA_VERSION}", fix=f"kiripix run {run.asset_id} sheet --force")
    for name in (COLOR_ATLAS, NORMAL_ATLAS):
        run.check_cancel()
        shutil.copyfile(folder / name, run.output_dir / name)
    character = {
        "schema_version": CHARACTER_SCHEMA_VERSION,
        "asset": run.asset_id,
        "files": {"color": COLOR_ATLAS, "normal": NORMAL_ATLAS},
        "cell": sheet["cell"],
        "pivot": sheet["pivot"],
        "atlas": sheet["atlas"],
        "directions": sheet["directions"],
        "clips": sheet["clips"],
    }
    (run.output_dir / CHARACTER_FILE).write_text(json.dumps(character, indent=2) + "\n", encoding="utf-8")


def check_character_export(run: StageRun) -> list[Finding]:
    if run.settings["export.godot"].get("project"):
        return []
    return [Finding(code="export.no_target", message="no Godot project to export into",
                    position=Position(asset=run.asset_id, stage="export"), owner_action=_NO_TARGET)]
