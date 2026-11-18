"""Render the phone (a) in `phone` and the stick in `attack`, one frame, 8 directions, then upscale to a quick look. Usage: run_view.py <clip> <thing> [frameindex]"""
import sys, json, shutil; sys.path.insert(0,"C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
from PIL import Image
clip, thing = sys.argv[1], sys.argv[2]
idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
out = SC / "view"
shutil.rmtree(out, ignore_errors=True)
args = base_args(SC / "things/model_a.blend", [clip], output=out, side=96, pivot=(48, 80), held_per_clip={clip: [thing]})
for c in args["clips"]:
    c["frames"] = c["frames"][idx: idx + 1]
r = blender("held_render.py", args, SC / "view_result.json")
tiles = [Image.open(out / f"color/{clip}/{d}/000.png").convert("RGBA") for d in EIGHT]
sheet = Image.new("RGBA", (96 * 4 * 4, 96 * 4 * 2), (58, 62, 72, 255))
for i, t in enumerate(tiles):
    big = t.resize((384, 384), Image.NEAREST)
    sheet.alpha_composite(big, ((i % 4) * 384, (i // 4) * 384))
sheet.convert("RGB").save(SC / f"view_{clip}_{thing}.png")
print(r["timing"], r["held_materials"], r["materials"][-3:])
