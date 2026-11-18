"""Trial 0153: where the fixed-order stack differs from the full render (which layer should show, which layer shows), and the
sheets at 4x. uv run --project <kiripix> python where.py"""
import json, sys
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from stacklib import R, CLIPS, STACKS, OUTLINE, load, rgba, stack, differ, over_grey, up, marked, frames, zmerge
from common import *

OUT = HERE / "sheets"
OUT.mkdir(exist_ok=True)
NAT = {"jacket": ["legs", "jacket", "hair", "pack"], "coat": ["legs", "coat", "hair", "pack"]}


def layer_of(material_name, layers):
    for l in layers:
        if material_name.startswith(l + "."):
            return l
    return "body"


pairs = {}
for sname, order in NAT.items():
    res = json.loads((R / ("full_" + sname) / "result.json").read_text())
    names = {m["index"]: layer_of(m["name"], order) for m in res["materials"]}
    names[0] = "none"
    pair = Counter(); per_dir = Counter(); per_layer_dir = Counter()
    for clip, d, i in frames():
        base = rgba("body", clip, d, i)
        parts = {l: rgba("layer_" + l, clip, d, i) for l in order}
        ref = rgba("full_" + sname, clip, d, i)
        mat = load("full_" + sname, "material", clip, d, i)
        got = base.copy()
        who = np.where(base[..., 3] > 0, "body", "none").astype(object)
        for l in order:
            m = parts[l][..., 3] > 0
            got[m] = parts[l][m]; who[m] = l
        diff = differ(got, ref)
        truth = np.vectorize(lambda k: names.get(int(k), "?"))(mat)
        for t, w in zip(truth[diff], who[diff]):
            pair[f"{t} -> {w}"] += 1
    pairs[sname] = dict(pair.most_common())
(HERE / "diff_where.json").write_text(json.dumps(pairs, indent=1))
print(json.dumps(pairs, indent=1))
