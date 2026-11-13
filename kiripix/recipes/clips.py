"""The character's `clips` Stage (spec §6.3, ticket 0103): each `clip` Decision resolved against its source, an action of the
rigged Model or an animation file added with `--role clip-source`, into `clips.json`: the frame range, the frame rates, the
loop and stationary flags, whether the root travels, and the frame numbers a render samples.

A clip's `source` is a clip-source file's stem (`walk` for `src/clips/walk.<hash>.fbx`; `walk/<action>` when the file has
several actions), else the name of an action in the rig's file (the Model's own `model.blend`, or the rigged file the Mixamo
round trip brought back). A clip-source file wins over an action of the same name.

Blender is asked once per file, for its actions, how far the root travels in each, and the foot bones' height and speed at
each frame; the Stage does the rest, among it the frames where a foot plants (`find_plants`, ticket 0172), listed per clip in
`events`: the same on every direction, as a direction is only the camera's view of one action.
"""

import hashlib
import json
import math
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import CurrentDecision, DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.blender_launcher import launch

# 2: each clip's `events` ({"foot": [index into `frames`, ...]}, ticket 0172); refused when older
CLIPS_SCHEMA_VERSION = 2
PLANT_HEIGHT = 0.03  # a foot within this fraction of the rig's height of the clip's lowest foot point is on the ground
PLANT_SPEED = 0.25  # with root motion, a planted foot moves less than this many rig heights a second
CLIP_SOURCES = "src/clips/"
EYELIDS = ("blink", "wink_left", "wink_right")  # a clip's frames with closed eyes: both, the Model's left, its right
ROOT_MOTION_RATIO = 0.1  # the root travels more than this fraction of the rig's height: root motion
HASH_LENGTH = 16  # hex digits of the SHA-256, as a Variant's name

DIRECTIONS = ("s", "sw", "w", "nw", "n", "ne", "e", "se")  # the 8 suffixes a SpriteFrames animation ends with (Q5)
# A clip ID is lower-case [a-z0-9_] and never ends in a direction: `walk_sw` would read as `walk` facing sw.
NAME_PATTERN = rf"^(?!.*_({'|'.join(DIRECTIONS)})$)[a-z0-9_]+$"

CLIP = DecisionSpec(
    name="clip",
    description="One named clip. `name` is the clip's ID in the game: lower-case snake_case, frozen at its first export, and "
                "never ending in a direction suffix (_s, _sw, _w, _nw, _n, _ne, _e, _se). `source` is a clip-source file's "
                "stem or an action of the rigged Model; `start` and `end` are frames of that action; `fps` is the "
                "clip's frame rate in the game; `stationary` (default false) marks a clip whose feet must not move, which "
                "the sheet's pivot-drift Check then holds it to. `speed` (default 1) plays the action that many times "
                "faster, so the clip has fewer frames at the same `fps`. `still` makes the clip the one pose at `start`, "
                "held for that many frames (`end` is not read): a standing idle. `blink` lists the clip's frames, from 0, "
                "that `finish` draws with the eyes closed when it stamps them; `wink_left` and `wink_right` list the "
                "frames with only the Model's left or right eye closed. Deciding a clip again under a name it "
                "already has changes that clip, keeping its name and so its IDs in the game; `undo` brings the old frames "
                "back.",
    entry_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "pattern": NAME_PATTERN},
            "source": {"type": "string", "minLength": 1},
            "start": {"type": "integer", "minimum": 0},
            "end": {"type": "integer", "minimum": 0},
            "fps": {"type": "integer", "minimum": 1},
            "loop": {"type": "boolean"},
            "stationary": {"type": "boolean", "default": False},
            "speed": {"type": "number", "exclusiveMinimum": 0, "default": 1},
            "still": {"type": "integer", "minimum": 1},
            "blink": {"type": "array", "items": {"type": "integer", "minimum": 0}, "uniqueItems": True},
            "wink_left": {"type": "array", "items": {"type": "integer", "minimum": 0}, "uniqueItems": True},
            "wink_right": {"type": "array", "items": {"type": "integer", "minimum": 0}, "uniqueItems": True},
        },
        "required": ["name", "source", "start", "end", "fps", "loop"],
        "additionalProperties": False,
    },
)

_NAME = re.compile(NAME_PATTERN)


def latest_clips(decisions: Iterable[CurrentDecision]) -> list[CurrentDecision]:
    """The clips, one Decision per name: a `clip` Decision under a name an earlier one has replaces it (ticket 0156), so
    the latest wins and the clip keeps the earlier one's place. The earlier one stays current in the journal, which is
    why `undo` of the new one brings it back."""
    latest: dict[str, CurrentDecision] = {}
    for decision in decisions:
        if decision.name == CLIP.name:
            latest[str(decision.data["name"])] = decision  # a dict keeps the first insertion's place
    return list(latest.values())


def clip_decisions(run: StageRun) -> list[CurrentDecision]:
    """The clips of a run. Every reader of the clips in a Stage goes through here."""
    return latest_clips(run.decisions)


def clips_needs_input(run: StageRun) -> NeedsInput | None:
    if clip_decisions(run):
        return None
    # Which animations the game plays, and which frames of which action each one is, is the owner's choice, so this is an
    # owner_action, not a command an agent could fill in with guessed values (the M3 acceptance run, 2026-11-11).
    return NeedsInput(
        "no clips: add a `clip` Decision for each animation the game plays "
        "(name, source, start, end, fps, loop; stationary optional)",
        owner_action=f"Choose the animations the game plays: one `clip` Decision on `clips` each, with its name, source, "
                     f"start and end frames, frame rate in the game, and whether it loops. {_sources_known(run)}")


def _sources_known(run: StageRun) -> str:
    """The sources a clip can name, as far as is known without reading a file in Blender."""
    known = [f"clip source {stem}" for stem in sorted(_clip_files(run))]
    try:
        rig = json.loads((run.upstream["rig"] / "rig.json").read_text(encoding="utf-8"))
        if rig["source"] == "rigged":
            known.append(f"the rigged file's actions (kiripix probe inspect {run.asset_id} rigged lists them)")
        else:
            model = json.loads((run.upstream["model"] / "model.json").read_text(encoding="utf-8"))
            known += [f"action {a['name']} (frames {a['start']} to {a['end']})" for a in model["actions"]]
    except (OSError, ValueError, KeyError):
        pass
    return f"Sources: {'; '.join(known)}." if known else "Import an animation file as a clip source first."


def _clip_files(run: StageRun) -> dict[str, Path]:
    return {Path(Path(name).stem).stem: path for name, path in sorted(run.files.items()) if name.startswith(CLIP_SOURCES)}


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_LENGTH]


def sample_frames(start: int, end: int, source_fps: float, fps: int, loop: bool, speed: float = 1.0) -> list[float | int]:
    """The frames of the action a render samples, `fps` a second, the action playing `speed` times as fast. A looping clip
    ends before `end`, which is its first pose again; a clip that doesn't loop ends on it. A frame that isn't a whole number
    is a sub-frame between two keys."""
    step = source_fps * speed / fps
    span = end - start
    count = max(1, round(span / step)) if loop else math.floor(span / step + 1e-9) + 1
    frames: list[float | int] = []
    for index in range(count):
        frame = round(start + index * step, 3)
        frames.append(int(frame) if frame == int(frame) else frame)
    return frames


def _at(frames: list[float], values: list[float], frame: float) -> float:
    """`values` at `frame`, linear between the two samples round it, and the end sample outside them."""
    if frame <= frames[0]:
        return values[0]
    for index in range(1, len(frames)):
        if frame <= frames[index]:
            span = frames[index] - frames[index - 1]
            weight = (frame - frames[index - 1]) / span if span else 1.0
            return values[index - 1] + (values[index] - values[index - 1]) * weight
    return values[-1]


def find_plants(feet: dict[str, Any], rig_height: float, start: int, end: int, game_frames: list[float | int], loop: bool,
                root_motion: bool) -> list[int]:
    """The indexes into `game_frames` where a foot plants. `feet` is `read_actions`' `feet` of the action.

    A foot is on the ground at a game frame when its height is within `PLANT_HEIGHT` of the rig's height above the clip's
    lowest foot point (either foot, within the clip's `start` and `end`) and, with root motion, when it also moves slower than
    `PLANT_SPEED` rig heights a second (with the root in place, the planted foot slides back at the walk's speed, so speed says
    nothing). A plant is the first frame of a run on the ground where the foot stops falling: the next frame is not lower. A
    loop's run goes on over the seam, and a foot on the ground all clip long, an idle's, never plants."""
    sides = [side for side in ("left", "right") if side in feet]
    frames = [float(f) for f in feet.get("frames", [])]
    if not sides or not frames or rig_height <= 0 or not game_frames:
        return []
    inside = [i for i, f in enumerate(frames) if start <= f <= end] or list(range(len(frames)))
    lowest = min(feet[side]["z"][i] for side in sides for i in inside)
    plants: set[int] = set()
    count = len(game_frames)
    for side in sides:
        heights = [_at(frames, feet[side]["z"], float(f)) for f in game_frames]
        speeds = [_at(frames, feet[side]["speed"], float(f)) for f in game_frames]
        down = [h <= lowest + PLANT_HEIGHT * rig_height and (not root_motion or s <= PLANT_SPEED * rig_height)
                for h, s in zip(heights, speeds, strict=True)]
        if all(down):
            continue
        for i in range(count):
            before = down[(i - 1) % count] if loop else (down[i - 1] if i else False)
            if not down[i] or before:
                continue
            j = i  # the run's first frame where the next is not lower: where the foot has come to rest
            while j + 1 < count and down[j + 1] and heights[j + 1] < heights[j] - 1e-9:
                j += 1
            plants.add(j)
    return sorted(plants)


def _read(run: StageRun, cache: dict[Path, dict[str, Any]], path: Path, root: list[str],
          feet: dict[str, str]) -> dict[str, Any]:
    if path not in cache:
        run.check_cancel()
        cache[path] = launch(run, "read_actions", {"input": str(path), "root": root, "feet": feet})
    return cache[path]


def _rig(run: StageRun) -> tuple[Path, dict[str, Any]]:
    path = run.upstream["rig"] / "rig.json"
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if document["source"] == "rigged":
        file = run.asset_dir / "src" / "rigged" / document["file"]
    else:
        file = run.upstream["model"] / "model.blend"
    return file, document


def _action(found: dict[str, Any], wanted: str | None, stem: str) -> tuple[dict[str, Any] | None, str]:
    """The action of a read file that a source names, or None with why not."""
    actions = {a["name"]: a for a in found["actions"]}
    if wanted is not None:
        if wanted in actions:
            return actions[wanted], ""
        short = [a for name, a in actions.items() if name.split("|")[-1] == wanted]  # FBX: `Armature|Armature|idle`
        if len(short) == 1:
            return short[0], ""
        return None, f"has no action {wanted} (its actions are {', '.join(actions) or 'none'})"
    if len(actions) == 1:
        return next(iter(actions.values())), ""
    if not actions:
        return None, "has no action"
    return None, f"has several actions ({', '.join(actions)}): name one as {stem}/<action>"


def run_clips(run: StageRun) -> None:
    decisions = clip_decisions(run)
    names = [str(d.data["name"]) for d in decisions]
    bad = sorted(n for n in names if not _NAME.match(n))
    if bad:
        raise StageFailure(
            f"clip names must be lower-case snake_case and not end in a direction suffix: {', '.join(bad)}",
            code="clips.bad_name",
            fix=f"kiripix undo {run.asset_id} clips")  # then decide the clip again with a valid name

    rig_file, rig = _rig(run)
    root = ["root", str(rig["mapping"].get("hips", "hips"))]
    mapping = rig["mapping"]
    feet = {side: str(mapping[key]) for side, key in (("left", "left_foot"), ("right", "right_foot")) if key in mapping}
    files = _clip_files(run)
    cache: dict[Path, dict[str, Any]] = {}
    missing: list[str] = []
    out_of_range: list[str] = []
    bad_blinks: list[str] = []
    clips: list[dict[str, Any]] = []
    for index, decision in enumerate(sorted(decisions, key=lambda d: str(d.data["name"]))):
        run.progress(index, len(decisions), f"reading {decision.data['name']}")
        data = decision.data
        name, source = str(data["name"]), str(data["source"])
        stem, _, action_name = source.partition("/")
        if stem in files:
            path, wanted = files[stem], (action_name or None)
        else:
            path, wanted = rig_file, source
        found = _read(run, cache, path, root, feet)
        action, why = _action(found, wanted, stem)
        if action is None:
            where = f"the clip source {stem}" if path != rig_file else "the rig's file"
            missing.append(f"{name}: {where} {why}" if path != rig_file else
                           f"{name}: no clip source {stem}, and {where} {why}")
            continue
        start, end = int(data["start"]), int(data["end"])
        if start > end or start < action["start"] or end > action["end"]:
            out_of_range.append(f"{name}: frames {start}-{end} are outside {action['name']}'s "
                                f"{action['start']}-{action['end']}")
            continue
        travel = float(action["travel"]) / float(found["height"]) if found["height"] else 0.0
        looping, in_place = bool(data["loop"]), travel <= ROOT_MOTION_RATIO
        speed, still = float(data.get("speed", 1)), data.get("still")
        if still is not None:
            frames: list[float | int] = [start] * int(still)
        else:
            frames = sample_frames(start, end, float(found["fps"]), int(data["fps"]), looping, speed)
        eyelids = {key: sorted(int(b) for b in data.get(key, [])) for key in EYELIDS}
        late = [f"{key} names {listed[-1]}" for key, listed in eyelids.items() if listed and listed[-1] >= len(frames)]
        if late:
            bad_blinks.append(f"{name}: it has {len(frames)} frames (0 to {len(frames) - 1}) and {' and '.join(late)}")
            continue
        # a key only when it is set, so a clip decided without them is the entry it always was (and `render` keeps its frames)
        extras: dict[str, Any] = {**({"speed": speed} if speed != 1 else {}), **({"still": int(still)} if still is not None else {}),
                                  **{key: listed for key, listed in eyelids.items() if listed}}
        clips.append({
            "name": name,
            "source": source,
            "source_hash": _hash_file(path),
            "action": action["name"],
            "start": start,
            "end": end,
            "source_fps": found["fps"],
            "fps": int(data["fps"]),
            "loop": bool(data["loop"]),
            "stationary": bool(data.get("stationary", False)),
            "root_travel": round(travel, 4),
            "root_motion": travel > ROOT_MOTION_RATIO,
            "frames": frames,
            "events": {"foot": [] if still is not None else
                       find_plants(action.get("feet") or {}, float(found["height"]), start, end, frames, looping, not in_place)},
            **extras,
        })
    if missing:
        raise StageFailure("a clip's source can't be found: " + "; ".join(missing), code="clips.source_missing",
                           owner_action="Add the animation file (kiripix import "
                                        f"{run.asset_id} <file.fbx> --role clip-source), or name an action of the rigged "
                                        "Model as the clip's source.")
    if out_of_range:
        raise StageFailure("a clip's frames are outside its action: " + "; ".join(out_of_range), code="clips.range",
                           fix=f"kiripix undo {run.asset_id} clips")
    if bad_blinks:
        raise StageFailure("a clip's blink or wink is not one of its frames: " + "; ".join(bad_blinks), code="clips.blink_range",
                           fix=f"kiripix undo {run.asset_id} clips")
    document = {"schema_version": CLIPS_SCHEMA_VERSION, "clips": clips}
    (run.output_dir / "clips.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def check_clips(run: StageRun) -> list[Finding]:
    """Root motion is reported, not refused: the render keeps the feet at the pivot either way."""
    path = run.output_dir / "clips.json"
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        Finding(
            code="clips.root_motion", severity="warning",
            message=f"the clip {clip['name']} moves its root ({clip['root_travel']:.0%} of the character's height): "
                    "the render keeps the feet at the pivot, so the sprite will play in place",
            position=Position(asset=run.asset_id, stage="clips"),
            owner_action="Download the animation again from Mixamo with In Place ticked, then add it: "
                         f"kiripix import {run.asset_id} <downloaded.fbx> --role clip-source")
        for clip in document["clips"] if clip["root_motion"]
    ]
