"""Trial 0238: as roundtrip_make.py, but the socket is a BONE `grip_r` under the right hand bone (edit mode), not an Empty."""
import json, sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, grip
from mathutils import Matrix, Euler
a = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=a[0])
cfg = json.loads(Path(a[2]).read_text())["socket"]
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bpy.context.view_layer.update()
frame, _ = grip.rest_frame(arm)
want = frame @ (Matrix.Translation(cfg["offset"]) @ Euler([math.radians(x) for x in cfg["turn"]], "XYZ").to_matrix().to_4x4())
hand = next(b.name for b in arm.data.bones if b.name.endswith("RightHand"))
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones.new("grip_r")
eb.parent = arm.data.edit_bones[hand]
scale = arm.matrix_world.to_scale()[0]
m = arm.matrix_world.inverted() @ want   # armature space
eb.head = m.translation
eb.tail = m.translation + m.to_3x3().col[1].normalized() * (0.04 / scale)
eb.align_roll(m.to_3x3().col[2])
bpy.ops.object.mode_set(mode="OBJECT")
print("WANT", [round(x, 5) for x in want.translation])
bpy.ops.export_scene.gltf(filepath=a[1], export_format="GLB", export_animations=False)
