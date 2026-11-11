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

Frame size (ticket 0155): one square cell for the whole character. It starts at `ceil(1.5 * height)` px rounded up to even,
with the pivot, the ground point the camera orbits, at its centre column and `ceil(0.1 * height)` px above its bottom. Before
rendering, Blender measures where every frame of every clip lands (`"measure": true`, no shading), and the cell grows, never
shrinks, until every pose fits with a pixel to spare on each side for `finish`'s outline, both as rendered and as `sheet` places
it by its pivot. So no pose is cut, and characters of one height share a cell unless one reaches further. The measures are kept
per clip in `render.json` with a key of what poses the clip, so a rebuild measures only clips that changed.

Pivots (ticket 0154): a `stationary` clip's pivot is the cell's pivot in every frame, where the feet are: the point under the
root sways with the hips, and a pivot that follows it would make `sheet` shift the whole sprite by a pixel as it crosses a half
pixel. A `root_motion` clip's camera follows the root, so its pivot is the cell's too; any other clip reports the pivot as
the root puts it.
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

from kiripix.recipes.base import StageFailure, StageRun, computed_setting
from kiripix.recipes.blender_launcher import launch
from kiripix.recipes.clips import DIRECTIONS

RENDER_SCHEMA_VERSION = 2  # 2: each clip carries its measured `bounds` (0155), a stationary clip one pivot (0154)
# A Stage input (ADR 0010), as the Blender version is: a render in an older format is stale, so `render` and every Stage
# after it are built again. Read at call time, so that a test can change the version.
FORMAT_SETTING = "render.format"
computed_setting(FORMAT_SETTING, lambda: RENDER_SCHEMA_VERSION)
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


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)  # as `sheet` rounds a pivot


def clip_bounds(measured: dict[str, list[dict[str, Any]]], follows_root: bool) -> list[float]:
    """A clip's extent [left, top, right, bottom] in px from the cell's pivot, over every direction and frame: as rendered,
    and, when its pivot follows the root, also as `sheet` places each frame by its rounded pivot."""
    left = top = math.inf
    right = bottom = -math.inf
    for frames in measured.values():
        for frame in frames:
            x0, y0, x1, y1 = frame["bounds"]
            shifts = [(0, 0)]
            if follows_root:
                shifts.append((_half_up(frame["under"][0]), _half_up(frame["under"][1])))
            for dx, dy in shifts:
                left, top, right, bottom = min(left, x0 - dx), min(top, y0 - dy), max(right, x1 - dx), max(bottom, y1 - dy)
    return [left, top, right, bottom]


def fit_cell(height: int, bounds: list[list[float]]) -> tuple[int, list[float]]:
    """The cell's side and pivot: the default cell, grown until every extent in `bounds` fits with 1 px left on each side for
    the outline. A pixel is drawn when its centre is covered, so `ceil` of an extent is the pixels it can reach."""
    side, below = cell_size(height), math.ceil(BOTTOM_RATIO * height)
    finite = [b for b in bounds if all(math.isfinite(v) for v in b)]
    if finite:
        left, top = min(b[0] for b in finite), min(b[1] for b in finite)
        right, bottom = max(b[2] for b in finite), max(b[3] for b in finite)
        below = max(below, math.ceil(bottom) + 1)
        half = math.ceil(max(-left, right, 0.0)) + 1
        side = max(side, 2 * half, below + math.ceil(max(-top, 0.0)) + 1)
        side += side % 2
    return side, [side / 2, float(side - below)]


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


def _previous_bounds(run: StageRun) -> dict[str, tuple[str, list[float]]]:
    """The measured bounds of the previous output's clips, by name, with the key they were measured under."""
    if run.forced or run.previous is None:
        return {}
    try:
        document = _json(run.previous / "render.json")
        return {str(e["name"]): (str(e["measure_key"]), [float(v) for v in e["bounds"]])
                for e in document["clips"] if "measure_key" in e and len(e["bounds"]) == 4}
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
    side, pivot = fit_cell(height, [])  # the default cell: where the measure pass puts the camera
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
    posing: dict[str, Any] = {name: args[name] for name in ("root", "model_height", "elevation", "px_per_unit")}
    posing.update(directions=list(names), rig=_stamp_hash(run.upstream["rig"]), model=_stamp_hash(run.upstream["model"]),
                  blender=str(run.settings.get("blender.version", "")), script=_script_hash(), schema=RENDER_SCHEMA_VERSION)
    measure_keys = {c["name"]: hashlib.sha256(json.dumps({"clip": c, **posing}, sort_keys=True).encode("utf-8")).hexdigest()
                    for c in clips}
    bounds = {name: found for name, (measured_under, found) in _previous_bounds(run).items()
              if measure_keys.get(name) == measured_under}
    unmeasured = [c for c in args["clips"] if c["name"] not in bounds]
    if unmeasured:
        run.progress(0, 1, f"measuring {len(unmeasured)} of {len(clips)} clips")
        measured = launch(run, "render_frames", {**args, "clips": unmeasured, "measure": True})["frames"]
        for clip in clips:
            if clip["name"] in measured:
                follows_root = not clip["stationary"] and not clip["root_motion"]
                bounds[clip["name"]] = clip_bounds(measured[clip["name"]], follows_root)
    side, pivot = fit_cell(height, [bounds[c["name"]] for c in clips])
    args.update(frame=[side, side], pivot=pivot)
    shared: dict[str, Any] = {name: args[name] for name in ("frame", "pivot", "toon")}
    shared.update(posing)

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
        measures = {"measure_key": measure_keys[clip["name"]], "bounds": bounds[clip["name"]]}
        if clip["name"] in kept:
            entry = {**{k: v for k, v in kept[clip["name"]].items() if k != "depth_range"}, **measures}
            if clip["stationary"]:  # an older render may have kept the swaying root's pivots (ticket 0154)
                entry["directions"] = {d: [{**f, "pivot": list(pivot)} for f in frames]
                                       for d, frames in entry["directions"].items()}
            entries.append(entry)
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
                               "pivot": list(pivot) if clip["stationary"] else found["pivot"]})
            directions[direction] = frames
        entries.append({"name": clip["name"], "key": keys[clip["name"]], "fps": clip["fps"], "loop": clip["loop"],
                        "stationary": clip["stationary"], "root_motion": clip["root_motion"], "directions": directions,
                        **measures})
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

