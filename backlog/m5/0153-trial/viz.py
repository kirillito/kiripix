"""Trial 0153: images. Per direction: body | each layer | stack in the fixed order | full render | differing pixels in red | stack
by depth. uv run --project <kiripix> python viz.py"""
import sys
import numpy as np
from PIL import Image, ImageDraw
from stacklib import *

OUT = HERE / "sheets"; OUT.mkdir(exist_ok=True)
NAT = {"jacket": ["legs", "jacket", "hair", "pack"], "coat": ["legs", "coat", "hair", "pack"]}


def label(img, text):
    im = Image.fromarray(img); ImageDraw.Draw(im).text((2, 2), text, fill=(255, 255, 255)); return np.array(im)


def sheet(sname, clip, i, order=None, name=None, k=4):
    order = order or NAT[sname]
    rows = []
    for d in EIGHT:
        base = rgba("body", clip, d, i)
        parts = [rgba("layer_" + l, clip, d, i) for l in order]
        ref = rgba("full_" + sname, clip, d, i)
        got = stack(base, parts)
        diff = differ(got, ref)
        z = zmerge([(base, load("body", "depth", clip, d, i))] + [(p, load("layer_" + l, "depth", clip, d, i)) for p, l in zip(parts, order)])
        cells = [over_grey(base)] + [over_grey(p) for p in parts] + [over_grey(got), over_grey(ref), marked(ref, diff), over_grey(z)]
        rows.append(np.concatenate([up(c, k) for c in cells], axis=1))
    img = np.concatenate(rows, axis=0)
    head = np.zeros((24, img.shape[1], 3), dtype=np.uint8) + 40
    names = ["body"] + order + ["stack", "full", "diff (red)", "stack by depth"]
    hi = Image.fromarray(head); dr = ImageDraw.Draw(hi)
    for n, t in enumerate(names):
        dr.text((n * 78 * k + 6, 6), t, fill=(255, 255, 255))
    out = np.concatenate([np.array(hi), img], axis=0)
    Image.fromarray(out).save(OUT / (name or f"layers_{sname}_{clip}{i}_x4.png"), optimize=True)


if __name__ == "__main__":
    sheet("jacket", "walk", 2); sheet("jacket", "attack", 9); sheet("jacket", "idle", 0)
    sheet("coat", "walk", 2); sheet("coat", "attack", 9)
    # the order that fixes the backpack facing south: pack under the outfit
    sheet("jacket", "walk", 2, ["pack", "legs", "jacket", "hair"], "layers_jacket_walk2_packfirst_x4.png")
