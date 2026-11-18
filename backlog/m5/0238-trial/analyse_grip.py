import json, math, sys
import numpy as np
SC = "C:/Users/Kirill/AppData/Local/Temp/claude/e7ccd5c4395c2f79/d37c99bd-e08f-4e58-95e9-b481c39f9155/scratchpad"
d = json.load(open(SC + "/grip.json"))
PX = 0.00983 * 30.02  # px per hand-local cm unit
allc = []
for name, rows in d["clips"].items():
    c = np.array([r["c"] for r in rows]); a = np.array([r["a"] for r in rows])
    m = c.mean(0)
    dev = np.linalg.norm(c - m, axis=1) * PX
    ang = np.degrees(np.arccos(np.clip(a @ (a.mean(0) / np.linalg.norm(a.mean(0))), -1, 1)))
    print(f"{name:10s} n={len(c):3d} mean hollow (x,y,z hand-local)={np.round(m,1)} px  spread max={dev.max():.2f} px  axis angle max={ang.max():.0f} deg")
    allc.append((name, m))
base = np.array(allc[0][1])
print("between clips (px, from idle):", {n: round(float(np.linalg.norm(m - base) * PX), 2) for n, m in allc})
print("knuckle centre", d["knuckle_centre_hand_local"], "px from wrist", round(14.4 * PX, 2))
