"""0307 trial: the lever table. For each body: the atlas as the real `sheet` Stage makes it (a near-square grid of cells), then each lever
alone and all together, on disk (PNG bytes, this trial's encoder for every row) and in VRAM (RGBA8: width x height x 4 a texture, colour and normal).
Levers: A fewer frames (the `_f<N>` Assets, rendered by the real Stages at min(fps, N)), B trimmed cells (MaxRects, 1 px gap),
C mirrored directions (ne e se drawn from nw w sw), D duplicate frames shared (identical colour and normal), E indexed PNG (disk only).
Usage: measure.py [asset-suffix ...]; writes measures.json."""
import json, sys, math
from pathlib import Path
import numpy as np
from common import *
from lib import *

OUT = HERE / "measures.json"
res = json.loads(OUT.read_text()) if OUT.exists() else {}


def grid(n):
    cols = math.ceil(math.sqrt(n))
    return cols, math.ceil(n / cols)


def entries(asset, dirs, dedupe):
    """[(clip, dir, index, col, nor)] kept; with dedupe, one entry per distinct frame (and the number of frames that share it)."""
    seen, out, total = {}, [], 0
    for clip, c in asset.items():
        for d in dirs:
            for i, (col, nor) in enumerate(c["frames"][d]):
                total += 1
                k = frame_key(col, nor) if dedupe else (clip, d, i)
                if k in seen:
                    continue
                seen[k] = 1
                out.append((clip, d, i, col, nor))
    return out, total


def build(asset, cell, dirs=EIGHT, trim=False, dedupe=False, index=False):
    ents, total = entries(asset, dirs, dedupe)
    w, h = cell
    if trim:
        boxes = [opaque_box(e[3], e[4]) for e in ents]
        keep = [(e, b) for e, b in zip(ents, boxes) if b is not None]
        sizes = [(b[2] - b[0], b[3] - b[1]) for _, b in keep]
        aw, ah, pos = pack(sizes)
        col = np.zeros((ah, aw, 4), np.uint8)
        nor = np.zeros((ah, aw, 4), np.uint8)
        for ((e, b), (x, y), (sw, sh)) in zip(keep, pos, sizes):
            col[y:y + sh, x:x + sw] = e[3][b[1]:b[3], b[0]:b[2]]
            nor[y:y + sh, x:x + sw] = e[4][b[1]:b[3], b[0]:b[2]]
        cells = len(keep)
    else:
        cols, rows = grid(len(ents))
        aw, ah = cols * w, rows * h
        col = np.zeros((ah, aw, 4), np.uint8)
        nor = np.zeros((ah, aw, 4), np.uint8)
        for n, e in enumerate(ents):
            x, y = (n % cols) * w, (n // cols) * h
            col[y:y + h, x:x + w] = e[3]
            nor[y:y + h, x:x + w] = e[4]
        cells = len(ents)
    if index:
        tc, tn = colour_table([col]), colour_table([nor])
        disk_c, disk_n = len(indexed_png(col, tc)), len(indexed_png(nor, tn))
        n_c, n_n = len(tc), len(tn)
    else:
        disk_c, disk_n = png_bytes(col), png_bytes(nor)
        n_c = n_n = None
    return {"frames_total": total, "cells": cells, "atlas": [aw, ah], "area_px": aw * ah,
            "disk_colour": disk_c, "disk_normal": disk_n, "disk": disk_c + disk_n,
            "vram": aw * ah * 4 * 2, "colours": n_c, "normal_colours": n_n}


LEVERS = {
    "none": {},
    "B_trim": {"trim": True},
    "C_mirror": {"dirs": FIVE},
    "D_dedupe": {"dedupe": True},
    "E_indexed": {"index": True},
    "B+C+D+E": {"trim": True, "dirs": FIVE, "dedupe": True, "index": True},
}


def main():
    suffixes = sys.argv[1:] or [""] + [f"_f{n}" for n in (8, 6, 4)]
    for a in BODIES:
        for suf in suffixes:
            name = a + suf
            adir = PROJ / "assets/character" / name
            if not (adir / "work/sheet/sheet.json").exists():
                print("missing", name)
                continue
            asset, cell, sheet = load_asset(adir)
            real = {k: (adir / "work/sheet" / v).stat().st_size for k, v in sheet["files"].items()}
            entry = {"cell": cell, "real_sheet_bytes": real, "real_atlas": [sheet["atlas"]["width"], sheet["atlas"]["height"]],
                     "clips": {c: {"fps": v["fps"], "frames": len(v["frames"]["s"])} for c, v in asset.items()}}
            for lname, kw in LEVERS.items():
                entry[lname] = build(asset, cell, **kw)
                print(name, lname, entry[lname]["cells"], entry[lname]["atlas"], entry[lname]["disk"], flush=True)
            res[name] = entry
            OUT.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
