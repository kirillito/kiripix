"""The character's `clips` Stage (spec §6.3, ticket 0103): each `clip` Decision resolved against its source, an action of the
rigged Model or an animation file added with `--role clip-source`, into `clips.json`: the frame range, the frame rates, the
loop and stationary flags, whether the root travels, and the frame numbers a render samples.

A clip's `source` is a clip-source file's stem (`walk` for `src/clips/walk.<hash>.fbx`; `walk/<action>` when the file has
several actions), else the name of an action in the rig's file (the Model's own `model.blend`, or the rigged file the Mixamo
round trip brought back). A clip-source file wins over an action of the same name.

Blender is asked once per file, for its actions and how far the root travels in each; the Stage does the rest.
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

CLIPS_SCHEMA_VERSION = 1
CLIP_SOURCES = "src/clips/"
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
                "the sheet's pivot-drift Check then holds it to.",
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
        },
        "required": ["name", "source", "start", "end", "fps", "loop"],
        "additionalProperties": False,
    },
)

_NAME = re.compile(NAME_PATTERN)


def clip_decisions(run: StageRun) -> list[CurrentDecision]:
    return [d for d in run.decisions if d.name == CLIP.name]


def clips_needs_input(run: StageRun) -> NeedsInput | None:
    if clip_decisions(run):
        return None
    sources = sorted(_clip_files(run))
    example = {"decision": "clip", "data": {"name": "idle", "source": sources[0] if sources else "<action or clip source>",
                                            "start": 0, "end": 24, "fps": 12, "loop": True, "stationary": True}}
    return NeedsInput(
        "no clips: add a `clip` Decision for each animation the game plays "
        "(name, source, start, end, fps, loop; stationary optional)",
        command=f"kiripix decide {run.asset_id} clips --decision '{json.dumps(example)}'")


def _clip_files(run: StageRun) -> dict[str, Path]:
    return {Path(Path(name).stem).stem: path for name, path in sorted(run.files.items()) if name.startswith(CLIP_SOURCES)}


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_LENGTH]


def sample_frames(start: int, end: int, source_fps: float, fps: int, loop: bool) -> list[float | int]:
    """The frames of the action a render samples, `fps` a second. A looping clip ends before `end`, which is its first
    pose again; a clip that doesn't loop ends on it. A frame that isn't a whole number is a sub-frame between two keys."""
    step = source_fps / fps
    span = end - start
    count = max(1, round(span / step)) if loop else math.floor(span / step + 1e-9) + 1
    frames: list[float | int] = []
    for index in range(count):
        frame = round(start + index * step, 3)
        frames.append(int(frame) if frame == int(frame) else frame)
    return frames


def _read(run: StageRun, cache: dict[Path, dict[str, Any]], path: Path, root: list[str]) -> dict[str, Any]:
    if path not in cache:
        run.check_cancel()
        cache[path] = launch(run, "read_actions", {"input": str(path), "root": root})
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
    names: dict[str, int] = {}
    for decision in decisions:
        name = str(decision.data["name"])
        names[name] = names.get(name, 0) + 1
    bad = sorted(n for n in names if not _NAME.match(n))
    if bad:
        raise StageFailure(
            f"clip names must be lower-case snake_case and not end in a direction suffix: {', '.join(bad)}",
            code="clips.bad_name",
            fix=f"kiripix undo {run.asset_id} clips")  # then decide the clip again with a valid name
    repeated = sorted(n for n, count in names.items() if count > 1)
    if repeated:
        raise StageFailure(f"a clip name is used twice in the character: {', '.join(repeated)}",
                           code="clips.duplicate_name",
                           fix=f"kiripix undo {run.asset_id} clips")  # the latest Decision is the repeat

    rig_file, rig = _rig(run)
    root = ["root", str(rig["mapping"].get("hips", "hips"))]
    files = _clip_files(run)
    cache: dict[Path, dict[str, Any]] = {}
    missing: list[str] = []
    out_of_range: list[str] = []
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
        found = _read(run, cache, path, root)
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
            "frames": sample_frames(start, end, float(found["fps"]), int(data["fps"]), bool(data["loop"])),
        })
    if missing:
        raise StageFailure("a clip's source can't be found: " + "; ".join(missing), code="clips.source_missing",
                           owner_action="Add the animation file (kiripix import "
                                        f"{run.asset_id} <file.fbx> --role clip-source), or name an action of the rigged "
                                        "Model as the clip's source.")
    if out_of_range:
        raise StageFailure("a clip's frames are outside its action: " + "; ".join(out_of_range), code="clips.range",
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
