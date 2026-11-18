"""Trial 0238 (not Kiripix code): blender -b --factory-startup -P grip_metrics.py -- <args.json> <result.json>
For every frame of the named clips: where the fist's hollow is, in the hand bone's own frame (units of the Model; px = units x
px_per_unit), and the fist's across-axis. Shows how rigid the hand is, so how well one fixed socket fits."""
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rf, grip  # noqa: E402
import bpy  # noqa: E402

ns = rf.load()
args = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text())
out_path = Path(sys.argv[sys.argv.index("--") + 2])
arm, root = ns["open_posable"](args)
bpy.context.view_layer.update()
bones = arm.pose.bones
hand = bones["mixamorig:RightHand"]
frame0, _ = grip.rest_frame(arm)
ground = None
res = {"rest_origin_hand_local": None, "clips": {}}
rest_hand = arm.matrix_world @ arm.data.bones["mixamorig:RightHand"].matrix_local
res["knuckle_centre_hand_local"] = list((rest_hand.inverted() @ grip.rest_frame(arm)[1]))
res["rest_frame_hand_local"] = [list(r) for r in (rest_hand.inverted() @ grip.rest_frame(arm)[0])]
for clip in args["clips"]:
    state = ns["begin_clip"](arm, clip, root, None) if False else None
    ns["assign"](arm, ns["action_for"](clip))
    rows = []
    for frame in clip["frames"]:
        ns["pose"](arm, frame)
        # the hand bone's pose matrix relative to its rest (so the hollow is in the bone's own frame: the bone is rigid, fingers aren't)
        hm = arm.matrix_world @ hand.matrix
        # pose matrix `hand.matrix` is the bone's pose frame in armature space, with its head at origin: hand-local = inverse
        c = hm.inverted() @ grip.fist_centre(arm)
        a = hm.to_3x3().inverted() @ grip.fist_axis(arm)
        rows.append({"c": [round(x, 5) for x in c], "a": [round(x, 5) for x in a]})
    res["clips"][clip["name"]] = rows
ns["reset_pose"](arm)
out_path.write_text(json.dumps(res))
