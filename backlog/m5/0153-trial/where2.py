import json
from collections import Counter
import numpy as np
from stacklib import *
order = ["legs", "jacket", "hair", "pack"]
res = json.loads((R / "full_jacket" / "result.json").read_text())
names = {m["index"]: next((l for l in order if m["name"].startswith(l + ".")), "body") for m in res["materials"]}
for label, seq in (("pack first", ["pack", "legs", "jacket", "hair"]), ("natural", order)):
    for dirs in (["s"], ["n"]):
        pair = Counter()
        for clip, d, i in frames():
            if d not in dirs: continue
            base = rgba("body", clip, d, i)
            got = base.copy(); who = np.where(base[..., 3] > 0, "body", "none").astype(object)
            for l in seq:
                p = rgba("layer_" + l, clip, d, i); m = p[..., 3] > 0; got[m] = p[m]; who[m] = l
            ref = rgba("full_jacket", clip, d, i); diff = differ(got, ref)
            mat = load("full_jacket", "material", clip, d, i)
            for t, w in zip(mat[diff], who[diff]): pair[f"{names.get(int(t),'none')} -> {w}"] += 1
        print(label, dirs, dict(pair))
