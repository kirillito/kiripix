"""Run inside Blender: read a rigged file (or the normalised Model) and report its armature, for the `rig` Stage.

    blender -b -P validate_rig.py -- <args.json> <result.json>

args:   {"input": <a .glb, .fbx or .blend>}
result: {"armature", "bones", "vertices", "size": [x, y, z]}

`armature` is the first armature's name (null when there is none) and `bones` its bone names. `vertices` and `size` describe
the character's meshes (the skinned ones, as `normalise_model.py` counts them) in the rest pose, in the same way as `normalise_model.py` does: `vertices` counts the distinct points of the
meshes whatever their size and place, and `size` is the bounds' extent in the file's own units (Mixamo's differ from
Kiripix's, so the Stage compares proportions only).
"""

import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


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


def is_skinned(obj: "bpy.types.Object") -> bool:
    return any(m.type == "ARMATURE" and m.object is not None for m in obj.modifiers) or         (obj.parent is not None and obj.parent.type == "ARMATURE")


def character_meshes() -> list:
    """The same rule as `normalise_model.py`: with an armature, only the skinned meshes; never a pose bone's custom shape."""
    shapes = {b.custom_shape for o in bpy.data.objects if o.type == "ARMATURE" for b in o.pose.bones if b.custom_shape}
    every = [o for o in bpy.data.objects if o.type == "MESH" and o not in shapes]
    if not any(o.type == "ARMATURE" for o in bpy.data.objects):
        return every
    return [o for o in every if is_skinned(o)] or every


def main() -> None:
    separator = sys.argv.index("--")
    args = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    result_path = Path(sys.argv[separator + 2])
    try:
        result = validate(args)
    except Exception as error:  # reported to Kiripix as the Stage's failure
        result = {"error": f"{type(error).__name__}: {error}"}
    result_path.write_text(json.dumps(result), encoding="utf-8")


def validate(args: dict) -> dict:
    progress(0, 2, "importing")
    import_model(Path(args["input"]))
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    for armature in armatures:
        armature.data.pose_position = "REST"  # the rest pose, so the size doesn't depend on the action showing
    bpy.context.view_layer.update()

    progress(1, 2, "measuring")
    graph = bpy.context.evaluated_depsgraph_get()
    meshes = [o.evaluated_get(graph) for o in character_meshes()]
    if not meshes:
        raise ValueError("the file has no mesh")
    low, high = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for evaluated in meshes:
        for corner in evaluated.bound_box:
            world = evaluated.matrix_world @ Vector(corner)
            low = Vector(min(a, b) for a, b in zip(low, world))
            high = Vector(max(a, b) for a, b in zip(high, world))
    longest = max(high - low) or 1.0
    points = set()
    for evaluated in meshes:
        for vertex in evaluated.data.vertices:
            world = evaluated.matrix_world @ vertex.co
            points.add(tuple(round((world[i] - low[i]) / longest, 3) for i in range(3)))
    progress(2, 2, "done")
    return {
        "armature": armatures[0].name if armatures else None,
        "bones": [bone.name for bone in armatures[0].data.bones] if armatures else [],
        "vertices": len(points),
        "size": [high[i] - low[i] for i in range(3)],
    }


main()
