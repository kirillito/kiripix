"""Trial 0153 (not Kiripix code): one rig, a body and separate layer objects.
blender -b --factory-startup -P assemble.py -- <gen folder> <out .blend> <info .json>
Opens gen/body.blend (the underwear body, bald), brings in the meshes built by generate.py (hairp, jacket, coat), splits each by
material into layer objects on the body's armature, and models a backpack by hand. Materials are renamed `<layer>.<name>`, so
every layer's materials are its own (a ramp per layer, as 0152 says). model_root is made from the body alone, so every
scenario has one scale and one pivot."""
import json, sys
import bpy, bmesh
from mathutils import Vector

gen, out, info_path = sys.argv[sys.argv.index("--") + 1:][:3]
bpy.ops.wm.open_mainfile(filepath=f"{gen}/body.blend")
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH")
body.name = "body"

def bring(name):
    with bpy.data.libraries.load(f"{gen}/{name}.blend", link=False) as (src, dst):
        dst.meshes = [name]
    return bpy.data.meshes[name] if name in bpy.data.meshes else dst.meshes[0]

LAYERS = {  # layer -> (file, materials it keeps)
    "hair": ("hairp", ["hair"]),
    "jacket": ("jacket", ["top", "sleeve", "hood", "under"]),
    "legs": ("jacket", ["bottom", "bottom_r", "shoes", "sole"]),
    "coat": ("coat", ["top", "sleeve", "collar"]),
}
loaded = {}
made = []
for layer, (file, keep) in LAYERS.items():
    if file not in loaded:
        loaded[file] = bring(file)
    mesh = loaded[file].copy()
    obj = bpy.data.objects.new(layer, mesh)
    bpy.context.scene.collection.objects.link(obj)
    wanted = {i for i, m in enumerate(mesh.materials) if m is not None and m.name.split(".")[0] in keep}
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in wanted], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(mesh); bm.free()
    for i, m in enumerate(list(mesh.materials)):
        if i in wanted:
            mesh.materials[i] = m.copy()
            mesh.materials[i].name = f"{layer}.{m.name.split('.')[0]}"
    obj.parent = arm  # the layer's mesh is in the body's own space (generate.py joins parts into the body)
    obj.matrix_parent_inverse = body.matrix_parent_inverse.copy()
    obj.matrix_basis = body.matrix_basis.copy()
    mod = obj.modifiers.new("Armature", "ARMATURE"); mod.object = arm
    made.append(obj)

# the backpack: a box behind the torso and two straps over the shoulders, all on the upper spine
J = {b.name.split(":")[-1]: arm.matrix_world @ b.head_local for b in arm.data.bones}
spine, neck = J["Spine2"], J["Neck"]
near = [(body.matrix_world @ v.co) for v in body.data.vertices if abs((body.matrix_world @ v.co).z - spine.z) < 0.08 and abs((body.matrix_world @ v.co).x) < 0.2]
back_y, front_y = max(p.y for p in near), min(p.y for p in near)
info = {"back_y": back_y, "front_y": front_y, "spine2_z": spine.z, "neck_z": neck.z}

def box(name, centre, size, mat_name, rgb):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + centre[0], v.co.y * size[1] + centre[1], v.co.z * size[2] + centre[2]))
    mesh = bpy.data.meshes.new(name); bm.to_mesh(mesh); bm.free()
    mat = bpy.data.materials.new(mat_name); mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    mat.diffuse_color = (*rgb, 1)
    mesh.materials.append(mat)
    return mesh

pack_mesh = box("pack", (0, back_y + 0.075, spine.z - 0.02), (0.36, 0.15, 0.44), "pack.bag", (0.8, 0.4, 0.1))
pack = bpy.data.objects.new("pack", pack_mesh)
bpy.context.scene.collection.objects.link(pack)
straps = []
for sx in (-0.1, 0.1):
    straps.append(box("strap", (sx, (back_y + front_y) / 2, (neck.z + spine.z - 0.1) / 2), (0.045, back_y - front_y + 0.03, neck.z - spine.z + 0.1 + 0.0), "pack.strap", (0.55, 0.28, 0.07)))
# the straps as one mesh with the pack
bm = bmesh.new(); bm.from_mesh(pack_mesh)
for s in straps:
    bm.from_mesh(s)
bm.to_mesh(pack_mesh); bm.free()
pack_mesh.materials.clear()
for n, rgb in (("pack.bag", (0.8, 0.4, 0.1)), ("pack.strap", (0.55, 0.28, 0.07))):
    mat = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    mat.diffuse_color = (*rgb, 1)
    pack_mesh.materials.append(mat)
n_box = 8
for i, p in enumerate(pack_mesh.polygons):
    p.material_index = 0 if p.index < 6 else 1
bone = next(b.name for b in arm.data.bones if b.name.endswith("Spine2"))
vg = pack.vertex_groups.new(name=bone)
vg.add(list(range(len(pack_mesh.vertices))), 1.0, "REPLACE")
pack.parent = arm  # the pack's coordinates are world: put its world matrix at identity
pack.matrix_parent_inverse = arm.matrix_world.inverted()
mod = pack.modifiers.new("Armature", "ARMATURE"); mod.object = arm
made.append(pack)

bpy.context.view_layer.update()
# model_root from the body alone (what `model` would do for the body)
lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
for v in body.data.vertices:
    w = body.matrix_world @ v.co
    lo = Vector(map(min, lo, w)); hi = Vector(map(max, hi, w))
scale = 2.0 / (hi.z - lo.z)
root = bpy.data.objects.new("model_root", None)
bpy.context.scene.collection.objects.link(root)
for o in [o for o in bpy.data.objects if o.parent is None and o is not root]:
    o.parent = root; o.matrix_parent_inverse = root.matrix_world.inverted()
centre = (lo + hi) / 2
root.scale = (scale,) * 3
root.location = (-centre.x * scale, -centre.y * scale, -lo.z * scale)
info["scale"] = scale
info["objects"] = {o.name: {"verts": len(o.data.vertices), "materials": [m.name for m in o.data.materials]} for o in [body] + made}
for o in bpy.data.objects:
    if o.type == "MESH":
        print("OBJ", o.name, len(o.data.vertices), [m.name for m in o.data.materials])
bpy.ops.wm.save_as_mainfile(filepath=out)
json.dump(info, open(info_path, "w"), indent=1)
