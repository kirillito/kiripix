"""0332 trial: style measures on matched and mismatched Assets. Prototype; reads the art Project, writes only here.

Run: uv run python backlog/m6/0332-trial/measure.py   (writes results.json and images/ beside it)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

ART = Path(r"C:\Homespace\urban-mystery-club-art")
HERE = Path(__file__).parent
OUTLINE_INDEX = 195

# ---------------------------------------------------------------- colour
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def oklab(rgb: np.ndarray) -> np.ndarray:
    c = rgb.astype(np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    lms = np.cbrt(lin @ _M1.T)
    return lms @ _M2.T


def from_oklab(lab: np.ndarray) -> np.ndarray:
    lms = (lab @ np.linalg.inv(_M2).T) ** 3
    lin = np.clip(lms @ np.linalg.inv(_M1).T, 0, 1)
    c = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * lin ** (1 / 2.4) - 0.055)
    return np.clip(np.rint(c * 255), 0, 255).astype(np.uint8)


def load_palette() -> np.ndarray:
    rows = []
    for line in (ART / "style/palette.gpl").read_text().splitlines()[3:]:
        p = line.split()
        if len(p) >= 3:
            rows.append([int(p[0]), int(p[1]), int(p[2])])
    return np.array(rows, dtype=np.uint8)


PAL = load_palette()
PACK = {(int(r) << 16) | (int(g) << 8) | int(b): i for i, (r, g, b) in reversed(list(enumerate(PAL.tolist())))}
OUTLINE_RGB = np.array(PAL[OUTLINE_INDEX], dtype=np.uint8)


def packed(rgb: np.ndarray) -> np.ndarray:
    r = rgb.astype(np.int64)
    return (r[..., 0] << 16) | (r[..., 1] << 8) | r[..., 2]


# ---------------------------------------------------------------- loading
def box_slice(a: np.ndarray):
    ys, xs = np.nonzero(a[..., 3] > 0)
    return slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1)


def read(p: Path) -> np.ndarray:
    return np.array(Image.open(p).convert("RGBA"))


def frame(asset: str, clip="idle", direction="s"):
    d = ART / "assets" / asset / "out/export"
    j = json.loads((d / "character.json").read_text())
    c = next((c for c in j["clips"] if c["name"] == clip), j["clips"][0])
    f = c["directions"][direction][0]["rect"]
    sl = (slice(f["y"], f["y"] + f["height"]), slice(f["x"], f["x"] + f["width"]))
    col, nor = read(d / "color.png")[sl], read(d / "normal.png")[sl]
    b = box_slice(col)
    return col[b], nor[b]


# ---------------------------------------------------------------- measures
def opaque(a):
    return a[..., 3] > 0


def is_outline(a):
    return np.all(a[..., :3] == OUTLINE_RGB, axis=-1) & opaque(a)


def edge_mask(alpha: np.ndarray) -> np.ndarray:
    o = np.pad(alpha, 1)
    n = o[:-2, 1:-1] & o[2:, 1:-1] & o[1:-1, :-2] & o[1:-1, 2:]
    return alpha & ~n


def m_palette(a, ref_hist):
    o = opaque(a)
    pk = packed(a[..., :3])[o]
    uniq, cnt = np.unique(pk, return_counts=True)
    idx = np.array([PACK.get(int(u), -1) for u in uniq])
    on = idx >= 0
    hist = np.zeros(len(PAL))
    np.add.at(hist, idx[on], cnt[on])
    n = cnt.sum()
    out = {"used_share": float(len(set(idx[on].tolist())) / len(PAL)), "colours": int(len(uniq)),
           "off_palette_px": float(cnt[~on].sum() / n)}
    h = hist / max(hist.sum(), 1)
    if ref_hist is not None:
        out["tv_vs_refs"] = float(0.5 * np.abs(h - ref_hist).sum())
    return out, h


def m_range(a):
    lab = oklab(a[..., :3][opaque(a)])
    L = lab[:, 0]
    C = np.hypot(lab[:, 1], lab[:, 2])
    l5, l95 = np.percentile(L, [5, 95])
    c5, c95 = np.percentile(C, [5, 95])
    return {"L5": l5, "L95": l95, "Lspan": l95 - l5, "C5": c5, "C95": c95, "Cspan": c95 - c5}


def m_outline(a, alpha=None):
    alpha = opaque(a) if alpha is None else alpha
    e = edge_mask(alpha)
    o = is_outline(a)
    edge_px = int(e.sum())
    return {"outline_px": int(o.sum()), "edge_px": edge_px, "density": float(o.sum() / max(edge_px, 1)),
            "edge_covered": float((o & e).sum() / max(edge_px, 1))}


def runs(pk, o):
    L, B = [], []
    n = len(pk)
    i = 0
    while i < n:
        if not o[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and o[j + 1] and pk[j + 1] == pk[i]:
            j += 1
        L.append(j - i + 1)
        if j + 1 < n and o[j + 1]:
            B.append(j + 1)
        i = j + 1
    return L, B


def m_scale(a):
    pk = packed(a[..., :3])
    o = opaque(a)
    allr, bnd = [], []
    for y in range(a.shape[0]):
        r, b = runs(pk[y], o[y]); allr += r; bnd += b
    for x in range(a.shape[1]):
        r, b = runs(pk[:, x], o[:, x]); allr += r; bnd += b
    allr = np.array(allr)
    bnd = np.array(bnd)
    return {"run_median": float(np.median(allr)), "run_gcd": int(np.gcd.reduce(allr)),
            "run1_share": float((allr == 1).mean()),
            "even_boundary_share": float((bnd % 2 == 0).mean()) if len(bnd) else 0.0}


def m_light_gradient(layers):
    """Pooled within-layer correlation of lightness with x and y, outline pixels left out.
    lit_left > 0: lighter on the left; lit_top > 0: lighter at the top. angle: 0 = lit from the left, 90 = from the top."""
    sxl = sx = syl = sy = sll = 0.0
    for a in layers:
        o = opaque(a) & ~is_outline(a)
        if o.sum() < 20:
            continue
        ys, xs = np.nonzero(o)
        L = oklab(a[..., :3][o])[:, 0]
        L = L - L.mean(); x = xs - xs.mean(); y = ys - ys.mean()
        sxl += (x * L).sum(); sx += (x * x).sum(); syl += (y * L).sum(); sy += (y * y).sum(); sll += (L * L).sum()
    cx = sxl / np.sqrt(sx * sll)
    cy = syl / np.sqrt(sy * sll)
    return {"lit_left": float(-cx), "lit_top": float(-cy), "angle_deg": float(np.degrees(np.arctan2(-cy, -cx))),
            "strength": float(np.hypot(cx, cy))}


def m_light_normals(color, normal):
    o = opaque(color) & opaque(normal)
    n = normal[..., :3][o].astype(np.float64) / 255 * 2 - 1
    keep = ~is_outline(color)[o]
    L = oklab(color[..., :3][o])[:, 0]
    n, L = n[keep], L[keep]
    A = np.c_[np.ones(len(n)), n[:, 0], n[:, 1], n[:, 2]]
    coef, *_ = np.linalg.lstsq(A, L, rcond=None)
    return {"nx_coef": float(coef[1]), "ny_coef": float(coef[2]), "nz_coef": float(coef[3]),
            "angle_deg": float(np.degrees(np.arctan2(coef[2], -coef[1])))}


def m_light_normals_fe(color, normal):
    """As m_light_normals, with a fixed effect per hue family (12 hue bins plus neutral), so albedo does not read as light."""
    o = opaque(color) & opaque(normal)
    keep = ~is_outline(color)[o]
    n = (normal[..., :3][o].astype(np.float64) / 255 * 2 - 1)[keep]
    lab = oklab(color[..., :3][o])[keep]
    L = lab[:, 0]
    C = np.hypot(lab[:, 1], lab[:, 2])
    h = ((np.degrees(np.arctan2(lab[:, 2], lab[:, 1])) % 360) // 30).astype(int)
    fam = np.where(C < 0.03, 12, h)
    fams = np.unique(fam)
    A = np.c_[n[:, 0], n[:, 1], n[:, 2], (fam[:, None] == fams[None, :]).astype(float)]
    coef, *_ = np.linalg.lstsq(A, L, rcond=None)
    return {"nx_coef": float(coef[0]), "ny_coef": float(coef[1]), "angle_deg": float(np.degrees(np.arctan2(coef[1], -coef[0])))}


def m_light_thirds(layers):
    """Per Layer: mean lightness of the left third of its opaque columns minus the right third's, and top minus bottom, pooled by pixel count."""
    dx = dy = w = 0.0
    for a in layers:
        o = opaque(a) & ~is_outline(a)
        if o.sum() < 60:
            continue
        ys, xs = np.nonzero(o)
        L = oklab(a[..., :3][o])[:, 0]
        x0, x1 = np.percentile(xs, [33, 67]); y0, y1 = np.percentile(ys, [33, 67])
        if (xs <= x0).any() and (xs >= x1).any() and (ys <= y0).any() and (ys >= y1).any():
            dx += o.sum() * (L[xs <= x0].mean() - L[xs >= x1].mean())
            dy += o.sum() * (L[ys <= y0].mean() - L[ys >= y1].mean())
            w += o.sum()
    return {"left_minus_right": float(dx / w), "top_minus_bottom": float(dy / w)}


def measure_all(a, layers=None, normal=None, ref_hist=None):
    t = {}

    def timed(k, f):
        s = time.perf_counter(); r = f(); t[k] = round(time.perf_counter() - s, 4); return r

    out = {}
    out["palette"], hist = timed("palette", lambda: m_palette(a, ref_hist))
    out["range"] = timed("range", lambda: m_range(a))
    out["outline"] = timed("outline", lambda: m_outline(a))
    out["scale"] = timed("scale", lambda: m_scale(a))
    out["light_grad"] = timed("light_grad", lambda: m_light_gradient(layers or [a]))
    if normal is not None:
        out["light_norm"] = timed("light_norm", lambda: m_light_normals(a, normal))
        out["light_norm_fe"] = timed("light_norm_fe", lambda: m_light_normals_fe(a, normal))
    out["light_thirds"] = timed("light_thirds", lambda: m_light_thirds(layers or [a]))
    out["time_s"] = t
    return out, hist


# ---------------------------------------------------------------- mismatches
def upscale2(a):
    return np.repeat(np.repeat(a, 2, 0), 2, 1)


def outline_off(a):
    a = a.copy()
    isout = is_outline(a)
    alpha = opaque(a)
    pad = np.pad(alpha, 1)
    touch_clear = ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    kill = isout & touch_clear
    inner = isout & ~touch_clear
    pk = packed(a[..., :3])
    H, W = isout.shape
    for y, x in zip(*np.nonzero(inner)):
        cnt = {}
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and alpha[yy, xx] and not isout[yy, xx]:
                    cnt[pk[yy, xx]] = cnt.get(pk[yy, xx], 0) + 1
        if cnt:
            best = min(cnt, key=lambda k: (-cnt[k], k))  # most common, ties to the lowest packed colour
            a[y, x, :3] = [(best >> 16) & 255, (best >> 8) & 255, best & 255]
    a[kill] = 0
    return a[box_slice(a)]


def saturate(a, k=1.8):
    a = a.copy()
    o = opaque(a)
    lab = oklab(a[..., :3][o])
    lab[:, 1:] *= k
    a[..., :3][o] = from_oklab(lab)
    return a


def mirror_normal(n):
    n = n[:, ::-1].copy()
    o = n[..., 3] > 0
    n[..., 0][o] = 255 - n[..., 0][o]
    return n


def mirror(a):
    return a[:, ::-1].copy()


# ---------------------------------------------------------------- main
def main():
    figs = {}
    for name, asset in [("body_male", "character/mc03_male"), ("body_female", "character/mc03_female"),
                        ("wearable_male_clothes01", "character/mc03_male_clothes01"),
                        ("sprite_raccoon", "sprite/raccoon")]:
        figs[name] = frame(asset)
    rooms = {}
    lane = ART / "assets/room/ch01_002_laneway/out/export"
    lane_layers = [read(p) for p in sorted(lane.glob("layer.*.png"))]
    comp = np.zeros_like(lane_layers[0])
    for l in lane_layers:  # no full Plate is exported (looks only): the foreground Layers composited, name order
        comp[opaque(l)] = l[opaque(l)]
    rooms["room_laneway"] = (comp, lane_layers)
    for r in ("r01", "r02", "r03"):
        d = ART / f"assets/room/ch01_dungeon_{r}/out/export"
        rooms[f"room_dungeon_{r}"] = (read(d / "plate.png"), [read(p) for p in sorted(d.glob("layer.*.png"))])
    props = {}
    for r in ("r02", "r03"):
        a = read(ART / f"assets/room/ch01_dungeon_{r}/out/export/layer.bin.png")
        props[f"prop_bin_{r}"] = a[box_slice(a)]

    raw = {}
    for k, (c, n) in figs.items():
        raw[k] = ("figure", c, None, n)
    for k, (plate, layers) in rooms.items():
        raw[k] = ("room", plate, layers, None)
    for k, p in props.items():
        raw[k] = ("prop", p, None, None)

    hists = {k: m_palette(a, None)[1] for k, (g, a, l, n) in raw.items()}
    ref_all = np.mean(list(hists.values()), axis=0)
    results = {}
    for k, (g, a, layers, n) in raw.items():
        r, _ = measure_all(a, layers, n, ref_all)
        r.update(group=g, matched=True, size=list(a.shape[:2]))
        results[k] = r

    rc, rn = figs["sprite_raccoon"]
    bc, bn = figs["body_male"]
    mm = {
        "mm_sprite_2x": ("figure", upscale2(rc), None, upscale2(rn)),
        "mm_body_no_outline": ("figure", outline_off(bc), None, None),
        "mm_sprite_saturated": ("figure", saturate(rc), None, rn),
        "mm_sprite_vivid": ("figure", saturate(rc, 4.0), None, rn),
        "mm_sprite_mirrored": ("figure", mirror(rc), None, mirror_normal(rn)),
        "mm_body_mirrored": ("figure", mirror(bc), None, mirror_normal(bn)),
    }
    plate, layers = rooms["room_dungeon_r02"]
    mm["mm_room_mirrored_r02"] = ("room", mirror(plate), [mirror(x) for x in layers], None)
    plate, layers = rooms["room_laneway"]
    mm["mm_room_mirrored_laneway"] = ("room", mirror(plate), [mirror(x) for x in layers], None)
    for k, (g, a, layers, n) in mm.items():
        r, _ = measure_all(a, layers, n, ref_all)
        r.update(group=g, matched=False, size=list(a.shape[:2]))
        results[k] = r
    (HERE / "results.json").write_text(json.dumps(results, indent=1, default=float))
    d = HERE / "images"
    d.mkdir(exist_ok=True)
    for k, (g, a, layers, n) in {**raw, **mm}.items():
        Image.fromarray(a).save(d / f"{k}.png")
    return results


if __name__ == "__main__":
    main()
