"""the hand mesh's extent in the hand frame (rest): vertices weighted > 0.5 to the right hand and its finger bones"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy, grip
import numpy as np
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name != "Icosphere" and any(m.type == "ARMATURE" for m in o.modifiers))
frame, k = grip.rest_frame(arm)
inv = frame.inverted()
names = {g.index: g.name for g in body.vertex_groups}
pts = []
for v in body.data.vertices:
    w = {names[g.group]: g.weight for g in v.groups}
    hand = sum(x for n, x in w.items() if n.startswith("mixamorig:RightHand"))
    if hand > 0.5:
        pts.append(inv @ (body.matrix_world @ v.co))
a = np.array([list(p) for p in pts])
print("HAND n", len(a), "min", a.min(0).round(3), "max", a.max(0).round(3))
print("HAND percentiles z", np.percentile(a[:, 2], [5, 50, 95]).round(3), "x", np.percentile(a[:, 0], [5, 50, 95]).round(3), "y", np.percentile(a[:, 1], [5, 50, 95]).round(3))
print("KNUCKLE", (inv @ k)[:])
for y0, y1 in [(0.0, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 0.20), (0.20, 0.26)]:
    s = a[(a[:, 1] >= y0) & (a[:, 1] < y1)]
    if len(s):
        print("SLAB y", y0, y1, "n", len(s), "x", s[:, 0].min().round(3), s[:, 0].max().round(3), "z", s[:, 2].min().round(3), s[:, 2].max().round(3))
