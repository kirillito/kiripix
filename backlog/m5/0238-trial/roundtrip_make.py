"""Trial 0238: what chargen would do. blender -b --factory-startup -P roundtrip_make.py -- <in.glb> <out.glb> <config.json>
Imports a built character's .glb, adds the socket Empty `grip_r` on the right hand bone from the hand's own rest geometry (grip.py),
and exports a .glb with the same call generate.py makes."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, grip
from mathutils import Matrix, Euler
import math
a = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
cfg = json.loads(Path(a[2]).read_text())["socket"]
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bpy.context.view_layer.update()
frame, _ = grip.rest_frame(arm)
want = frame @ (Matrix.Translation(cfg["offset"]) @ Euler([math.radians(x) for x in cfg["turn"]], "XYZ").to_matrix().to_4x4())
bone = next(b.name for b in arm.data.bones if b.name.endswith("RightHand"))
e = bpy.data.objects.new("grip_r", None)
bpy.context.scene.collection.objects.link(e)
e.parent, e.parent_type, e.parent_bone = arm, "BONE", bone
e.matrix_parent_inverse = Matrix.Identity(4)
bpy.context.view_layer.update()
e.matrix_parent_inverse = e.matrix_world.inverted() @ want
bpy.context.view_layer.update()
print("WANT", [round(x, 5) for x in want.translation], "HAND", [round(x, 5) for x in (arm.matrix_world @ arm.data.bones[bone].head_local)])
bpy.ops.export_scene.gltf(filepath=a[1], export_format="GLB", export_animations=False)
