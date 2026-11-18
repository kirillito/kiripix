"""Trial 0153: the outline per layer and once on the stack, against the outline of the full render; atlas sizes.
uv run --project <kiripix> python outline.py"""
import io, json
import numpy as np
from PIL import Image, ImageDraw
from kiripix.ops import add_outline
from stacklib import *

OUT = HERE / "sheets"
NAT = {"jacket": ["legs", "jacket", "hair", "pack"], "coat": ["legs", "coat", "hair", "pack"]}


def lines_of(sname, clip, d, i):
    order = NAT[sname]
    ref = add_outline(rgba("full_" + sname, clip, d, i), OUTLINE)
    base = rgba("body", clip, d, i)
    parts = [rgba("layer_" + l, clip, d, i) for l in order]
    once = add_outline(stack(base, parts), OUTLINE)
    per = stack(add_outline(base, OUTLINE), [add_outline(p, OUTLINE) for p in parts])
    return ref, once, per


stats = {}
for sname in NAT:
    tot = dict(ref_px=0, ref_outline=0, once_vs_ref=0, per_vs_ref=0, per_extra_inside=0, per_extra_outside=0, per_missing=0)
    per_clip = {}
    for clip, d, i in frames():
        ref, once, per = lines_of(sname, clip, d, i)
        silhouette = rgba("full_" + sname, clip, d, i)[..., 3] > 0
        isline = lambda im: (im[..., 3] > 0) & (im[..., :3] == OUTLINE).all(axis=-1) & ~silhouette_of_fill
        silhouette_of_fill = silhouette
        refline = (ref[..., 3] > 0) & ~silhouette  # the outline outside the silhouette
        dv_once, dv_per = differ(once, ref), differ(per, ref)
        # lines the per-layer way draws inside the figure: pixels of the silhouette whose colour is the outline's and not the full render's
        full = rgba("full_" + sname, clip, d, i)
        inside_line = silhouette & (per[..., :3] == OUTLINE).all(axis=-1) & ~(full[..., :3] == OUTLINE).all(axis=-1)
        outside_extra = (~silhouette) & (per[..., 3] > 0) & ~refline
        missing = refline & ~(per[..., 3] > 0)
        tot["ref_px"] += int(silhouette.sum()); tot["ref_outline"] += int(refline.sum())
        tot["once_vs_ref"] += int(dv_once.sum()); tot["per_vs_ref"] += int(dv_per.sum())
        tot["per_extra_inside"] += int(inside_line.sum()); tot["per_extra_outside"] += int(outside_extra.sum()); tot["per_missing"] += int(missing.sum())
        c = per_clip.setdefault(clip, dict(frames=0, per_vs_ref=0, once_vs_ref=0, inside=0)); c["frames"] += 1; c["per_vs_ref"] += int(dv_per.sum()); c["once_vs_ref"] += int(dv_once.sum()); c["inside"] += int(inside_line.sum())
    stats[sname] = {"total": tot, "by_clip": per_clip, "frames": sum(c["frames"] for c in per_clip.values())}
    print(sname, tot)


def sheet(sname, clip, i, k=4):
    rows = []
    for d in EIGHT:
        ref, once, per = lines_of(sname, clip, d, i)
        silhouette = rgba("full_" + sname, clip, d, i)[..., 3] > 0
        inside = silhouette & (per[..., :3] == OUTLINE).all(axis=-1)
        cells = [over_grey(rgba("full_" + sname, clip, d, i)), over_grey(ref), over_grey(once), over_grey(per), marked(per, differ(per, ref))]
        rows.append(np.concatenate([up(c, k) for c in cells], axis=1))
    img = np.concatenate(rows, axis=0)
    hi = Image.fromarray(np.zeros((24, img.shape[1], 3), dtype=np.uint8) + 40); dr = ImageDraw.Draw(hi)
    for n, t in enumerate(["full, no outline", "full render outlined (reference)", "once on the stack", "per layer", "per layer vs reference (red)"]):
        dr.text((n * 78 * k + 6, 6), t, fill=(255, 255, 255))
    Image.fromarray(np.concatenate([np.array(hi), img], axis=0)).save(OUT / f"outline_{sname}_{clip}{i}_x4.png", optimize=True)


sheet("jacket", "walk", 2); sheet("jacket", "attack", 9); sheet("coat", "walk", 2)

# atlas per layer: one sheet, a row per direction, a column per frame (idle 1, walk 8, attack 19)
atlas = {}
for name in ["body", "hair", "legs", "jacket", "coat", "pack", "full_jacket", "full_coat"]:
    scen = name if name.startswith("full") else ("body" if name == "body" else "layer_" + name)
    rows = []
    opaque = 0; lo = np.array([999, 999]); hi_ = np.array([-1, -1])
    for d in EIGHT:
        row = []
        for clip, n in CLIPS.items():
            for i in range(n):
                im = rgba(scen, clip, d, i)
                if name == "body":
                    pass
                row.append(im)
                m = im[..., 3] > 0
                opaque += int(m.sum())
                if m.any():
                    ys, xs = np.nonzero(m); lo = np.minimum(lo, [xs.min(), ys.min()]); hi_ = np.maximum(hi_, [xs.max(), ys.max()])
        rows.append(np.concatenate(row, axis=1))
    sheet_img = np.concatenate(rows, axis=0)
    buf = io.BytesIO(); Image.fromarray(sheet_img).save(buf, "PNG", optimize=True)
    cells = 8 * sum(CLIPS.values())
    atlas[name] = {"sheet_px": list(sheet_img.shape[1::-1]), "cells": cells, "png_bytes": buf.tell(), "opaque_px": opaque,
                   "opaque_share": round(opaque / (cells * 78 * 78), 4), "union_bbox": [int(lo[0]), int(lo[1]), int(hi_[0]), int(hi_[1])]}
    print(name, atlas[name])
(HERE / "outline_atlas.json").write_text(json.dumps({"outline": stats, "atlas": atlas}, indent=1))
