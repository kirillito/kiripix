"""Trial 0238 step 5: hand_r (0237's point on the hand bone, the wrist joint) against the grip (the socket bone `grip_r`, in the Model
that came back from a glb round trip), per frame and direction, in render px."""
import json, sys, math
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
import numpy as np
names = ["idle", "walk", "attack", "phone"]
args = base_args(SC / "rt/model_bone.blend", names, side=78, pivot=(39, 67), output=SC / "render/points_tmp", measure=False,
                 points=[{"name": "hand_r", "target": "mixamorig:RightHand"}, {"name": "grip_r", "target": "grip_r"}])
# no pixels needed: but render_frames has no points-only mode, so render the first frame of each clip's list only is not enough;
# use every frame (the poses), on CPU
res = blender("held_render.py", args, SC / "points_result.json")
rows = {}
for clip, dirs in res["frames"].items():
    stats = {"dist": [], "same_px": 0, "within1": 0, "n": 0}
    for d, frames in dirs.items():
        for f in frames:
            h, g = f["points"]["hand_r"], f["points"]["grip_r"]
            stats["dist"].append(math.hypot(h["x"] - g["x"], h["y"] - g["y"]))
            fx, fy = math.floor(h["x"]) - math.floor(g["x"]), math.floor(h["y"]) - math.floor(g["y"])
            stats["same_px"] += int(fx == 0 and fy == 0); stats["within1"] += int(abs(fx) <= 1 and abs(fy) <= 1); stats["n"] += 1
    dist = np.array(stats["dist"])
    rows[clip] = {"frames": stats["n"], "dist_px_min": round(float(dist.min()), 2), "dist_px_mean": round(float(dist.mean()), 2),
                  "dist_px_max": round(float(dist.max()), 2), "same_pixel": stats["same_px"], "within_1px_each_axis": stats["within1"]}
    print(clip, rows[clip])
(HERE / "points_check.json").write_text(json.dumps(rows, indent=1))
