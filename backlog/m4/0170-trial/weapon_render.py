"""Trial 0170 (not Kiripix code): run inside Blender, `blender -b -P weapon_render.py -- <args.json> <result.json>`.

It runs kiripix/blender/render_frames.py unchanged (its source is executed here, minus the final `main()` call) and adds one
placeholder weapon the way option (a) of ticket 0170 would: a cylinder with its own material, parented to a named bone, drawn
only in the named clips. `args` is render_frames's args plus
    "weapon": {"clips": ["attack"], "bone": "RightHand", "length": 1.0, "radius": 0.025, "material": "weapon",
               "colour": [r, g, b], "grip": 0.25, "along": "x", "number_last": false}
`length` is in Blender units after the Model is normalised (the Model is `model_height` units tall: 1 unit is 1 m for a 1.8 m
character); `grip` is how far from its lower end the hand holds it; `along` is the bone's local axis the stick lies on.
With `"weapon": null` nothing is added, which is the control. The result carries `"timing"`: seconds per phase.
"""
import json
import sys
import time
from pathlib import Path

RENDER_FRAMES = Path(__file__).resolve().parents[3] / "kiripix" / "blender" / "render_frames.py"

_code = RENDER_FRAMES.read_text(encoding="utf-8")
assert _code.rstrip().endswith("main()")
_code = _code.rstrip()[: -len("main()")]
_ns: dict = {"__name__": "render_frames_trial"}
exec(compile(_code, str(RENDER_FRAMES), "exec"), _ns)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

WEAPON: dict | None = None
STICK = None
timing: dict = {}


def add_stick(armature, spec: dict) -> None:
    global STICK
    bones = {_ns["plain"](b.name): b for b in armature.data.bones}
    bone = bones[_ns["plain"](spec["bone"])]
    bpy.context.view_layer.update()
    # the hand in the rest pose, in world space
    rest = armature.matrix_world @ bone.matrix_local
    axes = {"x": 0, "y": 1, "z": 2}
    along = Vector(rest.to_3x3().col[axes[spec.get("along", "x")]]).normalized()
    length, radius, grip = float(spec["length"]), float(spec["radius"]), float(spec["grip"])
    # the grip point: part way along the hand bone
    head, tail = rest.translation, rest @ Vector((0, bone.length, 0))
    grip_point = head + (tail - head) * 0.45
    up = Vector((0, 0, 1))
    # a mesh: a cylinder along +Z, length `length`, its lower end at z = -grip
    mesh = bpy.data.meshes.new("weapon_mesh")
    builder = bmesh.new()
    bmesh.ops.create_cone(builder, cap_ends=True, cap_tris=False, segments=8, radius1=radius, radius2=radius, depth=length)
    bmesh.ops.translate(builder, vec=(0, 0, length / 2 - grip), verts=builder.verts)
    builder.to_mesh(mesh)
    builder.free()
    obj = bpy.data.objects.new("weapon", mesh)
    bpy.context.scene.collection.objects.link(obj)
    material = bpy.data.materials.new(spec.get("material", "weapon"))
    material.use_nodes = True
    r, g, b = spec.get("colour", [0.55, 0.32, 0.12])
    material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (r, g, b, 1.0)
    material.diffuse_color = (r, g, b, 1.0)
    obj.data.materials.append(material)
    rotation = up.rotation_difference(along).to_matrix().to_4x4()
    obj.matrix_world = Matrix.Translation(grip_point) @ rotation
    bpy.context.view_layer.update()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone.name
    obj.matrix_parent_inverse = (armature.matrix_world @ bone.matrix_local).inverted() @ Matrix.Identity(4)
    # parent_type BONE puts the child at the bone's tail; correct so the stick stays where it was placed
    bpy.context.view_layer.update()
    want = Matrix.Translation(grip_point) @ rotation
    obj.matrix_parent_inverse = obj.matrix_parent_inverse @ (obj.matrix_world.inverted() @ want)
    bpy.context.view_layer.update()
    STICK = obj
    if spec.get("only"):  # the stick alone, to count how much of it the body hides
        for other in bpy.data.objects:
            if other.type == "MESH" and other is not obj:
                other.hide_render = True


_open_posable = _ns["open_posable"]


def open_posable(args):
    armature, root_bone = _open_posable(args)
    if WEAPON is not None:
        add_stick(armature, WEAPON)
        if WEAPON.get("number_last"):
            pass  # handled in number_materials below
    return armature, root_bone


_begin_clip = _ns["begin_clip"]


def begin_clip(armature, clip, root_bone, ground):
    timing.setdefault("loop_start", time.perf_counter())
    if STICK is not None:
        STICK.hide_render = clip["name"] not in WEAPON["clips"]
    return _begin_clip(armature, clip, root_bone, ground)


_end_clip = _ns["end_clip"]


def end_clip(armature, state):
    _end_clip(armature, state)
    timing["loop_end"] = time.perf_counter()


_number_materials = _ns["number_materials"]


def number_materials():
    found = _number_materials()
    if WEAPON is not None and WEAPON.get("number_last"):
        mats = [m for m in found if m["name"] != WEAPON["material"]]
        mats.append({"index": 0, "name": WEAPON["material"]})
        for index, m in enumerate(mats, start=1):
            m["index"] = index
            bpy.data.materials[m["name"]].pass_index = index
        found = mats
    return found


_ns.update(open_posable=open_posable, begin_clip=begin_clip, end_clip=end_clip, number_materials=number_materials)
# render_frames's functions look each other up in its namespace, so the overrides above are the ones it calls

if __name__ == "__main__" or True:
    separator = sys.argv.index("--")
    args = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    result_path = Path(sys.argv[separator + 2])
    WEAPON = args.pop("weapon", None)
    started = time.perf_counter()
    try:
        result = _ns["render"](args)
    except Exception as error:
        import traceback
        traceback.print_exc()
        result = {"error": f"{type(error).__name__}: {error}"}
    timing["total_s"] = time.perf_counter() - started
    if "loop_end" in timing:
        timing["loop_s"] = timing.pop("loop_end") - timing.pop("loop_start")
    result["timing"] = timing
    result_path.write_text(json.dumps(result), encoding="utf-8")
