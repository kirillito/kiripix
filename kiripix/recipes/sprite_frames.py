"""The sprite Kind's `frames` Stage (spec §6.4, ticket 0179): the imported sheets cut into `<clip>/<dir>/<NNN>` frames at source
resolution.

A sheet is a Source file in `src/sheets/` (ticket 0178), named by the start of its hash. A PNG needs a `sheet` Decision that says
how its cells map to a clip's directions and frames (`slice_grid`); a ZIP is read by the naming rule in `sprite_names` (PixelLab's
layout, provisional pending ticket 0175), and a `sheet` Decision may rename its clips. A `clip` Decision sets a clip's frame rate,
loop and stationary flags; without one a clip gets 8 fps, loops, and is stationary when it has a single frame.

Output in `work/frames/`: `color/<clip>/<dir>/<NNN>.png` (RGBA, as the sheet has them) and `frames.json`:

    {"schema_version": 1, "directions": ["s", "w", "n", "e"], "sheets": ["1a2b3c..."],
     "clips": [{"name": "idle", "fps": 8, "loop": true, "stationary": true, "raw": ["breathing-idle"],
                "directions": {"s": [{"index": 0, "file": "color/idle/s/000.png", "sheet": "1a2b3c...",
                                      "source": "animations/breathing-idle/south/frame_000.png"}]}}],
     "unplaced": [{"sheet": "...", "path": "readme/x.png", "why": "..."}],
     "duplicates": [{"clip": "idle", "direction": "s", "frame": 0, "sheet": "...", "source": "...", "other": "..."}]}

A direction the sprite doesn't ask for is left out. Nothing is mirrored: a direction a clip lacks is `frames.direction_missing`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
    from PIL import Image
else:
    np = lazy_module("numpy")
    Image = lazy_module("PIL.Image")

from kiripix.checks import Finding, Position
from kiripix.ops import slice_grid
from kiripix.recipes.base import CurrentDecision, DecisionSpec, NeedsInput, ParamSpec, StageFailure, StageRun
from kiripix.recipes.clips import DIRECTIONS, NAME_PATTERN
from kiripix.recipes.common import read_rgba, write_rgba
from kiripix.recipes.sprite_names import ROTATION_CLIP, place, snake_case

SCHEMA_VERSION = 1
FRAMES_FILE = "frames.json"
SHEETS_DIR = "src/sheets/"
DEFAULT_FPS = 8
FOUR = ("s", "w", "n", "e")  # the compass order, as the character's 4 directions

_NAME = re.compile(NAME_PATTERN)

DIRECTIONS_PARAM = ParamSpec(
    name="directions", type="choice", choices=["8", "4", "1"], default="4",
    description="How many directions the sprite has: 8 (s sw w nw n ne e se), 4 (s w n e) or 1 (s, a static figure). A clip "
                "that lacks one is frames.direction_missing; nothing is mirrored.")

_CLIP_NAME = {"type": "string", "pattern": NAME_PATTERN}
SHEET = DecisionSpec(
    name="sheet",
    description="How a sheet is cut. For a PNG: `file` (the sheet's name, the start of its hash), `clip`, `layout` (`rows`: one "
                "direction per row, its frames across; `columns`: one direction per column, its frames down), `directions` (in "
                "that order, as s sw w nw n ne e se) and `frames` (the count): the cell is the sheet's size divided by those. For "
                "a ZIP: `file` and, to rename clips, `clips` ({\"breathing-idle\": \"idle\"}, their folder's name to ours). A "
                "ZIP's names are read by rule, so it needs no Decision. Deciding a sheet again replaces it; `undo` brings the "
                "old one back.",
    entry_schema={
        "oneOf": [
            {"type": "object",
             "properties": {"file": {"type": "string", "minLength": 1}, "clip": _CLIP_NAME,
                            "layout": {"enum": ["rows", "columns"]},
                            "directions": {"type": "array", "items": {"enum": list(DIRECTIONS)}, "minItems": 1,
                                           "uniqueItems": True},
                            "frames": {"type": "integer", "minimum": 1}},
             "required": ["file", "clip", "layout", "directions", "frames"], "additionalProperties": False},
            {"type": "object",
             "properties": {"file": {"type": "string", "minLength": 1},
                            "clips": {"type": "object", "additionalProperties": _CLIP_NAME}},
             "required": ["file"], "additionalProperties": False},
        ]
    },
)

CLIP = DecisionSpec(
    name="clip",
    description="One clip's playback: `name` (an ID in the game: lower-case snake_case, frozen at its first export, never ending "
                "in a direction suffix), `fps` (default 8), `loop` (default true) and `stationary` (default: true when the clip "
                "has one frame), which holds the clip to the sheet's pivot-drift Check. Deciding a clip again under its name "
                "changes it; `undo` brings the old one back.",
    entry_schema={
        "type": "object",
        "properties": {"name": _CLIP_NAME, "fps": {"type": "integer", "minimum": 1}, "loop": {"type": "boolean"},
                       "stationary": {"type": "boolean"}},
        "required": ["name"], "additionalProperties": False,
    },
)


def expected_directions(params: dict[str, Any]) -> list[str]:
    """The directions the sprite asks for, in the compass order."""
    count = str(params.get("directions", "4"))
    return list(DIRECTIONS) if count == "8" else list(FOUR) if count == "4" else ["s"]


def sheets_of(run: StageRun) -> dict[str, Path]:
    """The imported sheets by name (the start of their hash)."""
    return {Path(name).stem: path for name, path in sorted(run.files.items()) if name.startswith(SHEETS_DIR)}


def resolve(sheets: dict[str, Path], reference: str) -> str | None:
    """The name of the sheet a `file` Decision names: its name, its file name, or a start of its hash that only one has."""
    if reference in sheets:
        return reference
    for name, path in sheets.items():
        if path.name == reference:
            return name
    starts = [name for name in sheets if name.startswith(reference)]
    return starts[0] if len(starts) == 1 else None


def latest_by_name(decisions: tuple[CurrentDecision, ...], kind: str, key: str) -> dict[str, CurrentDecision]:
    """The latest Decision of `kind` for each value of `data[key]`, in the order the values first appeared."""
    latest: dict[str, CurrentDecision] = {}
    for decision in decisions:
        if decision.name == kind:
            latest[str(decision.data[key])] = decision
    return latest


def _size(path: Path) -> str:
    try:
        with Image.open(path) as image:
            return f"{image.width} x {image.height} px"
    except OSError:
        return "unreadable"


def frames_needs_input(run: StageRun) -> NeedsInput | None:
    sheets = sheets_of(run)
    if not sheets:
        return NeedsInput("no sheets imported", command=f"kiripix import {run.asset_id} <file.png|file.zip> --role sheet")
    decided = {resolve(sheets, str(d.data["file"])) for d in run.decisions if d.name == SHEET.name}
    undecided = [name for name, path in sheets.items() if path.suffix == ".png" and name not in decided]
    if not undecided:
        return None
    shown = "; ".join(f"{name} ({_size(sheets[name])})" for name in undecided)
    return NeedsInput(
        f"say how the sheet's rows map to directions: {shown}",
        owner_action="Decide how each PNG sheet is cut: a `sheet` Decision on frames with `file`, `clip`, `layout` (rows or "
                     "columns), `directions` in that order and `frames`, such as kiripix decide "
                     f"{run.asset_id} frames --decision "
                     "'{\"decision\": \"sheet\", \"data\": {\"file\": \"" + undecided[0] + "\", \"clip\": \"idle\", "
                     "\"layout\": \"rows\", \"directions\": [\"s\", \"w\", \"n\", \"e\"], \"frames\": 1}}'")


class _Frames:
    """The frames found, by clip and direction and then by the number the source gave them. A rotation (a direction with no
    animation, the clip `idle`) is kept apart and joins only where no animation gave that clip the direction."""

    def __init__(self) -> None:
        self.found: dict[str, dict[str, dict[int, tuple[np.ndarray, str, str]]]] = {}
        self.rotations: list[tuple[str, str, str, int, np.ndarray, str, str]] = []
        self.raw: dict[str, list[str]] = {}
        self.duplicates: list[dict[str, Any]] = []
        self.dropped = 0

    def add(self, clip: str, raw: str, direction: str, number: int, image: np.ndarray, sheet: str, source: str,
            rotation: bool = False) -> None:
        if rotation:
            self.rotations.append((clip, raw, direction, number, image, sheet, source))
            return
        self._put(clip, raw, direction, number, image, sheet, source)

    def _put(self, clip: str, raw: str, direction: str, number: int, image: np.ndarray, sheet: str, source: str) -> None:
        if raw not in self.raw.setdefault(clip, []):
            self.raw[clip].append(raw)
        slot = self.found.setdefault(clip, {}).setdefault(direction, {})
        if number in slot:
            self.duplicates.append({"clip": clip, "direction": direction, "frame": number, "sheet": sheet, "source": source,
                                    "other": f"{slot[number][1]}:{slot[number][2]}"})
            return
        slot[number] = (image, sheet, source)

    def join_rotations(self) -> None:
        for clip, raw, direction, number, image, sheet, source in self.rotations:
            if direction not in self.found.get(clip, {}):
                self._put(clip, raw, direction, number, image, sheet, source)
            else:
                self.dropped += 1  # an animation gave the direction


def _cut_png(run: StageRun, found: _Frames, name: str, path: Path, data: dict[str, Any], wanted: list[str]) -> None:
    directions, count, layout = list(data["directions"]), int(data["frames"]), str(data["layout"])
    columns, rows = (count, len(directions)) if layout == "rows" else (len(directions), count)
    try:
        cells = slice_grid(read_rgba(path), columns, rows)
    except ValueError as error:
        raise StageFailure(f"sheet {name}: {error}", code="frames.sheet_size",
                           fix=f"kiripix undo {run.asset_id} frames") from None
    clip = str(data["clip"])
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            direction, number = (directions[r], c) if layout == "rows" else (directions[c], r)
            if direction in wanted:
                found.add(clip, clip, direction, number, cell, name, f"row {r}, column {c}")
            else:
                found.dropped += 1


def _read_zip(run: StageRun, found: _Frames, unplaced: list[dict[str, str]], name: str, path: Path,
              renames: dict[str, str], wanted: list[str]) -> None:
    import zipfile

    with zipfile.ZipFile(path) as archive:
        for info in sorted(archive.infolist(), key=lambda i: i.filename):
            run.check_cancel()
            if info.is_dir():
                continue
            where = place(info.filename)
            if where is None:
                unplaced.append({"sheet": name, "path": info.filename,
                                 "why": "no direction word in its path (south, south-east, ... or s, se, ...)"})
                continue
            if where.direction not in wanted:
                found.dropped += 1
                continue
            with archive.open(info) as entry:
                image = Image.open(entry)
                image.load()
                pixels = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
            raw = where.animation if where.animation is not None else ROTATION_CLIP
            clip = renames.get(raw) or renames.get(snake_case(raw)) or snake_case(raw)
            found.add(clip, raw, where.direction, where.frame, pixels, name, info.filename,
                      rotation=where.animation is None)


def run_frames(run: StageRun) -> None:
    wanted = expected_directions(run.params)
    sheets = sheets_of(run)
    decided = latest_by_name(run.decisions, SHEET.name, "file")
    cuts: dict[str, dict[str, Any]] = {}
    for reference, decision in decided.items():
        name = resolve(sheets, reference)
        if name is None:
            raise StageFailure(f"the sheet Decision names {reference}, which is not an imported sheet "
                               f"(the sheets are {', '.join(sheets) or 'none'})", code="frames.sheet_unknown",
                               fix=f"kiripix undo {run.asset_id} frames")
        cuts[name] = decision.data
    found = _Frames()
    unplaced: list[dict[str, str]] = []
    for index, (name, path) in enumerate(sheets.items()):
        run.progress(index, len(sheets), f"reading sheet {name}")
        run.check_cancel()
        data = cuts.get(name)
        if path.suffix == ".zip":
            _read_zip(run, found, unplaced, name, path, dict(data.get("clips", {})) if data else {}, wanted)
        elif data is not None:
            _cut_png(run, found, name, path, data, wanted)
    found.join_rotations()
    if not found.found:
        shown = "; ".join(f"{u['sheet']}:{u['path']}" for u in unplaced[:5])
        raise StageFailure("the sheets give no frames" + (f"; the rule can't place {shown}" if unplaced else ""),
                           code="frames.unknown_direction",
                           owner_action="Name the ZIP's entries with a direction (south, south-east, ... or s, se, ...) in a "
                                        "folder per animation, or cut a PNG with a `sheet` Decision.")
    clip_decisions = latest_by_name(run.decisions, CLIP.name, "name")
    clips: list[dict[str, Any]] = []
    for clip in sorted(found.found):
        said = clip_decisions[clip].data if clip in clip_decisions else {}
        by_direction = found.found[clip]
        one_frame = max(len(slot) for slot in by_direction.values()) == 1
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction in DIRECTIONS:
            slot = by_direction.get(direction)
            if slot is None:
                continue
            listed = []
            for index, number in enumerate(sorted(slot)):
                run.check_cancel()
                image, sheet, source = slot[number]
                file = f"color/{clip}/{direction}/{index:03d}.png"
                (run.output_dir / file).parent.mkdir(parents=True, exist_ok=True)
                write_rgba(run.output_dir / file, image)
                listed.append({"index": index, "file": file, "sheet": sheet, "source": source})
            directions[direction] = listed
        clips.append({"name": clip, "fps": int(said.get("fps", DEFAULT_FPS)), "loop": bool(said.get("loop", True)),
                      "stationary": bool(said.get("stationary", one_frame)), "raw": found.raw[clip],
                      "directions": directions})
    document = {"schema_version": SCHEMA_VERSION, "directions": wanted, "sheets": list(sheets), "clips": clips,
                "unplaced": unplaced, "duplicates": found.duplicates}
    (run.output_dir / FRAMES_FILE).write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    if found.dropped:
        run.notes.append(f"left out {found.dropped} frames: directions the sprite doesn't ask for, or rotations an animation replaces")


def check_frames(run: StageRun) -> list[Finding]:
    """`frames.direction_missing`, `frames.frame_count`, `frames.unknown_direction`, `clips.bad_name`, `clips.duplicate_name`."""
    try:
        document = json.loads((run.output_dir / FRAMES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    asset, findings = run.asset_id, []

    def at(field: str | None = None) -> Position:
        return Position(asset=asset, stage="frames", field=field)

    wanted = list(document["directions"])
    for clip in document["clips"]:
        name, present = str(clip["name"]), clip["directions"]
        if not _NAME.match(name):
            findings.append(Finding(
                code="clips.bad_name", message=f"the clip name {name!r} must be lower-case snake_case and not end in a "
                                               "direction suffix (_s, _sw, _w, _nw, _n, _ne, _e, _se)",
                position=at(name),
                owner_action=f"Rename it with a `sheet` Decision's `clips` (their name to ours) on {asset} frames; its names are "
                             f"{', '.join(clip['raw'])}."))
        for direction in wanted:
            if direction not in present:
                findings.append(Finding(
                    code="frames.direction_missing",
                    message=f"the clip {name} has no frames for direction {direction} (the sprite asks for "
                            f"{', '.join(wanted)}); a direction is never mirrored",
                    position=at(f"{name}/{direction}"),
                    owner_action=f"Import the {direction} frames of {name} (kiripix import {asset} <file> --role sheet, then "
                                 f"a `sheet` Decision for a PNG), or ask for fewer directions: kiripix set {asset} frames "
                                 "directions=<8, 4 or 1>."))
        counts = {d: len(listed) for d, listed in present.items()}
        if len(set(counts.values())) > 1:
            shown = ", ".join(f"{d} {n}" for d, n in counts.items())
            findings.append(Finding(
                code="frames.frame_count", severity="warning", position=at(name),
                message=f"the clip {name} has different frame counts in its directions ({shown})",
                owner_action=f"Import the missing frames of {name}, or accept the difference; the game plays each direction "
                             "at its own length."))
    for item in document["duplicates"]:
        findings.append(Finding(
            code="clips.duplicate_name", position=at(f"{item['clip']}/{item['direction']}"),
            message=f"the clip {item['clip']} gets frame {item['frame']} of direction {item['direction']} twice: "
                    f"{item['sheet']}:{item['source']} and {item['other']}, so the first is kept",
            owner_action="Rename one of the two clips with a `sheet` Decision's `clips`, or remove the extra sheet: "
                         "the same clip name must not come from two sources."))
    for item in document["unplaced"]:
        findings.append(Finding(
            code="frames.unknown_direction", severity="warning",
            message=f"the ZIP entry {item['path']} of sheet {item['sheet']} can't be placed: {item['why']}",
            position=Position(asset=asset, stage="frames", file=f"{item['sheet']}:{item['path']}"),
            owner_action="Name the entry with a direction (south, south-east, ... or s, se, ...), or leave it out of the ZIP; "
                         "it isn't used."))
    return findings
