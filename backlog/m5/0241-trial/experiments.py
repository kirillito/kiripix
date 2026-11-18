"""Ticket 0241 steps 2-7 on Sanjay's set: writes out/results.json and the comparison images.

Run: uv run python backlog/m5/0241-trial/experiments.py     (about 4 minutes; cutouts are cached in work/)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from PIL import ImageDraw  # noqa: E402

from kiripix.ops import set_report, upscale  # noqa: E402
from portrait_set import *  # noqa: E402,F403

HERE = Path(__file__).parent
OUT, WORK = HERE / "out", HERE / "work"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)
NAMES = ["neutral", "happy", "angry", "surprised", "sad", "worried"]
results: dict = {}
t0 = time.time()

# 2. cutout
cuts, info = {}, {}
for k in NAMES:
    cache = WORK / f"cut_{k}.png"
    src = next((HERE / "input").glob(f"{k}.*"))
    c, i = cutout(load(src))
    cuts[k], info[k] = c, i
    Image.fromarray(c).save(cache)
results["cutout"] = info

# 3. register, both ways
al = {"whole": register_set(cuts, "neutral", None), "outside": register_set(cuts, "neutral", FACE_BOX)}
results["register"] = {w: {k: {"scale_x": a.scale_x, "scale_y": a.scale_y, "shift_x": a.shift_x, "shift_y": a.shift_y,
                              "residual": a.residual, "tiles": a.tiles,
                              "worst_move_px": a.displacement(896, 1200), "applied": not a.negligible(896, 1200)}
                          for k, a in d.items()} for w, d in al.items()}


def aligned(d):
    return {"neutral": cuts["neutral"], **{k: warp_nearest(cuts[k], a) for k, a in d.items()}}


# 4. fit: one Grid for the set, from the neutral
ys, xs = np.nonzero(cuts["neutral"][..., 3])
grid = fit_grid((1200, 896), cx=int((xs.min() + xs.max()) // 2))
face = face_target(FACE_BOX, grid)
results["grid"] = grid.to_json()
results["figure_box_source"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
fit = {"none": {k: downscale(v, grid) for k, v in cuts.items()},
       "whole": {k: downscale(v, grid) for k, v in aligned(al["whole"]).items()},
       "outside": {k: downscale(v, grid) for k, v in aligned(al["outside"]).items()}}
results["face_px"] = [int(face.sum()), int(face.size)]
results["opaque_outside_face"] = int(((fit["outside"]["neutral"][..., 3] == 255) & ~face).sum())


def flat(a, bg=(90, 90, 100)):
    out = np.zeros(a.shape, np.uint8)
    out[...] = (*bg, 255)
    m = a[..., 3] == 255
    out[m] = a[m]
    return out


def dE(a, b):
    return np.sqrt(((srgb_to_oklab(a[..., :3]) - srgb_to_oklab(b[..., :3])) ** 2).sum(-1))


def shimmer_counts(imgs):
    ref = imgs["neutral"]
    ex, vis = {}, {}
    for k in NAMES[1:]:
        both = (ref[..., 3] == 255) & (imgs[k][..., 3] == 255) & ~face
        ex[k] = int(((imgs[k] != ref).any(-1) & ~face).sum())
        vis[k] = int((dE(ref, imgs[k])[both] > 0.03).sum())
    return {"exact": ex, "exact_total": sum(ex.values()), "dE_over_0.03": vis, "dE_total": sum(vis.values())}


# 5, 6, 7. colours, outline, shimmer
col, finals = {}, {}
configs = [(n, d, alone) for n in (16, 32, 64) for d in (0, 4) for alone in (False, True)]
configs += [(32, 2, False), (32, 8, False)]
for reg in ("none", "outside"):
    base = [fit[reg][k] for k in NAMES]
    for n, d, alone in configs:
        if reg == "none" and (d != 0 or alone):
            continue
        m, _pal = mapped(base, n, d, alone=alone)
        rep = set_report(base, m)
        fin = {k: outline(i) for k, i in zip(NAMES, m)}
        key = f"reg={reg} n={n} dither={d} {'alone' if alone else 'joint'}"
        col[key] = {"mean_error": [round(r.mean_error, 4) for r in rep], "p95_error": [round(r.p95_error, 4) for r in rep],
                    "mean_of_means": round(float(np.mean([r.mean_error for r in rep])), 4),
                    "mean_of_p95": round(float(np.mean([r.p95_error for r in rep])), 4),
                    "colours_used": [len(r.colours) for r in rep],
                    "colours_in_set_of_images": len(np.unique(np.concatenate(
                        [f[..., :3][f[..., 3] == 255] for f in fin.values()]), axis=0)),
                    "shimmer": shimmer_counts(fin)}
        finals[key] = fin
        print(key, col[key]["mean_of_means"], col[key]["shimmer"]["exact_total"], col[key]["shimmer"]["dE_total"],
              round(time.time() - t0))
results["colours"] = col

# raw (unmapped) shimmer, and the locked result
results["shimmer_unmapped_dE_over_0.03"] = {w: shimmer_counts(fit[w])["dE_over_0.03"] for w in fit}
CHOSEN = "reg=outside n=32 dither=0 joint"
locked = lock_outside_face(finals[CHOSEN], "neutral", face)
results["locked_shimmer"] = shimmer_counts(locked)


# images
def labelled(tiles, cols, scale, rows_h=None, pad=18):
    h = rows_h or tiles[0][1].shape[0]
    w = tiles[0][1].shape[1]
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w * scale, rows * (h * scale + pad)), (30, 30, 30))
    for i, (lab, a) in enumerate(tiles):
        x, y = (i % cols) * w * scale, (i // cols) * (h * scale + pad)
        sheet.paste(Image.fromarray(upscale(flat(a)[:h], scale)[..., :3]), (x, y + pad))
        ImageDraw.Draw(sheet).text((x + 4, y + 3), lab, fill=(255, 255, 255))
    return sheet


tiles = [("unmapped (fit only)", fit["outside"]["neutral"])]
for n in (16, 32, 64):
    for d in (0, 4):
        tiles.append((f"n={n} dither={d} joint", finals[f"reg=outside n={n} dither={d} joint"]["neutral"]))
tiles += [("n=32 each alone", finals["reg=outside n=32 dither=0 alone"]["neutral"]),
          ("n=64 each alone", finals["reg=outside n=64 dither=0 alone"]["neutral"])]
labelled(tiles, 4, 4, rows_h=150).save(OUT / "n_comparison_upper_body.png")

# the five emotions at the chosen settings, with and without lock
fin = finals[CHOSEN]
labelled([(k, fin[k]) for k in NAMES], 6, 3).save(OUT / "set_n32_joint.png")
labelled([(k + " (locked)", locked[k]) for k in NAMES], 6, 3).save(OUT / "set_n32_locked.png")

# where the shimmer is: pixels outside the face box differing exactly (yellow), by dE>0.03 (red), the box (blue)
tiles = []
ref = fin["neutral"]
for k in NAMES[1:]:
    m = np.zeros(ref.shape, np.uint8)
    m[..., 3] = 255
    m[ref[..., 3] == 255] = (70, 70, 70, 255)
    m[(fin[k] != ref).any(-1) & ~face] = (255, 255, 0, 255)
    m[(dE(ref, fin[k]) > 0.03) & ~face & (ref[..., 3] == 255) & (fin[k][..., 3] == 255)] = (255, 0, 0, 255)
    edge = face ^ (face & np.roll(face, 1, 0) & np.roll(face, -1, 0) & np.roll(face, 1, 1) & np.roll(face, -1, 1))
    m[edge] = (0, 160, 255, 255)
    tiles.append((f"{k}: yellow exact, red dE>0.03", m))
labelled(tiles, 5, 3).save(OUT / "shimmer_map.png")

# outline placement: outside (grows the figure 1 px) against edge (repaints the border)
base = [fit["outside"][k] for k in NAMES]
m, _ = mapped(base, 32, 0)
tiles = [("outside", outline(m[0], "outside")), ("edge", outline(m[0], "edge")), ("none", m[0])]
labelled(tiles, 3, 5, rows_h=224).save(OUT / "outline_placement.png")

# the other size: 120 x 168 (5:7 again, 3/4 of the canvas)
g2 = fit_grid((1200, 896), canvas=(120, 168), cx=int((xs.min() + xs.max()) // 2))
fit2 = [downscale(warp_nearest(cuts[k], al["outside"][k]) if k != "neutral" else cuts[k], g2) for k in NAMES]
m2, _ = mapped(fit2, 24, 0)
labelled([(f"120x168 n=24 {k}", outline(i)) for k, i in zip(NAMES, m2)], 6, 3).save(OUT / "other_size_120x168.png")

(OUT / "results.json").write_text(json.dumps(results, indent=1, default=float))
print("done", round(time.time() - t0), "s")
