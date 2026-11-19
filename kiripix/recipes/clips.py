"""The character's `clips` Stage (spec §6.3, ticket 0103): each `clip` Decision resolved against its source, an action of the
rigged Model or an animation file added with `--role clip-source`, into `clips.json`: the frame range, the frame rates, the
loop and stationary flags, whether the root travels, and the frame numbers a render samples.

A clip's `source` is a clip-source file's stem (`walk` for `src/clips/walk.<hash>.fbx`; `walk/<action>` when the file has
several actions), else the name of an action in the rig's file (the Model's own `model.blend`, or the rigged file the Mixamo
round trip brought back). A clip-source file wins over an action of the same name.

A character made from a base (ADR 0012) starts with the base's clips: the base's current Decisions come first, then its own,
which add a clip, replace one of the same name or `remove` one. The base's clip-source files are read where they are, in the
base's folder; a file of the character's own with the same stem wins. Only clip-source files cross: a base clip that plays an
action of the base's own Model file is looked for in the character's Model, and fails `clips.source_missing` without it.

Blender is asked once per file, for its actions, how far the root travels in each, and the foot bones' height and speed at
each frame; the Stage does the rest, among it the frames where a foot plants (`find_plants`, ticket 0172), listed per clip in
`events`: the same on every direction, as a direction is only the camera's view of one action.
"""

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import CurrentDecision, DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.blender_launcher import launch

# 2: each clip's `events` ({"foot": [index into `frames`, ...]}, ticket 0172); refused when older
# 3: a `transition` clip's entry (`transition`: its two ends and `length`, ticket 0218)
CLIPS_SCHEMA_VERSION = 3
PLANT_HEIGHT = 0.03  # a foot within this fraction of the rig's height of the clip's lowest foot point is on the ground
PLANT_SPEED = 0.25  # with root motion, a planted foot moves less than this many rig heights a second
CLIP_SOURCES = "src/clips/"
THINGS_DIR = "src/things/"  # a held thing's files: `src/things/<id>/<file>` (ticket 0301 imports them; 0300 only reads that they exist)
THINGS_PATTERN = "src/things/*/*"  # the `clips` Stage's file input: a thing added or removed makes it stale, as it may fail
THING_ID = r"^[a-z0-9_]+$"
DEFAULT_SOCKET = "grip_r"  # the bone a held thing sits on (ticket 0238)
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
                "frames with only the Model's left or right eye closed; on a `still` clip one past its last frame is refused when decided, and on another the run fails clips.blink_range. Deciding a clip again under a name it "
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
            "attach": {
                "type": "array",
                "description": "The things the clip holds, each at a socket bone of the Model.",
                "items": {
                    "type": "object",
                    "properties": {
                        "thing": {"type": "string", "pattern": THING_ID,
                                  "description": "A held thing's ID: imported on the Asset with `--role thing --thing <id>`."},
                        "socket": {"type": "string", "minLength": 1, "default": DEFAULT_SOCKET,
                                   "description": "A bone of the rigged Model the thing is parented to."},
                        "offset": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                                   "description": "x, y, z in the socket's frame, in Model units (default 0, 0, 0)."},
                        "turn": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3,
                                 "description": "Degrees about each axis of the socket's frame (default 0, 0, 0)."},
                    },
                    "required": ["thing"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["name", "source", "start", "end", "fps", "loop"],
        "additionalProperties": False,
    },
    problem=lambda data: _eyelid_problem(data) or attach_problem(data),
)


def attach_problem(data: dict[str, Any]) -> str | None:
    """A thing named twice in one clip's `attach`: the entry alone says it."""
    things = [str(a["thing"]) for a in data.get("attach", [])]
    twice = sorted({t for t in things if things.count(t) > 1})
    return f"`attach` names {', '.join(twice)} more than once; a thing is held once in a clip" if twice else None


def held_things(attach: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A clip's `attach` as `clips.json` records it: the socket filled in, `offset` and `turn` only when given."""
    return [{"thing": str(a["thing"]), "socket": str(a.get("socket", DEFAULT_SOCKET)),
             **{key: [float(v) for v in a[key]] for key in ("offset", "turn") if key in a}} for a in attach]


def thing_ids(files: Any) -> set[str]:
    """The IDs of the things on an Asset, from its file names: `src/things/<id>/<file>`."""
    return {name[len(THINGS_DIR):].split("/", 1)[0] for name in files
            if name.startswith(THINGS_DIR) and name.count("/") >= 3}


def unknown_things(attach: list[dict[str, Any]], known: set[str]) -> list[str]:
    return sorted({str(a["thing"]) for a in attach if str(a["thing"]) not in known})


def unknown_sockets(attach: list[dict[str, Any]], bones: Any) -> list[str]:
    return sorted({str(a.get("socket", DEFAULT_SOCKET)) for a in attach if str(a.get("socket", DEFAULT_SOCKET)) not in bones})


def socket_message(sockets: list[str], bones: list[str]) -> str:
    shown = ", ".join(bones[:30]) + ("..." if len(bones) > 30 else "")
    return f"no bone {', '.join(sockets)} in the rig (its bones are {shown})"


def _eyelid_problem(data: dict[str, Any]) -> str | None:
    """A blink or wink past the clip's last frame, where the entry alone gives the frame count: a `still` clip. Otherwise
    the count depends on the source's frame rate, which only the Stage reads, and its run fails clips.blink_range."""
    still = data.get("still")
    if still is None:
        return None
    late = [f"{key} names {max(data[key])}" for key in EYELIDS if data.get(key) and max(data[key]) >= int(still)]
    return f"the clip has {still} frames (0 to {int(still) - 1}) and {' and '.join(late)}" if late else None


_END = {
    "type": "object",
    "properties": {"clip": {"type": "string", "minLength": 1}, "frame": {"type": "integer", "minimum": 0}},
    "required": ["clip"],
    "additionalProperties": False,
}

TRANSITION = DecisionSpec(
    name="transition",
    description="A clip that blends one clip's pose into another's, rendered by Kiripix and exported like any clip, so an idle "
                "character that attacks doesn't snap into the attack's first frame. `name` is its ID in the game, with the "
                "same pattern as a clip's and frozen at its first export; by convention `<from>_to_<to>`. `from` and `to` "
                "name a `clip` and one of its frames (`frame`, from 0 in the clip's own frames: `from` defaults to the last, "
                "`to` to the first). `length` (default 3) is the number of frames between the two poses, not including "
                "them: frame i of n is the blend at (i + 1) / (n + 1), every bone's location and scale linear and its "
                "rotation spherical, with the root kept in place. `fps` defaults to the `from` clip's. It never loops. "
                "Deciding a transition again under a name it already has changes it; `undo` brings the old one back. "
                "A name a `clip` has fails clips.duplicate_name.",
    entry_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "pattern": NAME_PATTERN},
            "from": _END,
            "to": _END,
            "length": {"type": "integer", "minimum": 1, "default": 3},
            "fps": {"type": "integer", "minimum": 1},
        },
        "required": ["name", "from", "to"],
        "additionalProperties": False,
    },
)

REMOVE = DecisionSpec(
    name="remove",
    description="Take a clip or a transition away by its `name`, together with every transition from or to it, as far as "
                "they were decided before this. On a character made from a base it takes a clip of the base away from this "
                "character only; the base keeps it. A `clip` Decision under the name afterwards brings the clip back, and "
                "`undo` takes the removal back. A name no clip has at that point changes nothing (a warning, "
                "clips.remove_unknown).",
    entry_schema={
        "type": "object",
        "properties": {"name": {"type": "string", "pattern": NAME_PATTERN}},
        "required": ["name"],
        "additionalProperties": False,
    },
)

_NAME = re.compile(NAME_PATTERN)


def apply_clip_edits(decisions: tuple[CurrentDecision, ...]) -> tuple[CurrentDecision, ...]:
    """The clips Stage's Decisions as it reads them (`StageSpec.decisions_view`, ticket 0228): one `clip` and one
    `transition` per name, and the `remove` Decisions that found nothing to take away. The Decisions are taken in order (a
    base's first, ADR 0012): a `clip` or `transition` under a name an earlier one has replaces it and keeps its place (ticket
    0156), so the latest wins; the earlier one stays current in the journal, which is why `undo` of the new one brings it
    back. A `remove` takes away the clip or transition of that name and every transition from or to it.

    The result is the `remove` Decisions that found nothing, then the clips, then the transitions, so replaying it again
    gives it back unchanged."""
    clips: dict[str, CurrentDecision] = {}
    transitions: dict[str, CurrentDecision] = {}
    unknown: list[CurrentDecision] = []
    for decision in decisions:
        name = str(decision.data.get("name", ""))
        if decision.name == CLIP.name:
            clips[name] = decision  # a dict keeps the first insertion's place
        elif decision.name == TRANSITION.name:
            transitions[name] = decision
        elif decision.name == REMOVE.name:
            if name not in clips and name not in transitions:
                unknown.append(decision)
                continue
            clips.pop(name, None)
            transitions.pop(name, None)
            for other in [n for n, t in transitions.items() if name in (str(t.data["from"]["clip"]), str(t.data["to"]["clip"]))]:
                del transitions[other]
    return (*unknown, *clips.values(), *transitions.values())


def clip_decisions(run: StageRun) -> list[CurrentDecision]:
    """The clips of a run, one per name, as `apply_clip_edits` left them. Every reader of the clips in a Stage goes through
    here."""
    return [d for d in run.decisions if d.name == CLIP.name]


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
    known = [f"clip source {stem}" for stem in sorted(clip_files(run))]
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


def clip_files(run: StageRun) -> dict[str, Path]:
    """The clip-source files a clip's `source` can name, by stem: the character's own, and its base's (ADR 0012), which
    stay in the base's folder. Its own file wins a stem both have, so a character can play a base clip from another file."""
    found: dict[str, Path] = {}
    for files in ((run.base.files if run.base is not None else {}), run.files):
        found.update({Path(Path(name).stem).stem: path for name, path in sorted(files.items())
                      if name.startswith(CLIP_SOURCES)})
    return found


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
    _check_attach(run, decisions, rig)
    files = clip_files(run)
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
                                  **({"attach": held_things(data["attach"])} if data.get("attach") else {}),
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
        of_base = "" if run.base is None else (
            f" A clip of the base {run.base.asset_id} that plays an action of the base's own Model doesn't reach this "
            "character: only the base's clip-source files do, so give the base that animation as a clip source.")
        raise StageFailure("a clip's source can't be found: " + "; ".join(missing), code="clips.source_missing",
                           owner_action="Add the animation file (kiripix import "
                                        f"{run.asset_id} <file.fbx> --role clip-source), or name an action of the rigged "
                                        f"Model as the clip's source.{of_base}")
    if out_of_range:
        raise StageFailure("a clip's frames are outside its action: " + "; ".join(out_of_range), code="clips.range",
                           fix=f"kiripix undo {run.asset_id} clips")
    if bad_blinks:
        raise StageFailure("a clip's blink or wink is not one of its frames: " + "; ".join(bad_blinks), code="clips.blink_range",
                           fix=f"kiripix undo {run.asset_id} clips")
    clips += _resolve_transitions(run, clips, names)
    clips.sort(key=lambda c: str(c["name"]))
    document = {"schema_version": CLIPS_SCHEMA_VERSION, "clips": clips}
    (run.output_dir / "clips.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _check_attach(run: StageRun, decisions: list[CurrentDecision], rig: dict[str, Any]) -> None:
    """Every thing a clip holds is on the Asset, at a bone of the rig, and held once: `decide` refuses these when it can, and
    a thing taken away or a rig changed since fails here."""
    known = thing_ids(run.files)
    bones = list(rig.get("parents", {}))
    undo = f"kiripix undo {run.asset_id} clips"
    for decision in decisions:
        attach = list(decision.data.get("attach", []))
        name = decision.data["name"]
        if problem := attach_problem(decision.data):
            raise StageFailure(f"{name}: {problem}", code="clips.thing_twice", fix=undo)
        if lost := unknown_things(attach, known):
            raise StageFailure(f"the clip {name} holds {', '.join(lost)}, and the Asset has no such thing "
                               f"(its things are {', '.join(sorted(known)) or 'none'})", code="clips.unknown_thing",
                               owner_action=f"Import the thing: kiripix import {run.asset_id} <file> --role thing --thing "
                                            f"{lost[0]}; or decide the clip again without it.")
        if wrong := unknown_sockets(attach, bones):
            raise StageFailure(f"the clip {name}: {socket_message(wrong, bones)}", code="clips.unknown_socket",
                               fix=undo)  # then decide the clip again with a bone of the rig as `socket`


def _resolve_transitions(run: StageRun, clips: list[dict[str, Any]], clip_names: list[str]) -> list[dict[str, Any]]:
    """The entries of the `transition` Decisions: the blend positions as `frames`, and each end with the source's hash, the
    action and the action's frame, taken from the named clip's own `frames` (ticket 0218). A transition's failures name the
    clip, the frame or the pair at fault and are taken back with `undo`."""
    transitions = [d for d in run.decisions if d.name == TRANSITION.name]  # one per name: `apply_clip_edits`
    by_name = {str(c["name"]): c for c in clips}
    undo = f"kiripix undo {run.asset_id} clips"
    shared = sorted(n for n in (str(t.data["name"]) for t in transitions) if n in clip_names)
    if shared:
        raise StageFailure(f"a transition has the name of a clip: {', '.join(shared)}", code="clips.duplicate_name", fix=undo)
    bad = sorted(str(t.data["name"]) for t in transitions if not _NAME.match(str(t.data["name"])))
    if bad:
        raise StageFailure(f"clip names must be lower-case snake_case and not end in a direction suffix: {', '.join(bad)}",
                           code="clips.bad_name", fix=undo)
    named = {str(t.data["name"]) for t in transitions}
    looping = sorted({f"{t.data['name']}: {t.data[end]['clip']} is a transition" for t in transitions for end in ("from", "to")
                      if str(t.data[end]["clip"]) in named})
    if looping:
        raise StageFailure("a transition between transitions has no meaning: " + "; ".join(looping),
                           code="clips.transition_loop", fix=undo)
    unknown = sorted({f"{t.data['name']}: no clip {t.data[end]['clip']}" for t in transitions for end in ("from", "to")
                      if str(t.data[end]["clip"]) not in by_name})
    if unknown:
        raise StageFailure(f"a transition names no clip ({'; '.join(unknown)}); the clips are {', '.join(sorted(by_name))}",
                           code="clips.transition_missing_clip", fix=undo)  # then decide the clip, or undo
    found: list[dict[str, Any]] = []
    outside: list[str] = []
    for decision in transitions:
        data = decision.data
        ends: dict[str, dict[str, Any]] = {}
        for end, default in (("from", -1), ("to", 0)):
            source = by_name[str(data[end]["clip"])]
            count = len(source["frames"])
            index = int(data[end].get("frame", default % count))
            if not 0 <= index < count:
                outside.append(f"{data['name']}: {source['name']} has frames 0 to {count - 1}, and {end} names {index}")
                continue
            ends[end] = {"clip": source["name"], "frame": index, "source": source["source"],
                         "source_hash": source["source_hash"], "action": source["action"],
                         "action_frame": source["frames"][index], "root_motion": source["root_motion"]}
        if len(ends) < 2:
            continue
        length = int(data.get("length", 3))
        first = by_name[str(data["from"]["clip"])]
        found.append({
            "name": str(data["name"]),
            "transition": {**ends, "length": length},
            "fps": int(data.get("fps", first["fps"])),
            "loop": False,
            "stationary": bool(first["stationary"] and by_name[str(data["to"]["clip"])]["stationary"]),
            "root_travel": 0.0,
            "root_motion": False,
            "frames": [round((i + 1) / (length + 1), 6) for i in range(length)],
            "events": {"foot": []},
            **({"attach": first["attach"]} if first.get("attach") else {}),  # it holds what its `from` clip holds
        })
    if outside:
        raise StageFailure("a transition names a frame its clip doesn't have: " + "; ".join(outside),
                           code="clips.transition_frame", fix=undo)  # then decide it again with a frame in range
    return found


def check_clips(run: StageRun) -> list[Finding]:
    """Root motion is reported, not refused: the render keeps the feet at the pivot either way. So is a `remove` that
    found no clip under its name, which a base that dropped the clip leaves behind."""
    path = run.output_dir / "clips.json"
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    unknown = [
        Finding(
            code="clips.remove_unknown", severity="warning",
            message=f"a `remove` names the clip {name}, and there was no clip or transition of that name to take away",
            position=Position(asset=run.asset_id, stage="clips"),
            owner_action=f"Nothing is needed if {name} is meant to be gone. If the name is a typo, undo the `remove` "
                         f"(kiripix undo {run.asset_id} clips, while it is the latest Decision) and decide it again.")
        for name in dict.fromkeys(str(d.data["name"]) for d in run.decisions if d.name == REMOVE.name)
    ]
    return unknown + [
        Finding(
            code="clips.root_motion", severity="warning",
            message=f"the clip {clip['name']} moves its root ({clip['root_travel']:.0%} of the character's height): "
                    "the render keeps the feet at the pivot, so the sprite will play in place",
            position=Position(asset=run.asset_id, stage="clips"),
            owner_action="Download the animation again from Mixamo with In Place ticked, then add it: "
                         f"kiripix import {run.asset_id} <downloaded.fbx> --role clip-source")
        for clip in document["clips"] if clip["root_motion"]
    ]
