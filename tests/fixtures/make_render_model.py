"""Build the render test Model in Blender 5.2 (ticket 0281): `tests/fixtures/characters/render_model.glb`.

Run it from the repository root; it overwrites the file:

    blender --background --factory-startup --python tests/fixtures/make_render_model.py

(`blender` is `%KIRIPIX_BLENDER%` or the one on PATH.) Optional: `-- <output folder> <stem> <scale>` writes
`<folder>/<stem>.glb` with every length multiplied by `<scale>` (the tests make a smaller copy of the rig that way, for the
base's height ratio, ticket 0165).

What it holds, for the marked tests that run the real `render` on it (`tests/cli/test_blender_render.py`):
- a humanoid of about 400 faces, the figure about 1.7 m tall on z = 0 facing -Y, with Mixamo-style bone names
  (`mixamorig:Hips`, ...) under a `root` bone at ground level, and a hand bone on each arm (`mixamorig:RightHand`);
- four materials: `skin` and `cloth` for the body, and `eye_white` and `eye_iris` for the eyes. Each eye is a flat patch of
  each eye material just in front of the face, on the Model's right (-X) and left (+X) side of the head;
- two actions: `idle` (the spine and head breathe; frame 1 is the rest pose) and `walk` (the legs and arms swing in
  place: at frame 1 and frame 25 one side forward, at frame 13 the opposite, with the middle of the two the rest pose).

The geometry is made here from boxes, so the file carries no third-party licence. Everything is deterministic.

A Wearable (ticket 0291): a fourth argument, `<part>`, is `body` (the default: the file above), `vest` (the same skeleton and
a vest and a skirt, the materials `vest` and `trim`, and nothing else: a Wearable's file) or `both` (the body and the vest in one
file: the full render to compare a stack with). The vest is a thin shell on the front of the torso and the hips, inside the body's
bounding box in x, y and z, so the body alone, the vest alone and both are normalised the same: the same scale and place, hence
the same camera. It is wider than the torso, so from behind (`n`) the body hides most of it, and the skirt sits where the
swinging legs pass in front of it and behind it. The committed files: `render_vest.glb` (`-- tests/fixtures/characters
render_vest 1 vest`) and `render_with_vest.glb` (`render_with_vest 1 both`).
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Vector

FPS = 24
FRAMES = 24

# (bone, parent, head, tail) in metres.
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
    ("mixamorig:LeftHand", "mixamorig:LeftForeArm", (0.65, 0, 1.35), (0.8, 0, 1.35)),
    ("mixamorig:RightShoulder", "mixamorig:Spine1", (0, 0, 1.35), (-0.15, 0, 1.35)),
    ("mixamorig:RightArm", "mixamorig:RightShoulder", (-0.15, 0, 1.35), (-0.4, 0, 1.35)),
    ("mixamorig:RightForeArm", "mixamorig:RightArm", (-0.4, 0, 1.35), (-0.65, 0, 1.35)),
    ("mixamorig:RightHand", "mixamorig:RightForeArm", (-0.65, 0, 1.35), (-0.8, 0, 1.35)),
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
    ("hand_l", "mixamorig:LeftHand", "skin", (0.7, 0, 1.35), (0.2, 0.14, 0.14)),
    ("hand_r", "mixamorig:RightHand", "skin", (-0.7, 0, 1.35), (0.2, 0.14, 0.14)),
    ("leg_l", "mixamorig:LeftUpLeg", "cloth", (0.1, 0, 0.5), (0.12, 0.12, 0.9)),
    ("leg_r", "mixamorig:RightUpLeg", "cloth", (-0.1, 0, 0.5), (0.12, 0.12, 0.9)),
    ("foot_l", "mixamorig:LeftFoot", "skin", (0.1, -0.05, 0.04), (0.12, 0.3, 0.08)),
    ("foot_r", "mixamorig:RightFoot", "skin", (-0.1, -0.05, 0.04), (0.12, 0.3, 0.08)),
]

# (name, material, x centre, z centre, width, height, y): flat patches on the face (its front is y = -0.1), the iris in front
# of the white. One of each per side of the head, the Model's right eye on -X.
EYES = [
    (f"eye_{side}_{kind}", f"eye_{kind}", x, 1.60, width, height, y)
    for side, x in (("r", -0.05), ("l", 0.05))
    for kind, width, height, y in (("white", 0.08, 0.06, -0.1005), ("iris", 0.045, 0.04, -0.101))
]

COLOURS = {"skin": (0.9, 0.7, 0.55, 1.0), "cloth": (0.15, 0.35, 0.8, 1.0),
           "eye_white": (0.95, 0.95, 0.95, 1.0), "eye_iris": (0.1, 0.2, 0.05, 1.0)}

# The Wearable's parts, as PARTS: a vest on the chest and a skirt at the hips, both just in front of the body (its front is
# y = -0.1; its feet reach y = -0.2, so these stay inside the body's bounds).
VEST_PARTS = [
    ("vest", "mixamorig:Spine1", "vest", (0, -0.125, 1.2), (0.5, 0.05, 0.32)),
    ("skirt", "mixamorig:Hips", "trim", (0, -0.13, 0.9), (0.4, 0.06, 0.2)),
]
VEST_COLOURS = {"vest": (0.7, 0.15, 0.15, 1.0), "trim": (0.9, 0.8, 0.2, 1.0)}

SCALE = 1.0
PART = "body"


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS


def new_material(name: str, colour: tuple) -> "bpy.types.Material":
    material = bpy.data.materials.new(name)
    material.diffuse_color = colour
    material.use_nodes = True
    shader = material.node_tree.nodes["Principled BSDF"]
    shader.inputs["Base Color"].default_value = colour
    shader.inputs["Roughness"].default_value = 1.0
    return material


def materials() -> dict[str, "bpy.types.Material"]:
    made = {}
    for name, colour in COLOURS.items():
        if PART == "vest":
            break
        material = bpy.data.materials.new(name)
        material.diffuse_color = colour
        material.use_nodes = True
        shader = material.node_tree.nodes["Principled BSDF"]
        shader.inputs["Base Color"].default_value = colour
        shader.inputs["Roughness"].default_value = 1.0
        made[name] = material
    for name, colour in VEST_COLOURS.items():
        if PART != "body":
            made[name] = new_material(name, colour)
    return made


def scaled(values: tuple) -> tuple:
    return tuple(v * SCALE for v in values)


def box_object(name: str, material: "bpy.types.Material", centre: tuple, size: tuple) -> "bpy.types.Object":
    """A box cut once each way (24 faces), so the Model has a few hundred faces."""
    mesh = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in scaled(size))
    cx, cy, cz = scaled(centre)
    corners = [(cx + x * sx, cy + y * sy, cz + z * sz) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(corners, [], faces)
    mesh.update()
    cut = bmesh.new()
    cut.from_mesh(mesh)
    bmesh.ops.subdivide_edges(cut, edges=list(cut.edges), cuts=1, use_grid_fill=True)
    cut.to_mesh(mesh)
    cut.free()
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def patch_object(name: str, material: "bpy.types.Material", x: float, z: float, width: float, height: float,
                 y: float) -> "bpy.types.Object":
    """One quad facing -Y."""
    mesh = bpy.data.meshes.new(name)
    x0, x1, z0, z1 = x - width / 2, x + width / 2, z - height / 2, z + height / 2
    mesh.from_pydata([scaled((x0, y, z0)), scaled((x1, y, z0)), scaled((x1, y, z1)), scaled((x0, y, z1))], [], [(0, 1, 2, 3)])
    mesh.update()
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def body(mats: dict) -> "bpy.types.Object":
    """Join the parts into one mesh named `Body`, a vertex group per bone, each part weighted to its bone."""
    objects = []
    if PART != "vest":
        for name, bone, material, centre, size in PARTS:
            objects.append((box_object(name, mats[material], centre, size), bone))
        for name, material, x, z, width, height, y in EYES:
            objects.append((patch_object(name, mats[material], x, z, width, height, y), "mixamorig:Head"))
    if PART != "body":
        for name, bone, material, centre, size in VEST_PARTS:
            objects.append((box_object(name, mats[material], centre, size), bone))
    for obj, bone in objects:
        group = obj.vertex_groups.new(name=bone)
        group.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")
    bpy.ops.object.select_all(action="DESELECT")
    for obj, _ in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0][0]
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
        bone.head, bone.tail = Vector(scaled(head)), Vector(scaled(tail))
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
    action(rig, "idle", {  # stationary: a slow breath in the spine; frame 1 is the rest pose
        "mixamorig:Spine": {1: (0, 0, 0), mid: (4, 0, 0), end: (0, 0, 0)},
        "mixamorig:Head": {1: (0, 0, 0), mid: (-3, 0, 0), end: (0, 0, 0)},
    })
    swing = 30
    action(rig, "walk", {  # in place; frame 1 and frame 13 are opposite poses, and their middle is the rest pose
        "mixamorig:LeftUpLeg": {1: (swing, 0, 0), mid: (-swing, 0, 0), end: (swing, 0, 0)},
        "mixamorig:RightUpLeg": {1: (-swing, 0, 0), mid: (swing, 0, 0), end: (-swing, 0, 0)},
        "mixamorig:LeftArm": {1: (-20, 0, 0), mid: (20, 0, 0), end: (-20, 0, 0)},
        "mixamorig:RightArm": {1: (20, 0, 0), mid: (-20, 0, 0), end: (20, 0, 0)},
    })
    for bone in rig.pose.bones:
        bone.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.animation_data.action = None


def build(path: Path) -> None:
    clear_scene()
    mesh = body(materials())
    rig = armature()
    mesh.parent = rig
    modifier = mesh.modifiers.new("Armature", "ARMATURE")
    modifier.object = rig
    actions(rig)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_animation_mode="ACTIONS")


def main() -> None:
    global SCALE, PART
    argv = sys.argv
    given = argv[argv.index("--") + 1:] if "--" in argv else []
    folder = Path(given[0]) if given else Path(__file__).resolve().parent / "characters"
    stem = given[1] if len(given) > 1 else "render_model"
    SCALE = float(given[2]) if len(given) > 2 else 1.0
    PART = given[3] if len(given) > 3 else "body"
    if PART not in ("body", "vest", "both"):
        raise SystemExit(f"the part is body, vest or both, not {PART}")
    build(folder / f"{stem}.glb")


main()
