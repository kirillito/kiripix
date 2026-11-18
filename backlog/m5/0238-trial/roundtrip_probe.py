"""blender -b -P roundtrip_probe.py -- <model.blend> : is grip_r there, parented to the hand bone, and where, in the hand's frame?"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, grip
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
e = bpy.data.objects.get("grip_r")
print("EMPTY", e and (e.type, e.parent.name if e.parent else None, e.parent_type, e.parent_bone))
if e:
    frame, _ = grip.rest_frame(arm)
    local = frame.inverted() @ e.matrix_world.translation
    scale = arm.matrix_world.to_scale()[0] * bpy.data.objects["model_root"].scale[0]
    print("LOCAL in the hand frame (Model units)", [round(x, 4) for x in local], "world", [round(x, 4) for x in e.matrix_world.translation])
    print("AXES dot", [round(float(frame.to_3x3().inverted() @ (e.matrix_world.to_3x3() @ __import__("mathutils").Vector(v)).normalized() @ __import__("mathutils").Vector(v)), 4) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1))])
