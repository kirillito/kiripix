"""Trial 0238 (not Kiripix code): blender -b --factory-startup -P build_things.py -- <args.json> <result.json>
args: {"model": <model.blend>, "out": <folder>, "socket": {"offset": [x, y, z], "turn": [rx, ry, rz deg]} (in the hand frame of grip.py,
Model units), "things": {name: {"offset", "turn"}} (in the socket's frame)}
Writes <out>/model_a.blend: the Model with an Empty `grip_r` parented to the right hand bone and the things (phone, stick, rake)
parented to the Empty, hidden from renders. Writes <out>/layer_<thing>.blend per thing: the Model with the thing alone as a mesh
skinned to the right hand at weight 1 and the body deleted (a Wearable, ticket 0291). Units: the Model is 2.0 tall (1 unit = 0.9 m)."""
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, bmesh  # noqa: E402
import grip  # noqa: E402
from mathutils import Matrix, Euler, Vector  # noqa: E402

args = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
result_path = Path(sys.argv[sys.argv.index("--") + 2])
out = Path(args["out"]); out.mkdir(parents=True, exist_ok=True)
M = 1.0 / 0.9  # units per metre (a 1.8 m body is 2.0 units)
HAND = "mixamorig:RightHand"


def mat(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    m.diffuse_color = (*rgb, 1)
    return m


def box(bm, centre, size, material_index=0):
    before = set(bm.faces)
    r = bmesh.ops.create_cube(bm, size=1.0)
    verts = r["verts"]
    for v in verts:
        v.co = Vector((v.co.x * size[0] + centre[0], v.co.y * size[1] + centre[1], v.co.z * size[2] + centre[2]))
    for f in set(bm.faces) - before:
        f.material_index = material_index
    return [f for f in set(bm.faces) - before]


def cylinder(bm, start, end, radius, material_index=0, sides=8):
    a, b = Vector(start), Vector(end)
    before = set(bm.faces)
    r = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=sides, radius1=radius, radius2=radius, depth=(b - a).length)
    rot = Vector((0, 0, 1)).rotation_difference((b - a).normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=r["verts"])
    for f in set(bm.faces) - before:
        f.material_index = material_index


def make_thing(name):
    """The thing in the socket's frame (X across the hand, Y along the fingers, Z out of the back of the hand), units of the Model.
    Returns (mesh, [materials])."""
    bm = bmesh.new()
    if name == "phone":
        w, l, t = 0.085 * M, 0.16 * M, 0.011 * M
        box(bm, (0, 0, 0), (w, l, t), 0)
        # the screen: a thin lighter slab on the palm-down face (-Z faces the palm; the screen faces away from the palm, so +Z)
        box(bm, (0, 0, t / 2 + 0.0015), (w * 0.86, l * 0.9, 0.003), 1)
        mats = [mat("phone", (0.08, 0.10, 0.16)), mat("phone_screen", (0.55, 0.75, 0.95))]
    elif name == "stick":
        L = 1.0 * M
        cylinder(bm, (-0.65 * L, 0, 0), (0.35 * L, 0, 0), 0.04)  # 1 m, held 35 % up from the lower end
        mats = [mat("stick", (0.55, 0.32, 0.12))]
    elif name == "rake":
        L = 1.5 * M
        cylinder(bm, (-0.8 * L, 0, 0), (0.2 * L, 0, 0), 0.03, 0)  # the handle, 1.5 m
        hx = -0.8 * L  # the head: a bar across the handle's low end and 7 tines
        box(bm, (hx, 0, 0), (0.025, 0.36 * M, 0.02), 1)
        for i in range(7):
            box(bm, (hx - 0.11 * M, (i - 3) * 0.06 * M, 0), (0.22 * M, 0.012, 0.012), 1)
        mats = [mat("rake", (0.55, 0.32, 0.12)), mat("rake_head", (0.62, 0.62, 0.55))]
    else:
        raise SystemExit("unknown thing " + name)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh); bm.free()
    for m in mats:
        mesh.materials.append(m)
    return mesh


def local_matrix(spec):
    e = Euler([math.radians(x) for x in spec.get("turn", [0, 0, 0])], "XYZ")
    return Matrix.Translation(spec.get("offset", [0, 0, 0])) @ e.to_matrix().to_4x4()


def build(kind):
    """kind 'a': the Model with the socket and the things parented to it. kind <thing>: the Wearable file for that thing."""
    bpy.ops.wm.open_mainfile(filepath=args["model"])
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name != "Icosphere" and any(m.type == "ARMATURE" for m in o.modifiers))
    for stray in [o for o in bpy.data.objects if o.name == "Icosphere"]:
        bpy.data.objects.remove(stray, do_unlink=True)
    bpy.context.view_layer.update()
    frame, _ = grip.rest_frame(arm)
    sock = args["socket"]
    want = frame @ local_matrix(sock)  # the socket's world matrix in the rest pose
    info = {"socket_world": [list(r) for r in want]}
    if kind == "a":
        empty = bpy.data.objects.new("grip_r", None)
        empty.empty_display_type = "ARROWS"; empty.empty_display_size = 0.05
        bpy.context.scene.collection.objects.link(empty)
        empty.parent = arm; empty.parent_type = "BONE"; empty.parent_bone = HAND
        empty.matrix_parent_inverse = Matrix.Identity(4)
        bpy.context.view_layer.update()
        empty.matrix_parent_inverse = empty.matrix_world.inverted() @ want  # P_bone @ inv = want, whatever the bone's head or tail
        bpy.context.view_layer.update()
        assert (empty.matrix_world.translation - want.translation).length < 1e-5, "socket not placed"
        for name in args["things"]:
            obj = bpy.data.objects.new(name, make_thing(name))
            bpy.context.scene.collection.objects.link(obj)
            obj.parent = empty
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_basis = local_matrix(args["things"][name])  # scale-free: the Empty's world matrix has no scale
            obj.hide_render = True
        bpy.ops.wm.save_as_mainfile(filepath=str(out / "model_a.blend"))
    else:
        mesh = make_thing(kind)
        mesh.transform(want @ local_matrix(args["things"][kind]))  # baked in the rest pose, world space
        obj = bpy.data.objects.new(kind, mesh)
        bpy.context.scene.collection.objects.link(obj)
        group = obj.vertex_groups.new(name=HAND)
        group.add(list(range(len(mesh.vertices))), 1.0, "REPLACE")
        modifier = obj.modifiers.new("Armature", "ARMATURE"); modifier.object = arm
        obj.parent = arm; obj.matrix_parent_inverse = arm.matrix_world.inverted()
        obj.matrix_basis = Matrix.Identity(4)
        bpy.data.objects.remove(body, do_unlink=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out / f"layer_{kind}.blend"))
    return info


info = {}
for kind in ["a"] + list(args["things"]):
    info[kind] = build(kind)
result_path.write_text(json.dumps(info))
