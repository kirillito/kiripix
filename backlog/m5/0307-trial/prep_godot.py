"""0307 trial, lever B in Godot: pack one body's frames trimmed (the same packer as measure.py), write the two atlases and frames.json
(per frame: its region in the atlas, its margin in the cell, and the untrimmed cell PNG that Godot's drawing must equal), into godot_check/data/."""
import json, shutil, sys
import numpy as np
from PIL import Image
from common import *
from lib import *

name = sys.argv[1] if len(sys.argv) > 1 else "mc03_male_clothes01"
asset, cell, sheet = load_asset(PROJ / "assets/character" / name)
piv = sheet["pivot"]
out = HERE / "godot_check/data"
shutil.rmtree(out, ignore_errors=True)
(out / "cells").mkdir(parents=True)
ents = []
for clip, c in asset.items():
    for d in EIGHT:
        for i, (col, nor) in enumerate(c["frames"][d]):
            b = opaque_box(col, nor)
            if b is not None:
                ents.append((clip, d, i, col, nor, b))
sizes = [(e[5][2] - e[5][0], e[5][3] - e[5][1]) for e in ents]
aw, ah, pos = pack(sizes)
col = np.zeros((ah, aw, 4), np.uint8)
nor = np.zeros((ah, aw, 4), np.uint8)
frames = []
for e, (x, y), (w, h) in zip(ents, pos, sizes):
    b = e[5]
    col[y:y + h, x:x + w] = e[3][b[1]:b[3], b[0]:b[2]]
    nor[y:y + h, x:x + w] = e[4][b[1]:b[3], b[0]:b[2]]
    cp = f"cells/{e[0]}_{e[1]}_{e[2]:03d}.png"
    Image.fromarray(e[3], "RGBA").save(out / cp)
    Image.fromarray(e[4], "RGBA").save(out / cp.replace(".png", "_n.png"))
    frames.append({"clip": e[0], "dir": e[1], "index": e[2], "region": [x, y, w, h], "margin": [b[0], b[1], cell[0] - w, cell[1] - h], "cell": cp})
Image.fromarray(col, "RGBA").save(out / "color.png")
Image.fromarray(nor, "RGBA").save(out / "normal.png")
(out / "frames.json").write_text(json.dumps({"cell": cell, "pivot": [piv["x"], piv["y"]], "atlas": [aw, ah], "frames": frames}))
print(name, len(frames), "frames", aw, ah)
