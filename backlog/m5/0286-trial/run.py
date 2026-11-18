import json, subprocess, sys, threading, time
from pathlib import Path
import numpy as np
from PIL import Image
from common import *
import suggest
from kiripix.runners.sam2 import Sam2

class Vram:
    def __init__(self):
        self.peak = 0; self.stop = False
    def poll(self):
        while not self.stop:
            v = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])
            self.peak = max(self.peak, v); time.sleep(0.1)

def base():
    return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])

def score(sugg, key):
    best = {k: (0.0, None) for k in key}
    hit_s, rows = set(), []
    for s in sugg:
        ious = {k: iou(s["mask"], m) for k, m in key.items()}
        k, v = max(ious.items(), key=lambda kv: (kv[1], kv[0]))
        s["best_key"], s["iou"] = k, round(v, 3)
        for kk, vv in ious.items():
            if vv > best[kk][0]:
                best[kk] = (vv, s["name"])
    hits = {k: v for k, (v, n) in best.items() if v > 0.7}
    # a suggestion is a hit if it matches a key layer above 0.7; extra suggestions of an already-hit layer are duplicates
    matched = [s for s in sugg if s["iou"] > 0.7]
    first = {}
    for s in matched:
        first.setdefault(s["best_key"], s)
    dups = len(matched) - len(first)
    false = [s for s in sugg if s["iou"] <= 0.7]
    cover = np.zeros(next(iter(key.values())).shape, bool)
    for s in sugg: cover |= s["mask"]
    allkey = np.zeros_like(cover)
    for m in key.values(): allkey |= m
    return {"key": len(key), "suggested": len(sugg), "hits": len(hits), "hit_layers": sorted(hits), "near": sorted(k for k, (v, n) in best.items() if 0.3 < v <= 0.7),
            "false": len(false), "duplicates": dups, "best_iou": {k: [round(v, 2), n] for k, (v, n) in best.items()},
            "key_pixel_recall": round(float((cover & allkey).sum() / allkey.sum()), 3), "false_names": [s["name"] for s in false]}

def outline(m):
    e = m.copy()
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
    return m & ~e

def overlay(rgba, key, sugg, path):
    im = rgba[..., :3].copy()
    for m in key.values(): im[outline(m)] = (255, 0, 0)        # the Owner's: red
    for s in sugg: im[outline(s["mask"])] = (0, 255, 0) if s["iou"] > 0.7 else (255, 255, 0)  # hit green, false yellow
    Image.fromarray(im).save(path)

import os
RISE0 = os.environ.get("RISE0") == "1"
def main():
    OUT.mkdir(exist_ok=True)
    rooms = sys.argv[1:] or ROOMS
    if RISE0: suggest.RISE = 0
    runner = Sam2()
    wdir = ART / ".kiripix/weights/sam2.1-small"
    b0 = base()
    vr = Vram(); vr.peak = b0
    t = threading.Thread(target=vr.poll, daemon=True); t.start()
    runner.load(wdir, "auto"); print("device", runner.device_used, "baseline MiB", b0, flush=True)
    summary = {}
    for room in rooms:
        rgba, solid, pit, key = load(room)
        rgba = np.ascontiguousarray(rgba)
        res = {}
        t0 = time.time(); fl = suggest.flood_method(rgba, solid); res["flood"] = (fl, time.time() - t0)
        t0 = time.time(); cl, bx = suggest.sam_methods(runner, rgba, solid); dt = time.time() - t0
        res["click"] = (cl, dt); res["box"] = (bx, dt)   # one embed shared; time is for both
        au = []
        if not RISE0: t0 = time.time(); au = suggest.auto_method(runner, rgba, solid); res["auto"] = (au, time.time() - t0)
        st = []
        if not RISE0: t0 = time.time(); st = suggest.standing_method(runner, rgba, solid, pit); res["stand"] = (st, time.time() - t0)
        # combined: click, box, flood, auto; keep the first of near-duplicates (IoU > 0.7)
        comb = []
        for s in cl + bx + fl + au + st:
            if not any(iou(s["mask"], c["mask"]) > 0.7 for c in comb): comb.append(s)
        res["combined"] = (comb, None)
        if RISE0: res = {k + "_r0": v for k, v in res.items() if k != "combined"}
        summary[room] = {}
        for meth, (sg, dt) in res.items():
            sc = score(sg, key); sc["seconds"] = None if dt is None else round(dt, 1)
            summary[room][meth] = sc
            overlay(rgba, key, sg, OUT / f"overlay_{room}_{meth}.png")
            print(room, meth, {k: v for k, v in sc.items() if k not in ("best_iou",)}, flush=True)
            (OUT / f"suggestions_{room}_{meth}.json").write_text(json.dumps([{k: v for k, v in s.items() if k != "mask"} | {"pixels": int(s["mask"].sum())} for s in sg], indent=1, default=int))
    vr.stop = True
    summary["_vram"] = {"baseline_mib": b0, "peak_mib": vr.peak, "delta_mib": vr.peak - b0}
    (OUT / ("summary_r0.json" if RISE0 else "summary.json")).write_text(json.dumps(summary, indent=1))
    print("vram", summary["_vram"])
main()
