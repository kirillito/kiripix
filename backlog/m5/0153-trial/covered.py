import json
from stacklib import *
out = {}
for sname, order in (("jacket", ["legs", "jacket", "hair", "pack"]), ("coat", ["legs", "coat", "hair", "pack"])):
    body = covered = 0
    for clip, d, i in frames():
        b = rgba("body", clip, d, i)[..., 3] > 0
        over = np.zeros_like(b)
        for l in order:
            over |= rgba("layer_" + l, clip, d, i)[..., 3] > 0
        body += int(b.sum()); covered += int((b & over).sum())
    out[sname] = {"body_px": body, "covered_by_layers_px": covered, "share": round(covered / body, 3)}
print(out)
json.dump(out, open(HERE / "body_covered.json", "w"), indent=1)
