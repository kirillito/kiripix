"""Trial 0153: a third way: per-layer outline, but only on pixels the body (the holdout) does not cover, so the body's edge
inside a layer draws no line. Counted against the outline of the full render."""
import json
from kiripix.ops import add_outline
from stacklib import *
NAT = {"jacket": ["legs", "jacket", "hair", "pack"], "coat": ["legs", "coat", "hair", "pack"]}
out = {}
for sname, order in NAT.items():
    diff = inside = 0
    for clip, d, i in frames():
        base = rgba("body", clip, d, i); body_m = base[..., 3] > 0
        ref = add_outline(rgba("full_" + sname, clip, d, i), OUTLINE)
        sil = rgba("full_" + sname, clip, d, i)[..., 3] > 0
        layers = []
        for l in order:
            p = rgba("layer_" + l, clip, d, i); o = add_outline(p, OUTLINE)
            new = (o[..., 3] > 0) & ~(p[..., 3] > 0) & body_m   # outline pixels over the body's own pixels
            o[new] = 0
            layers.append(o)
        got = stack(add_outline(base, OUTLINE), layers)
        diff += int(differ(got, ref).sum())
        inside += int((sil & (got[..., :3] == OUTLINE).all(axis=-1) & ~(rgba("full_" + sname, clip, d, i)[..., :3] == OUTLINE).all(axis=-1)).sum())
    out[sname] = {"differ_vs_ref": diff, "inner_line_px": inside}
print(out); json.dump(out, open(HERE / "outline_variant.json", "w"), indent=1)
