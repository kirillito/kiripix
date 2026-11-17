"""Trial 0170: is the stick in the object mask, and does `finish` outline it? Usage: check_outline.py <projS asset folder>"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

asset = Path(sys.argv[1])
render = json.loads((asset / "work/render/render.json").read_text())
weapon = next(m["index"] for m in render["materials"] if m["name"] == "weapon")
stats = dict(frames=0, stick_px=0, stick_px_in_mask=0, frames_without_stick=0, edge_neighbours=0, edge_outlined=0,
             stick_colour_px_after_palette=0, idle_walk_weapon_px=0)
outline_colours = set()
for clip in render["clips"]:
    for direction, frames in clip["directions"].items():
        for frame in frames:
            mat = np.array(Image.open(asset / "work/render" / frame["files"]["material"]))
            mask = np.array(Image.open(asset / "work/render" / frame["files"]["mask"])) > 0
            fin = np.array(Image.open(asset / "work/finish" / frame["files"]["color"]).convert("RGBA"))
            stick = mat == weapon
            if clip["name"] != "attack":
                stats["idle_walk_weapon_px"] += int(stick.sum())
                continue
            stats["frames"] += 1
            stats["stick_px"] += int(stick.sum())
            stats["stick_px_in_mask"] += int((stick & mask).sum())
            stats["frames_without_stick"] += int(not stick.any())
            opaque = fin[..., 3] > 0
            near = np.zeros_like(stick)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                near |= np.roll(np.roll(stick, dy, 0), dx, 1)
            edge = near & ~mask  # background pixels beside a stick pixel
            stats["edge_neighbours"] += int(edge.sum())
            stats["edge_outlined"] += int((edge & opaque).sum())
            outline_colours |= {tuple(int(v) for v in c) for c in fin[edge & opaque][:, :3]}
stats["outline_colours_next_to_stick"] = sorted(outline_colours)
print(json.dumps(stats, indent=1))
