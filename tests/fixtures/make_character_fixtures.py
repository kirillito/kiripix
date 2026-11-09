"""Build the character test fixtures in Blender 5.2 (ticket 0100).

Run it from the repository root; it overwrites the files in `tests/fixtures/characters/`:

    blender --background --factory-startup --python tests/fixtures/make_character_fixtures.py

(`blender` is `%KIRIPIX_BLENDER%` or the one on PATH.) Optional: add `-- <output folder>` to write elsewhere.

Writes:
- `rigged.glb`, `rigged.fbx`: a tiny humanoid (about 100 triangles), Mixamo-style bone names (`mixamorig:Hips`, ...)
  under a `root` bone at ground level (the pivot is the ground point under it), two coloured parts (a `skin`
  and a `cloth` material), and two short actions: `idle` (stationary) and `walk` (the feet move in place).
- `no_rig.glb`, `no_rig.fbx`: the same body parts with no armature, for the `rig` Stage's "no rig" path.

The geometry is made here from boxes, so the files carry no third-party licence. Everything is deterministic.
"""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector

FPS = 24
FRAMES = 24

# (bone, parent, head, tail) in metres; the figure is about 1.7 m tall and stands on z = 0, facing -Y.
BONES = [
    ("root", None, (0, 0, 0), (0, 0, 0.15)),
    ("mixamorig:Hips", "root", (0, 0, 0.95), (0, 0, 1.05)),
    ("mixamorig:Spine", "mixamorig:Hips", (0, 0, 1.05), (0, 0, 1.2)),
    ("mixamorig:Spine1", "mixamorig:Spine", (0, 0, 1.2), (0, 0, 1.35)),
    ("mixamorig:Neck", "mixamorig:Spine1", (0, 0, 1.35), (0, 0, 1.45)),
    ("mixamorig:Head", "mixamorig:Neck", (0, 0, 1.45), (0, 0, 1.7)),
    ("mixamorig:LeftShoulder", "mixamorig:Spine1", (0, 0, 1.35), (0.15, 0, 1.35)),
    ("mixamorig:LeftArm", "mixamorig:LeftShoulder", (0.15, 0, 1.35), (0.4, 0, 1.35)),
    ("mixamorig:LeftForeArm", "mixamorig:LeftArm", (0.4, 0, 1.35), (0.65, 0, 1.35)),
    ("mixamorig:RightShoulder", "mixamorig:Spine1", (0, 0, 1.35), (-0.15, 0, 1.35)),
    ("mixamorig:RightArm", "mixamorig:RightShoulder", (-0.15, 0, 1.35), (-0.4, 0, 1.35)),
    ("mixamorig:RightForeArm", "mixamorig:RightArm", (-0.4, 0, 1.35), (-0.65, 0, 1.35)),
    ("mixamorig:LeftUpLeg", "mixamorig:Hips", (0.1, 0, 0.95), (0.1, 0, 0.5)),
    ("mixamorig:LeftLeg", "mixamorig:LeftUpLeg", (0.1, 0, 0.5), (0.1, 0, 0.08)),
    ("mixamorig:LeftFoot", "mixamorig:LeftLeg", (0.1, 0, 0.08), (0.1, -0.15, 0.0)),
    ("mixamorig:RightUpLeg", "mixamorig:Hips", (-0.1, 0, 0.95), (-0.1, 0, 0.5)),
    ("mixamorig:RightLeg", "mixamorig:RightUpLeg", (-0.1, 0, 0.5), (-0.1, 0, 0.08)),
    ("mixamorig:RightFoot", "mixamorig:RightLeg", (-0.1, 0, 0.08), (-0.1, -0.15, 0.0)),
]

# (name, bone, material, centre, size): every part is a box weighted fully to one bone.
PARTS = [
    ("pelvis", "mixamorig:Hips", "cloth", (0, 0, 1.0), (0.3, 0.18, 0.12)),
    ("torso", "mixamorig:Spine1", "cloth", (0, 0, 1.2), (0.34, 0.2, 0.3)),
    ("head", "mixamorig:Head", "skin", (0, 0, 1.58), (0.2, 0.2, 0.24)),
    ("arm_l", "mixamorig:LeftArm", "skin", (0.4, 0, 1.35), (0.5, 0.1, 0.1)),
    ("arm_r", "mixamorig:RightArm", "skin", (-0.4, 0, 1.35), (0.5, 0.1, 0.1)),
    ("leg_l", "mixamorig:LeftUpLeg", "cloth", (0.1, 0, 0.5), (0.12, 0.12, 0.9)),
    ("leg_r", "mixamorig:RightUpLeg", "cloth", (-0.1, 0, 0.5), (0.12, 0.12, 0.9)),
    ("foot_l", "mixamorig:LeftFoot", "skin", (0.1, -0.05, 0.04), (0.12, 0.3, 0.08)),
    ("foot_r", "mixamorig:RightFoot", "skin", (-0.1, -0.05, 0.04), (0.12, 0.3, 0.08)),
]

COLOURS = {"skin": (0.9, 0.7, 0.55, 1.0), "cloth": (0.15, 0.35, 0.8, 1.0)}


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS


def materials() -> dict[str, "bpy.types.Material"]:
    made = {}
    for name, colour in COLOURS.items():
        material = bpy.data.materials.new(name)
        material.diffuse_color = colour
        material.use_nodes = True
        shader = material.node_tree.nodes["Principled BSDF"]
        shader.inputs["Base Color"].default_value = colour
        shader.inputs["Roughness"].default_value = 1.0
        made[name] = material
    return made


def box_object(name: str, material: "bpy.types.Material", centre: tuple, size: tuple) -> "bpy.types.Object":
    mesh = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = centre
    corners = [(cx + x * sx, cy + y * sy, cz + z * sz) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(corners, [], faces)
    mesh.update()
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def body(mats: dict) -> "bpy.types.Object":
    """Join the parts into one mesh named `Body`, a vertex group per bone, each box weighted to its bone."""
    objects = []
    for name, bone, material, centre, size in PARTS:
        obj = box_object(name, mats[material], centre, size)
        group = obj.vertex_groups.new(name=bone)
        group.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")
        objects.append(obj)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = "Body"
    joined.data.name = "Body"
    for polygon in joined.data.polygons:
        polygon.use_smooth = False
    return joined


def armature() -> "bpy.types.Object":
    data = bpy.data.armatures.new("Armature")
    obj = bpy.data.objects.new("Armature", data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, head, tail in BONES:
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = Vector(head), Vector(tail)
        if parent:
            bone.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def key(rig: "bpy.types.Object", bone: str, frame: int, degrees: tuple) -> None:
    pose = rig.pose.bones[bone]
    pose.rotation_mode = "XYZ"
    pose.rotation_euler = Euler(tuple(math.radians(d) for d in degrees), "XYZ")
    pose.keyframe_insert("rotation_euler", frame=frame)


def action(rig: "bpy.types.Object", name: str, keys: dict) -> None:
    """`keys`: bone -> {frame: (rx, ry, rz) in degrees}. Bones not listed stay at rest."""
    made = bpy.data.actions.new(name)
    made.use_fake_user = True
    rig.animation_data.action = made
    for bone in rig.pose.bones:
        bone.rotation_euler = (0, 0, 0)
    for bone, frames in keys.items():
        for frame, degrees in frames.items():
            key(rig, bone, frame, degrees)
    made.use_frame_range = True
    made.frame_start, made.frame_end = 1, FRAMES + 1


def actions(rig: "bpy.types.Object") -> None:
    rig.animation_data_create()
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    end = FRAMES + 1
    mid = FRAMES // 2 + 1
    action(rig, "idle", {  # stationary: a slow breath in the spine, the feet and the root never move
        "mixamorig:Spine": {1: (0, 0, 0), mid: (4, 0, 0), end: (0, 0, 0)},
        "mixamorig:Head": {1: (0, 0, 0), mid: (-3, 0, 0), end: (0, 0, 0)},
    })
    swing = 30
    action(rig, "walk", {  # the feet move in place: the root has no keys, so there is no root motion
        "mixamorig:LeftUpLeg": {1: (swing, 0, 0), mid: (-swing, 0, 0), end: (swing, 0, 0)},
        "mixamorig:RightUpLeg": {1: (-swing, 0, 0), mid: (swing, 0, 0), end: (-swing, 0, 0)},
        "mixamorig:LeftLeg": {1: (0, 0, 0), mid // 2: (-35, 0, 0), mid: (0, 0, 0), end: (0, 0, 0)},
        "mixamorig:RightLeg": {1: (0, 0, 0), mid: (0, 0, 0), mid + mid // 2: (-35, 0, 0), end: (0, 0, 0)},
        "mixamorig:LeftArm": {1: (-20, 0, 0), mid: (20, 0, 0), end: (-20, 0, 0)},
        "mixamorig:RightArm": {1: (20, 0, 0), mid: (-20, 0, 0), end: (20, 0, 0)},
    })
    for bone in rig.pose.bones:
        bone.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.animation_data.action = None


def export(folder: Path, stem: str, with_animation: bool) -> None:
    glb = str(folder / f"{stem}.glb")
    fbx = str(folder / f"{stem}.fbx")
    options = {"export_animation_mode": "ACTIONS"} if with_animation else {"export_animations": False}
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_yup=True, **options)
    bpy.ops.export_scene.fbx(filepath=fbx, bake_anim=with_animation, bake_anim_use_all_actions=with_animation,
                             bake_anim_use_nla_strips=False, add_leaf_bones=False)


def build_rigged(folder: Path) -> None:
    clear_scene()
    mats = materials()
    mesh = body(mats)
    rig = armature()
    mesh.parent = rig
    modifier = mesh.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig
    actions(rig)
    export(folder, "rigged", True)


def build_no_rig(folder: Path) -> None:
    clear_scene()
    body(materials())
    export(folder, "no_rig", False)


def main() -> None:
    argv = sys.argv
    given = argv[argv.index("--") + 1:] if "--" in argv else []
    folder = Path(given[0]) if given else Path(__file__).resolve().parent / "characters"
    folder.mkdir(parents=True, exist_ok=True)
    build_rigged(folder)
    build_no_rig(folder)


main()
