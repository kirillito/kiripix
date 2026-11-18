import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, grip
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
b = arm.data.bones.get("grip_r")
print("BONE", b and (b.parent.name, [round(x, 4) for x in (arm.matrix_world @ b.head_local)]))
if b:
    frame, _ = grip.rest_frame(arm)
    m = arm.matrix_world @ b.matrix_local
    print("LOCAL in the hand frame", [round(x, 4) for x in (frame.inverted() @ m.translation)])
    print("AXES", [[round(x, 3) for x in (frame.to_3x3().inverted() @ m.to_3x3().col[i])] for i in range(3)])
