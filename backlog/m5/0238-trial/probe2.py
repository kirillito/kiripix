import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rf, grip, bpy
ns = rf.load()
args = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
arm, root = ns["open_posable"](args)
bpy.context.view_layer.update()
for o in bpy.data.objects: print("OBJ", o.name, o.type, o.parent.name if o.parent else None, o.parent_type, o.hide_render)
ph = bpy.data.objects["phone"]; g = bpy.data.objects["grip_r"]
print("REST phone", ph.matrix_world.translation[:], "grip", g.matrix_world.translation[:], "hand", (arm.matrix_world @ arm.pose.bones["mixamorig:RightHand"].head)[:])
ns["assign"](arm, ns["action_for"](args["clips"][0])); ns["pose"](arm, args["clips"][0]["frames"][5])
print("POSED phone", ph.matrix_world.translation[:], "grip", g.matrix_world.translation[:], "hand", (arm.matrix_world @ arm.pose.bones["mixamorig:RightHand"].head)[:])
print("DIM", ph.dimensions[:], [v.co[:] for v in ph.data.vertices][:2])
