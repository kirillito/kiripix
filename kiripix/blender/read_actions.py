"""Run inside Blender: list the actions of a file with their frame ranges, the file's frame rate, and how far the root
travels in each, for the `clips` Stage.

    blender -b -P read_actions.py -- <args.json> <result.json>

args:   {"input": <a .glb, .fbx or .blend>, "root": [<bone names to try as the root, in order>],
         "travel": <false to skip the sampling of the root's travel: default true>,
         "optional": <true to answer a file with no armature instead of failing: default false>}
result: {"armature", "bones": [<bone names>], "fps", "height", "root", "actions": [{"name", "start", "end", "travel"}]}

The `inspect` Probe (ticket 0123) calls it with `travel` false and `optional` true: it lists a file's bones and actions and
needs neither the root nor the travel. A file with no armature then answers `armature` null and no bones or actions.

`fps` is the file's own frame rate. `height` is the armature's extent upright in the rest pose and `travel` is the furthest
the root bone's head gets from where it is at the action's first frame, on the ground plane (x and y), both in the file's own
units; the Stage uses their ratio, so a rigged file that isn't normalised to Kiripix's height needs no conversion. The root is
the first of `root` that is a bone of the rig (names compare without a `mixamorig:` prefix, in lower case).
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

MAX_SAMPLES = 600  # frames looked at per action: a long action is sampled evenly


def progress(done: int, total: int, message: str) -> None:
    print(f"PROGRESS {done} {total} {message}", flush=True)


def import_model(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if suffix == ".glb" or suffix == ".gltf":
            bpy.ops.import_scene.gltf(filepath=str(path))
        elif suffix == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(path))
        else:
            raise ValueError(f"{path.name} is not a .glb, .fbx or .blend")


def plain(name: str) -> str:
    return "".join(c for c in name.split(":")[-1].lower() if c.isalnum())


def find_root(armature, wanted: list) -> str:
    bones = {plain(b.name): b.name for b in armature.data.bones}
    for name in wanted:
        if plain(name) in bones:
            return bones[plain(name)]
    return armature.data.bones[0].name


def rest_height(armature) -> float:
    zs = []
    for bone in armature.data.bones:
        for point in (bone.head_local, bone.tail_local):
            zs.append((armature.matrix_world @ point).z)
    return (max(zs) - min(zs)) if zs else 0.0


def assign(armature, action) -> None:
    armature.animation_data_create()
    armature.animation_data.action = action
    slots = list(getattr(action, "slots", []))
    if slots and getattr(armature.animation_data, "action_slot", None) is None:
        armature.animation_data.action_slot = slots[0]  # Blender 5: an action's channels sit in a slot


def read(args: dict) -> dict:
    progress(0, 2, "importing")
    import_model(Path(args["input"]))
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    scene = bpy.context.scene
    fps = scene.render.fps / (scene.render.fps_base or 1.0)
    if not armatures:
        if not args.get("optional"):
            raise ValueError("the file has no armature")
        progress(2, 2, "done")
        return {"armature": None, "bones": [], "fps": fps, "height": 0.0, "root": None, "actions": []}
    armature = armatures[0]
    sample = bool(args.get("travel", True))
    root = find_root(armature, list(args.get("root", [])))
    height = rest_height(armature)
    actions = []
    total = len(bpy.data.actions)
    for index, action in enumerate(sorted(bpy.data.actions, key=lambda a: a.name)):
        progress(1, 2, f"action {index + 1} of {total}")
        start, end = int(round(action.frame_range[0])), int(round(action.frame_range[1]))
        if not sample:
            actions.append({"name": action.name, "start": start, "end": end, "travel": 0.0})
            continue
        assign(armature, action)
        step = max(1, math.ceil((end - start + 1) / MAX_SAMPLES))
        first = None
        travel = 0.0
        for frame in range(start, end + 1, step):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            point = armature.matrix_world @ armature.pose.bones[root].head
            flat = Vector((point.x, point.y))
            first = flat if first is None else first
            travel = max(travel, (flat - first).length)
        actions.append({"name": action.name, "start": start, "end": end, "travel": travel})
    if armature.animation_data is not None:
        armature.animation_data.action = None
    progress(2, 2, "done")
    return {"armature": armature.name, "bones": [b.name for b in armature.data.bones], "fps": fps, "height": height, "root": root, "actions": actions}


def main() -> None:
    separator = sys.argv.index("--")
    args = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    result_path = Path(sys.argv[separator + 2])
    try:
        result = read(args)
    except Exception as error:  # reported to Kiripix as the Stage's failure
        result = {"error": f"{type(error).__name__}: {error}"}
    result_path.write_text(json.dumps(result), encoding="utf-8")


main()
