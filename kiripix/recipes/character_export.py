"""The character's `export` Stage (spec §6.3 and §9, ticket 0113): what the game gets, with nothing of Godot in it. It reads
`sheet`'s `sheet.json` and atlases only, and leaves in `out/export/`:

    color.png, normal.png   the two atlases, copied
    character.json          {"schema_version": 4, "asset": "character.hero",
                             "files": {"color": "color.png", "normal": "normal.png"},
                             "cell": {"width": 78, "height": 78}, "pivot": {"x": 39, "y": 72},   # from the cell's top left
                             "atlas": {"width": 858, "height": 936},
                             "directions": ["s", "sw", ...],
                             "clips": [{"name": "idle", "fps": 12, "loop": true, "stationary": true,
                                        "events": {"foot": [0, 5]},   # frames (the same in every direction) where a foot plants
                                        "directions": {"s": [{"index": 0, "rect": {"x": 0, "y": 0, "width": 78,
                                                                                     "height": 78}}, ...]}}],
                             "parts": [{"name": "skin", "materials": ["skin"], "row": 0, "shared": true,
                                        "indexes": [12, 3, 9], "rgb": [[r, g, b], ...]}],
                             "rows": [{"name": "skin", "length": 3}, {"name": "hair", "length": 3}]}

`parts` is each part's ramp, dark to light, from `palette`, in row order ([] without parts); `shared` is true when its colours
are the Project ramp table's. `rows` is `ramps.png`'s rows: the table's parts in its order, those the character lacks too, so it
is the same on every character of the Project; with no table, the character's own parts (ticket 0169).

The animation `<clip>_<direction>` of the game is a clip's frames in one direction. The Exporter (`kiripix.export`) turns
this into the engine's files.
"""

import json
import shutil
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import NeedsInput, StageFailure, StageRun
from kiripix.recipes.character_palette import PALETTE_FILE, PALETTE_SCHEMA_VERSION
from kiripix.recipes.clips import CLIPS_SCHEMA_VERSION
from kiripix.recipes.character_sheet import COLOR_ATLAS, NORMAL_ATLAS, SHEET_FILE, SHEET_SCHEMA_VERSION

# 2: `parts`, each swappable part's ramp from `palette` (`[]` without parts)
# 3: each part's `row` and `shared`, in row order, and `rows`, the Project ramp table's (ticket 0169); refused when older
# 4: each clip's `events`, from `clips` (ticket 0172)
CHARACTER_SCHEMA_VERSION = 4
CHARACTER_FILE = "character.json"
_NO_TARGET = "Set project under [export.godot] in kiripix.toml to the Godot project's folder."


def export_needs_input(run: StageRun) -> NeedsInput | None:
    if run.settings["export.godot"].get("project"):
        return None
    return NeedsInput("no Godot project to export into", owner_action=_NO_TARGET)


def _rows(palette: dict[str, Any]) -> list[dict[str, Any]]:
    """`ramps.png`'s rows, {name, length} in order: the Project ramp table the palette was built from, when it has one and the
    character has parts; else the character's own parts."""
    if palette["parts"] and palette.get("table"):
        return [{"name": str(r["name"]), "length": int(r["length"])} for r in palette["table"]]
    return [{"name": str(p["name"]), "length": len(p["rgb"])} for p in sorted(palette["parts"], key=lambda p: int(p["row"]))]


def run_character_export(run: StageRun) -> None:
    folder = run.upstream["sheet"]
    try:
        sheet: dict[str, Any] = json.loads((folder / SHEET_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"sheet has no {SHEET_FILE}; run it again", fix=f"kiripix run {run.asset_id} sheet --force") from None
    if sheet.get("schema_version") != SHEET_SCHEMA_VERSION:
        raise StageFailure(f"{SHEET_FILE} has schema_version {sheet.get('schema_version')}; this Kiripix reads "
                           f"{SHEET_SCHEMA_VERSION}", fix=f"kiripix run {run.asset_id} sheet --force")
    try:
        palette: dict[str, Any] = json.loads((run.upstream["palette"] / PALETTE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"palette has no {PALETTE_FILE}; run it again",
                           fix=f"kiripix run {run.asset_id} palette --force") from None
    if palette.get("schema_version") != PALETTE_SCHEMA_VERSION:
        raise StageFailure(f"{PALETTE_FILE} has schema_version {palette.get('schema_version')}; this Kiripix reads "
                           f"{PALETTE_SCHEMA_VERSION}", fix=f"kiripix run {run.asset_id} palette --force")
    try:
        built: dict[str, Any] = json.loads((run.upstream["clips"] / "clips.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure("clips has no clips.json; run it again", fix=f"kiripix run {run.asset_id} clips --force") from None
    if built.get("schema_version") != CLIPS_SCHEMA_VERSION:
        raise StageFailure(f"clips.json has schema_version {built.get('schema_version')}; this Kiripix reads "
                           f"{CLIPS_SCHEMA_VERSION}", fix=f"kiripix run {run.asset_id} clips --force")
    events = {str(c["name"]): c["events"] for c in built["clips"]}
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
        "clips": [{**c, "events": events.get(str(c["name"]), {"foot": []})} for c in sheet["clips"]],
        "parts": [{"name": p["name"], "materials": p["materials"], "row": p["row"], "shared": p["shared"],
                   "indexes": p["indexes"], "rgb": p["rgb"]} for p in sorted(palette["parts"], key=lambda p: int(p["row"]))],
        "rows": _rows(palette),
    }
    (run.output_dir / CHARACTER_FILE).write_text(json.dumps(character, indent=2) + "\n", encoding="utf-8")


def check_character_export(run: StageRun) -> list[Finding]:
    if run.settings["export.godot"].get("project"):
        return []
    return [Finding(code="export.no_target", message="no Godot project to export into",
                    position=Position(asset=run.asset_id, stage="export"), owner_action=_NO_TARGET)]
