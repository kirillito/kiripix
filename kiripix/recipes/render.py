"""The character's `render` Stage (spec §6.3, ticket 0104): every clip of `clips.json` in every direction, at the target pixel
size, as four passes (colour, normal, depth, object mask), by headless Blender, into `render.json` and the frame files.

A camera preset is `[character.camera.<name>]` in kiripix.toml (its elevation and 4 or 8 directions), picked by the `camera`
parameter. The Model is turned about its up axis in fixed steps (in Blender the camera orbits the pivot, so the light stays with
it): `s` faces the camera, then `sw w nw n ne e se` as the screen reads them. All directions are rendered, none mirrored (Q6).
Renders aren't pinned (ADR 0010): the Blender version and every render setting are inputs, so a change makes the Stage stale.
The device is not an input: a run with `--cpu` renders on the CPU and holds no GPU lock.

Reuse (ticket 0119): each clip of `render.json` carries a `key`, a hash of everything that changes its frames: its own entry
in `clips.json` (with its source's hash), the rig's and the Model's input hashes (so the Model's file, `facing` and the Blender
version), the camera preset's numbers, the toon settings, the height, the Blender version, the device and the render script. On a
rebuild the frames of a clip whose key matches the one in the Stage's `previous` output are copied from it, and Blender gets only
the other clips. The output is the same bytes as a full rebuild's. `--force` and a `previous` without keys render everything.

Frame size: one square cell for the whole character, `ceil(1.5 * height)` px rounded up to even, so a raised arm or a weapon
fits. The pivot, the ground point under the root, lands at the cell's centre column and `ceil(0.1 * height)` px above its bottom.
The Model's standing height (its z extent, seen from the camera) is `height` px: pixels per Blender unit is
`height / (Model height * cos(elevation))`.

Toon shading (ticket 0105): the colour pass is the Model's colour lit by one key light fixed in camera space (the preset's
`light_angle` and `light_tilt`), cut into `bands` steps and darkened by `shadow`. It is done in the script on the normal, not with
a Blender shader, because Shader to RGB is EEVEE-only and render uses Cycles so that `--cpu` works. The other passes don't change.
"""

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.blender_launcher import launch
from kiripix.recipes.clips import DIRECTIONS

RENDER_SCHEMA_VERSION = 1
PASSES = ("color", "normal", "depth", "mask")
EIGHT = DIRECTIONS
FOUR = ("s", "w", "n", "e")
# Degrees the Model turns about its up axis (counter-clockwise from above), for the direction it then faces on screen. The
# camera is at -Y looking +Y, the Model at rest faces -Y (toward it), screen right is +X.
YAW = {"s": 0, "sw": -45, "w": -90, "nw": -135, "n": 180, "ne": 135, "e": 90, "se": 45}
CELL_RATIO = 1.5
BOTTOM_RATIO = 0.1  # of the height, the pivot's distance above the cell's bottom
ROOTS = ("root",)


def cell_size(height: int) -> int:
    side = math.ceil(CELL_RATIO * height)
    return side + side % 2


def _json(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _rig_file(run: StageRun, rig: dict[str, Any]) -> Path:
    if rig["source"] == "rigged":
        return run.asset_dir / "src" / "rigged" / rig["file"]
    return run.upstream["model"] / "model.blend"


def _clip_file(run: StageRun, clip: dict[str, Any]) -> str | None:
    """The clip-source file a clip's `source` names (`<stem>` or `<stem>/<action>`), or None: an action of the rig's file."""
    stem = str(clip["source"]).partition("/")[0]
    for name, path in sorted(run.files.items()):
        if name.startswith("src/clips/") and Path(Path(name).stem).stem == stem:
            return str(path)
    return None


def _stamp_hash(folder: Path) -> str:
    """The input hash in a Stage's stamp (`.stage.json`): what the Stage's output was built from."""
    try:
        return str(json.loads((folder / ".stage.json").read_text(encoding="utf-8")).get("input_hash", ""))
    except (OSError, ValueError):
        return ""


def _script_hash() -> str:
    script = Path(__file__).resolve().parents[1] / "blender" / "render_frames.py"
    return hashlib.sha256(script.read_bytes()).hexdigest()


def _previous_clips(run: StageRun, names: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """The clips of the previous output that can be copied as they are, by name: they have a key, all the directions asked for
    and every frame file. Nothing when the Stage is forced, there is no previous output or its `render.json` can't be read."""
    if run.forced or run.previous is None:
        return {}
    try:
        document = _json(run.previous / "render.json")
        found: dict[str, dict[str, Any]] = {}
        for entry in document["clips"]:
            frames = entry["directions"]
            if "key" not in entry or list(frames) != list(names):
                continue
            files = [run.previous / f for direction in names for item in frames[direction] for f in item["files"].values()]
            if all(path.is_file() for path in files):
                found[entry["name"]] = {**entry, "depth_range": document["depth_range"]}
        return found
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _copy_clip(run: StageRun, previous: Path, name: str) -> None:
    for kind in PASSES:
        shutil.copytree(previous / kind / name, run.output_dir / kind / name)
    run.check_cancel()


def run_render(run: StageRun) -> None:
    camera_name = str(run.params.get("camera", "top34_8"))
    presets = run.settings.get("character.camera") or {}
    if camera_name not in presets:
        raise StageFailure(
            f"there is no camera preset {camera_name} (the presets are {', '.join(sorted(presets)) or 'none'})",
            code="render.camera_unknown",
            owner_action=f"Add [character.camera.{camera_name}] (elevation, directions) to kiripix.toml, or set the "
                         f"Asset's camera parameter to one of the presets.")
    preset = presets[camera_name]
    elevation, count = float(preset["elevation"]), int(preset["directions"])
    height = int(run.params.get("height") or run.settings.get("character.height") or 52)

    clips_document = _json(run.upstream["clips"] / "clips.json")
    rig = _json(run.upstream["rig"] / "rig.json")
    model = _json(run.upstream["model"] / "model.json")
    model_height = float(model["height"])
    side = cell_size(height)
    pivot = [side / 2, float(side - math.ceil(BOTTOM_RATIO * height))]
    names = EIGHT if count == 8 else FOUR
    clips = clips_document["clips"]
    args: dict[str, Any] = {
        "rig_file": str(_rig_file(run, rig)),
        "root": [*ROOTS, str(rig["mapping"].get("hips", "hips"))],
        "model_height": model_height,
        "clips": [{"name": c["name"], "action": c["action"], "file": _clip_file(run, c), "frames": c["frames"],
                   "root_motion": bool(c["root_motion"])} for c in clips],
        "directions": [{"name": d, "yaw": YAW[d]} for d in names],
        "elevation": elevation,
        "frame": [side, side],
        "px_per_unit": round(height / (model_height * math.cos(math.radians(elevation))), 6),
        "pivot": pivot,
        "toon": {"bands": int(run.params.get("bands", 3)), "shadow": float(run.params.get("shadow", 0.5)),
                 "light": {"angle": float(preset.get("light_angle", -45)), "tilt": float(preset.get("light_tilt", 35))}},
        "device": "cpu" if run.cpu else "gpu",
        "output": str(run.output_dir),
    }
    shared = {name: args[name] for name in ("root", "model_height", "elevation", "frame", "px_per_unit", "pivot", "toon")}
    shared.update(directions=list(names), rig=_stamp_hash(run.upstream["rig"]), model=_stamp_hash(run.upstream["model"]),
                  blender=str(run.settings.get("blender.version", "")), script=_script_hash(), schema=RENDER_SCHEMA_VERSION)

    def key(clip: dict[str, Any], device: str) -> str:
        return hashlib.sha256(json.dumps({"clip": clip, **shared, "device": device}, sort_keys=True)
                              .encode("utf-8")).hexdigest()

    keys = {c["name"]: key(c, args["device"]) for c in clips}
    kept = _previous_clips(run, names)
    kept = {name: entry for name, entry in kept.items() if name in keys and entry["key"] == keys[name]}
    every = list(args["clips"])
    reused = len(kept) * len(names)
    previous = run.previous
    args["clips"] = [c for c in every if c["name"] not in kept]

    if args["clips"]:
        run.progress(0, 1, "starting Blender" if not kept else
                     f"reused {reused} clip and direction pairs; starting Blender for {len(args['clips'])} of {len(every)} clips")
        result = launch(run, "render_frames", args)
        if kept and result["depth_range"] != next(iter(kept.values()))["depth_range"]:
            # the depth scale moved, so the kept frames don't match the new ones. The key should prevent it; render all.
            kept, reused, args["clips"] = {}, 0, every
            result = launch(run, "render_frames", args)
        if args["device"] == "gpu" and str(result.get("device", "")).startswith("cpu"):
            # No GPU was found, so Blender rendered on the CPU: the new frames are keyed as CPU frames, as they are.
            keys.update({c["name"]: key(c, "cpu") for c in clips if c["name"] not in kept})
            run.notes.append("no GPU was found, so the frames were rendered on the CPU; run with --cpu to reuse them next time")
    else:
        result = {"depth_range": next(iter(kept.values()), {"depth_range": [0.0, 1.0]})["depth_range"], "frames": {}}
        run.progress(0, 1, f"reused {reused} clip and direction pairs")
    for name in kept:
        assert previous is not None
        _copy_clip(run, previous, name)
    if reused:
        run.notes.append(f"reused {reused} of {len(clips) * len(names)} clip and direction pairs")

    entries = []
    for clip in clips:
        if clip["name"] in kept:
            entries.append({k: v for k, v in kept[clip["name"]].items() if k != "depth_range"})
            continue
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction in names:
            frames = []
            for index, found in enumerate(result["frames"][clip["name"]][direction]):
                files = {p: f"{p}/{clip['name']}/{direction}/{index:03d}.png" for p in PASSES}
                missing = [f for f in files.values() if not (run.output_dir / f).is_file()]
                if missing:
                    raise StageFailure(f"Blender finished without writing {missing[0]}")
                frames.append({"index": index, "source_frame": clip["frames"][index], "files": files,
                               "pivot": found["pivot"]})
            directions[direction] = frames
        entries.append({"name": clip["name"], "key": keys[clip["name"]], "fps": clip["fps"], "loop": clip["loop"],
                        "stationary": clip["stationary"], "root_motion": clip["root_motion"], "directions": directions})
    document = {
        "schema_version": RENDER_SCHEMA_VERSION,
        "camera": camera_name,
        "elevation": elevation,
        "height": height,
        "frame": {"width": side, "height": side},
        "pivot": pivot,
        "px_per_unit": args["px_per_unit"],
        "toon": args["toon"],
        "depth_range": result["depth_range"],
        "passes": list(PASSES),
        "directions": list(names),
        "clips": entries,
    }
    (run.output_dir / "render.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
