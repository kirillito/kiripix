"""A Wearable's `model`, `rig` and `render` Stages (spec §6.3, ticket 0291).

The Wearable's Model is its own meshes on the body's skeleton. `model` normalises it as the body's Model is (`normalise_model.py`
with `like`: the body's `model_root`, so a hat keeps its place whatever its own height). `rig` compares the Wearable's armature
with the body's `rig.json` by bone name: the body's armature drives the Wearable's meshes, so every bone must be there, with the
same parent, and no other.

`render` is the body's render with the Wearable in the scene and the body as a holdout (`render_frames.py`, `wearable`): the
same clips, camera preset, directions, frames, cell and pivot, read from the body's built `clips.json`, `render.json` and Model,
so the frames stack pixel for pixel. The body hides what is behind it and isn't drawn, so the Wearable holds only the pixels that
show. The passes are the body's (colour, normal, depth, mask, material), the depth scale is the body's (checked against its
`render.json`), and the Wearable's materials are numbered after the body's. No outline: the game draws it once on the stack.
Reuse of the body's frames by clip, as the character's `render` does, is not done: a Wearable renders whole.

`render.json` has the body's shape, plus `body` (the asset, its materials' count and its `render` hash), `seconds` (the Blender
time, for the game to budget each hair style and outfit), and `outside_cell`: the frames whose pixels reach past the body's cell
(each `{"clip", "direction", "frame"}`) with `margin`, the body's `cell_margin` at which every frame fits (null when none does).
The Check `wearable.outside_cell` reads them. A Wearable whose body isn't a character (refused at `new` too), or a character whose rig came back from
Mixamo (its file isn't in the Model's space), is refused with a finding.
"""

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import BodyView, StageFailure, StageRun
from kiripix.recipes.blender_launcher import launch
from kiripix.recipes.render import (
    EIGHT, FOUR, PASSES, RENDER_SCHEMA_VERSION, ROOTS, YAW, blender_clip, clip_bounds, fits_cell, needed_margin
)
from kiripix.recipes.rig import base_mismatch

RIG_SCHEMA_VERSION = 1
DEPTH_TOLERANCE = 0.01  # Blender units: the body's depth range and this render's agree to this
MOST_FRAMES_NAMED = 6  # of the frames outside the cell, in the finding's message


def _json(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def worn_body(run: StageRun) -> BodyView:
    """The body, when a Wearable can be built on it: a character whose Model carries its own armature."""
    body = run.body
    if body is None:
        raise StageFailure("this Wearable has no body", code="wearable.body_unknown",
                           owner_action=f"Set `body` in assets/wearable/{run.asset_id.split('.', 1)[1]}/asset.toml to a character.")
    if body.kind != "character":
        raise StageFailure(
            f"its body {body.asset_id} is a {body.kind}: a Wearable's Model is rendered on a character's skeleton",
            code="wearable.body_not_character",
            owner_action="Set `body` to a character (a sprite body takes no 3D Wearable).")
    return body


def _body_rig(body: BodyView) -> dict[str, Any]:
    rig = _json(body.built["rig"] / "rig.json")
    if rig.get("source") != "model":
        raise StageFailure(
            f"the rig of {body.asset_id} came from a rigged file (Mixamo), whose size and place are not the Model's, so a "
            "Wearable's Model can't be put on it", code="wearable.body_rigged",
            owner_action=f"Build {body.asset_id} from a Model that carries its own armature, then run its rig and render again.")
    return rig


def run_wearable_model(run: StageRun) -> None:
    from kiripix.recipes.character import run_model

    worn_body(run)
    run_model(run)


def run_wearable_rig(run: StageRun) -> None:
    body = worn_body(run)
    theirs = _body_rig(body)
    model = run.upstream["model"] / "model.blend"
    run.progress(0, 1, "reading the rig")
    found = launch(run, "validate_rig", {"input": str(model)})
    if not found.get("armature"):
        raise StageFailure(f"{model.name} has no armature: the Wearable's Model is its meshes on the skeleton of {body.asset_id}",
                           code="wearable.rig_missing",
                           owner_action=f"Export the Wearable's meshes with the armature of {body.asset_id}, then import the file "
                                        f"again.")
    parents: dict[str, Any] = dict(found.get("parents") or {})
    if set(parents) != set(found["bones"]):
        raise StageFailure("Blender read the armature without each bone's parent")
    missing, moved = base_mismatch(theirs, parents)
    extra = [bone for bone in parents if bone not in theirs["parents"]]
    if missing or moved or extra:
        said = []
        if missing:
            said.append(f"it lacks the bones {_listed(missing)}")
        if extra:
            said.append(f"it has bones the body doesn't: {_listed(extra)}")
        if moved:
            said.append(f"it has {_listed(moved)}")
        raise StageFailure(
            f"the skeleton in {model.name} isn't the one of its body {body.asset_id}: {'; '.join(said)}",
            code="wearable.rig_mismatch",
            owner_action=f"Export the Wearable's meshes on {body.asset_id}'s own skeleton (every bone under its exact name and "
                         "parent, none added), then import the file again.")
    document = {"schema_version": RIG_SCHEMA_VERSION, "body": body.asset_id, "armature": found["armature"],
                "bones": len(parents), "parents": {bone: parents[bone] for bone in found["bones"]}}
    (run.output_dir / "rig.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _listed(names: list[str], most: int = 12) -> str:
    return ", ".join(names[:most]) + (f" and {len(names) - most} more" if len(names) > most else "")


def run_wearable_render(run: StageRun) -> None:
    body = worn_body(run)
    rig = _body_rig(body)
    clips_document = _json(body.built["clips"] / "clips.json")
    shown = _json(body.built["render"] / "render.json")
    model = _json(body.built["model"] / "model.json")
    clips = clips_document["clips"]
    names = EIGHT if len(shown["directions"]) == 8 else FOUR
    if list(shown["directions"]) != list(names) or [c["name"] for c in clips] != [c["name"] for c in shown["clips"]]:
        raise StageFailure(f"the render of {body.asset_id} doesn't match its clips", fix=f"kiripix run {body.asset_id} render")
    side, pivot = int(shown["frame"]["width"]), [float(v) for v in shown["pivot"]]
    cells = {str(e["name"]): _body_clip_cell(e, side, pivot) for e in shown["clips"]}  # each clip's own cell (ticket 0311)
    height = int(shown["height"])
    on_body = replace(run, files=body.files, base=None)  # `clips` finds a clip's source file by its stem among the body's files
    args: dict[str, Any] = {
        "rig_file": str(body.built["model"] / "model.blend"),
        "root": [*ROOTS, str(rig["mapping"].get("hips", "hips"))],
        "model_height": float(model["height"]),
        "clips": [blender_clip(on_body, c) for c in clips],
        "directions": [{"name": d, "yaw": YAW[d]} for d in names],
        "elevation": float(shown["elevation"]),
        "frame": [side, side],
        "px_per_unit": float(shown["px_per_unit"]),
        "pivot": pivot,
        "toon": shown["toon"],
        "device": "cpu" if run.cpu else "gpu",
        "wearable": {"file": str(run.upstream["model"] / "model.blend"), "holdout": True},
        "output": str(run.output_dir),
    }

    run.progress(0, 1, "measuring the Wearable")
    started = time.monotonic()
    measured = launch(run, "render_frames", {**args, "measure": True})["frames"]
    measure_seconds = time.monotonic() - started
    outside: list[dict[str, Any]] = []
    past: list[list[float]] = []  # the extents that don't fit their clip's cell
    bounds: dict[str, list[float]] = {}
    for clip in clips:
        follows_root = not clip["stationary"] and not clip["root_motion"]
        bounds[clip["name"]] = clip_bounds(measured[clip["name"]], follows_root)
        for direction, frames in measured[clip["name"]].items():
            for index, frame in enumerate(frames):
                extent = clip_bounds({direction: [frame]}, follows_root)
                if not fits_cell(*cells[clip["name"]], extent):
                    outside.append({"clip": clip["name"], "direction": direction, "frame": index})
                    past.append(extent)
        run.check_cancel()
    margin = needed_margin(height, [list(map(float, c["bounds"])) for c in shown["clips"]], past) if outside else None

    run.progress(0, 1, "starting Blender")
    started = time.monotonic()
    result = _launch_cells(run, args, cells)
    render_seconds = time.monotonic() - started
    if any(abs(a - b) > DEPTH_TOLERANCE for a, b in zip(result["depth_range"], shown["depth_range"], strict=True)):
        raise StageFailure(
            f"the Wearable's depth range {result['depth_range']} is not the body's {shown['depth_range']}, so their depth passes "
            f"wouldn't stack", fix=f"kiripix run {body.asset_id} render --force")
    materials = [{"index": int(m["index"]), "name": str(m["name"])} for m in result["materials"]]
    if device_fallback(args, result):
        run.notes.append("no GPU was found, so the frames were rendered on the CPU")

    entries = []
    frames_made = 0
    for clip, entry in zip(clips, shown["clips"], strict=True):
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction in names:
            frames = []
            found_frames = result["frames"][clip["name"]][direction]
            if len(found_frames) != len(entry["directions"][direction]):
                raise StageFailure(f"the Wearable has {len(found_frames)} frames of {clip['name']} {direction} and its body "
                                   f"{len(entry['directions'][direction])}")
            for index, found in enumerate(found_frames):
                files = {p: f"{p}/{clip['name']}/{direction}/{index:03d}.png" for p in PASSES}
                missing = [f for f in files.values() if not (run.output_dir / f).is_file()]
                if missing:
                    raise StageFailure(f"Blender finished without writing {missing[0]}")
                frames.append({"index": index, "source_frame": clip["frames"][index], "files": files,
                               "pivot": list(cells[clip["name"]][1]) if clip["stationary"] else found["pivot"]})
            directions[direction] = frames
            frames_made += len(frames)
        entries.append({"name": clip["name"], "fps": entry["fps"], "loop": entry["loop"], "stationary": entry["stationary"],
                        "root_motion": entry["root_motion"], "directions": directions, "bounds": bounds[clip["name"]],
                        "frame": {"width": cells[clip["name"]][0], "height": cells[clip["name"]][0]},
                        "pivot": list(cells[clip["name"]][1])})
        run.check_cancel()
    document = {
        "schema_version": RENDER_SCHEMA_VERSION,
        "wearable": True,
        "camera": shown["camera"],
        "elevation": shown["elevation"],
        "height": height,
        "frame": shown["frame"],
        "pivot": pivot,
        "px_per_unit": shown["px_per_unit"],
        "toon": shown["toon"],
        "bands": shown["bands"],
        "materials": materials,
        "depth_range": result["depth_range"],
        "passes": list(PASSES),
        "directions": list(names),
        "clips": entries,
        "body": {"asset": body.asset_id, "materials": len(shown["materials"])},
        "seconds": {"measure": round(measure_seconds, 2), "render": round(render_seconds, 2),
                    "frames": frames_made, "per_frame": round(render_seconds / max(frames_made, 1), 4)},
        "outside_cell": outside,
        "margin": margin,
    }
    (run.output_dir / "render.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def _body_clip_cell(entry: dict[str, Any], side: int, pivot: list[float]) -> tuple[int, list[float]]:
    """A body clip's cell, `(side, pivot)`: its own (ticket 0303), or the body's when its `render.json` is older."""
    if "frame" not in entry:
        return side, pivot
    return int(entry["frame"]["width"]), [float(v) for v in entry["pivot"]]


def _launch_cells(run: StageRun, args: dict[str, Any], cells: dict[str, tuple[int, list[float]]]) -> dict[str, Any]:
    """Blender for the clips in `args`, once for each cell size they need (the frame and pivot are the scene's); one result."""
    groups: dict[tuple[int, tuple[float, ...]], list[dict[str, Any]]] = {}
    for clip in args["clips"]:
        side, at = cells[clip["name"]]
        groups.setdefault((side, tuple(at)), []).append(clip)
    merged: dict[str, Any] | None = None
    for (size, place), group in groups.items():
        found = launch(run, "render_frames", {**args, "clips": group, "frame": [size, size], "pivot": list(place)})
        if merged is None:
            merged = found
        else:
            if found["depth_range"] != merged["depth_range"]:
                raise StageFailure("Blender gave two depth ranges for one Wearable", fix=f"kiripix run {run.asset_id} render --force")
            merged["frames"] = {**merged["frames"], **found["frames"]}
    assert merged is not None
    return merged


def device_fallback(args: dict[str, Any], result: dict[str, Any]) -> bool:
    return bool(args["device"] == "gpu" and str(result.get("device", "")).startswith("cpu"))


def check_wearable_render(run: StageRun) -> list[Finding]:
    """`wearable.outside_cell`: frames of the Wearable that reach past the body's cell, with the body's `cell_margin` that
    holds them."""
    path = run.output_dir / "render.json"
    if not path.is_file():
        return []
    document = _json(path)
    outside = document.get("outside_cell") or []
    if not outside:
        return []
    body = str(document["body"]["asset"])
    shown = ", ".join(f"{f['clip']} {f['direction']} {f['frame']}" for f in outside[:MOST_FRAMES_NAMED])
    more = f" and {len(outside) - MOST_FRAMES_NAMED} more" if len(outside) > MOST_FRAMES_NAMED else ""
    cell = document["frame"]["width"]
    message = (f"{len(outside)} frames of the Wearable reach past the {cell} px cell of its body {body} (clip, direction, frame: "
               f"{shown}{more}), so they are cut off and don't stack on the body's")
    position = Position(asset=run.asset_id, stage="render")
    margin = document.get("margin")
    if isinstance(margin, int):
        return [Finding(code="wearable.outside_cell", severity="error", message=message, position=position,
                        fix=f"kiripix set {body} render cell_margin={margin}")]
    return [Finding(code="wearable.outside_cell", severity="error", message=message, position=position,
                    owner_action=f"No cell_margin of {body}'s render holds these frames: change the Wearable so that it stays "
                                 "closer to the body.")]
