"""0307 trial, lever C: how far is a mirrored frame from the one the render made? For ne <- nw, e <- w, se <- sw, every frame of every clip:
the colour of flip(nw) against ne (pixels that differ, of the pixels either has; the silhouette alone), the normal with its x negated
(R -> 255 - R) against the real, and, for a loop, the best phase (the mirrored gait starts on the other foot). Writes mirror.json
and a sheet of the clearest frames: real | mirrored | difference, at 3x."""
import json, sys
import numpy as np
from PIL import Image, ImageDraw
from common import *
from lib import *

OUT = HERE / "mirror.json"


def flipc(a):
    return a[:, ::-1]


def flipn(a):
    b = a[:, ::-1].copy()
    m = b[..., 3] > 0
    b[..., 0][m] = 255 - b[..., 0][m]
    return b


def diff(real, mir):
    ra, ma = real[..., 3] > 0, mir[..., 3] > 0
    union = ra | ma
    sil = int((ra ^ ma).sum())
    both = ra & ma
    colour = int((((real != mir).any(axis=2)) & both).sum()) + sil
    return {"opaque": int(union.sum()), "silhouette_px": sil, "colour_px": colour}


def main():
    res = {}
    for name in sys.argv[1:] or ["mc03_male_clothes01"]:
        asset, cell, _ = load_asset(PROJ / "assets/character" / name)
        per = {}
        for clip, c in asset.items():
            rows = []
            for dst, src in MIRROR.items():
                n = len(c["frames"][dst])
                best_phase = []
                tot = {"opaque": 0, "silhouette_px": 0, "colour_px": 0}
                nor_abs = 0.0
                nor_abs_wrong = 0.0
                npx = 0
                for i in range(n):
                    real_c, real_n = c["frames"][dst][i]
                    mir_c, mir_n = flipc(c["frames"][src][i][0]), flipn(c["frames"][src][i][1])
                    d = diff(real_c, mir_c)
                    for k in tot:
                        tot[k] += d[k]
                    m = (real_n[..., 3] > 0) & (mir_n[..., 3] > 0)
                    nor_abs += np.abs(real_n[..., :3].astype(int) - mir_n[..., :3].astype(int))[m].sum()
                    wrong = c["frames"][src][i][1][:, ::-1]
                    nor_abs_wrong += np.abs(real_n[..., :3].astype(int) - wrong[..., :3].astype(int))[m].sum()
                    npx += int(m.sum()) * 3
                    if c["loop"] and n > 1:
                        best_phase.append(min(range(n), key=lambda p: diff(real_c, flipc(c["frames"][src][(i + p) % n][0]))["colour_px"]))
                rows.append({"dir": dst, "from": src, "frames": n, **tot, "pct_colour_px": round(100 * tot["colour_px"] / max(tot["opaque"], 1), 1),
                             "pct_silhouette_px": round(100 * tot["silhouette_px"] / max(tot["opaque"], 1), 1),
                             "normal_mean_abs": round(nor_abs / max(npx, 1), 2), "normal_mean_abs_if_x_not_negated": round(nor_abs_wrong / max(npx, 1), 2),
                             "best_phase_shift": sorted(set(best_phase)) if best_phase else None})
            per[clip] = rows
        res[name] = per
        sheet(name, asset, cell)
    OUT.write_text(json.dumps(res, indent=1))


def sheet(name, asset, cell, scale=3):
    picks = [("walk", 2), ("attack", 8), ("idle", 0), ("phone", 12)]
    picks = [(c, i) for c, i in picks if c in asset]
    w, h = cell
    img = Image.new("RGB", (len(picks) * 3 * w * scale + 70, 3 * h * scale + 24), (20, 20, 24))
    dr = ImageDraw.Draw(img)
    for r, (dst, src) in enumerate(MIRROR.items()):
        for k, (clip, i) in enumerate(picks):
            real = asset[clip]["frames"][dst][min(i, len(asset[clip]["frames"][dst]) - 1)][0]
            mir = flipc(asset[clip]["frames"][src][min(i, len(asset[clip]["frames"][src]) - 1)][0])
            dd = np.zeros((h, w, 4), np.uint8)
            dd[..., :3] = (np.array([60, 62, 72]) )
            dd[..., 3] = 255
            ra, ma = real[..., 3] > 0, mir[..., 3] > 0
            dd[ra & ma] = (90, 90, 100, 255)
            dd[((real != mir).any(axis=2)) & ra & ma] = (255, 210, 0, 255)  # same silhouette, other colour
            dd[ra & ~ma] = (255, 60, 60, 255)  # only in the render
            dd[~ra & ma] = (60, 140, 255, 255)  # only in the mirror
            for j, im in enumerate([real, mir, dd]):
                t = Image.new("RGBA", (w, h), (58, 62, 72, 255))
                t.alpha_composite(Image.fromarray(im, "RGBA") if im.shape[2] == 4 else im)
                x = 70 + (k * 3 + j) * w * scale
                img.paste(t.convert("RGB").resize((w * scale, h * scale), Image.NEAREST), (x, 24 + r * h * scale))
        dr.text((6, 24 + r * h * scale + h * scale // 2), f"{dst}\nfrom\n{src}", fill=(255, 255, 255))
    for k, (clip, i) in enumerate(picks):
        dr.text((70 + k * 3 * w * scale + 4, 6), f"{clip} #{i}:  render | flip({'src'}) | difference (yellow colour, red only render, blue only mirror)", fill=(255, 255, 255))
    p = HERE / "sheets" / f"mirror_{name}_x3.png"
    p.parent.mkdir(exist_ok=True)
    img.save(p)
    print(p, img.size)


main()
