"""Debug look (not a sheet): the thing in the hand at 4x the real pixel density, 8 directions. Usage: run_zoom.py <clip> <thing> <frameindex> [config.json]"""
import sys, json, shutil; sys.path.insert(0,"C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
from PIL import Image
clip, thing, idx = sys.argv[1], sys.argv[2], int(sys.argv[3])
out = SC / "zoom"
shutil.rmtree(out, ignore_errors=True)
args = base_args(SC / "things/model_a.blend", [clip], output=out, side=4 * 78, pivot=(4 * 39, 4 * 67), held_per_clip={clip: [thing]})
args["px_per_unit"] *= 4
args["points"] = [{"name": "hand_r", "target": "mixamorig:RightHand"}]
for c in args["clips"]:
    c["frames"] = c["frames"][idx: idx + 1]
res = blender("held_render.py", args, SC / "zoom_result.json")
W = 140
sheet = Image.new("RGBA", (W * 4, W * 2), (58, 62, 72, 255))
for i, d in enumerate(EIGHT):
    t = Image.open(out / f"color/{clip}/{d}/000.png").convert("RGBA")
    p = res["frames"][clip][d][0]["points"]["hand_r"]
    cx, cy = int(p["x"]), int(p["y"])
    t = t.crop((cx - W // 2, cy - W // 2, cx + W // 2, cy + W // 2))
    sheet.alpha_composite(t, ((i % 4) * W, (i // 4) * W))
sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST); sheet.convert("RGB").save(SC / f"zoom_{clip}_{thing}.png")
