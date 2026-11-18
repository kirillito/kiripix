"""Trial 0238: print the hand's rest geometry in model.blend. blender -b --factory-startup -P probe.py -- <model.blend>"""
import sys, bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
print("OBJECTS", [(o.name, o.type, o.parent.name if o.parent else None) for o in bpy.data.objects])
print("ROOT scale", [o.scale[:] for o in bpy.data.objects if o.name == "model_root"])
for n in ["RightHand", "RightHandIndex1", "RightHandMiddle1", "RightHandRing1", "RightHandPinky1", "RightHandThumb1", "RightHandIndex2", "RightForeArm"]:
    b = arm.data.bones["mixamorig:" + n]
    print(n, [round(x, 4) for x in (arm.matrix_world @ b.head_local)], [round(x, 4) for x in (arm.matrix_world @ b.tail_local)], round(b.length, 4))
print("world scale", arm.matrix_world.to_scale()[:], arm.matrix_world.to_translation()[:])
