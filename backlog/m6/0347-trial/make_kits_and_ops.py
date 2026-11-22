"""0347 trial, routes (b) hand-painted kit and (c) whole-pixel Ops. Run: .venv/Scripts/python backlog/m6/0347-trial/make_kits_and_ops.py
Reads kiripix.ops (read only); writes frames to b_kit/ and c_ops/ beside this file. Prototype only."""
from pathlib import Path
import numpy as np
from PIL import Image
from kiripix.ops import cycle, frames

HERE = Path(__file__).parent
ART = HERE.parent.parent.parent.parent / "urban-mystery-club-art"


def load_palette():
    rows = []
    for line in (ART / "style/palette.gpl").read_text().splitlines():
        p = line.split()
        if len(p) >= 3 and p[0].isdigit():
            rows.append([int(p[0]), int(p[1]), int(p[2])])
    return np.array(rows, dtype=np.uint8)


PAL = load_palette()
NAMED = {}
for line in (ART / "style/palette.gpl").read_text().splitlines():
    p = line.split()
    if len(p) >= 4 and p[0].isdigit():
        NAMED[p[3]] = (int(p[0]), int(p[1]), int(p[2]), 255)

KEY = {"W": "paper-2", "y": "amber-9", "o": "ember-10", "r": "brick-8", "a": "amber-6", "t": "teal-2", "c": "teal-1",
       "b": "sky-4", "d": "sky-3", "s": "stone-4", "m": "stone-3", "p": "paper-1", "v": "violet-1", "h": "amber-2"}


def paint(rows):
    h, w = len(rows), max(len(r) for r in rows)
    img = np.zeros((h, w, 4), np.uint8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in KEY:
                img[y, x] = NAMED[KEY[ch]]
    return img


def place(img, w, h, ax, ay):
    """Put img on a w x h canvas with its centre at (ax, ay)."""
    out = np.zeros((h, w, 4), np.uint8)
    ih, iw = img.shape[:2]
    x0, y0 = ax - iw // 2, ay - ih // 2
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(w, x0 + iw), min(h, y0 + ih)
    out[ys:ye, xs:xe] = img[ys - y0:ye - y0, xs - x0:xe - x0]
    return out


def save(name, folder, fr):
    d = HERE / folder / name
    d.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(fr):
        Image.fromarray(f).save(d / f"{i:03d}.png")
    Image.fromarray(np.concatenate(list(fr), axis=1)).save(d / "strip.png")
    print(folder, name, len(fr), fr[0].shape[1], "x", fr[0].shape[0])


def up(img, k):
    return np.repeat(np.repeat(img, k, 0), k, 1)


ramp_of = cycle.ramps(PAL)
pal_index = {tuple(c): i for i, c in enumerate(PAL.tolist())}


def step(img, n):
    """Move every opaque pixel n steps down (n<0 up) its palette ramp: fade (darker) by palette steps."""
    out = img.copy()
    for y, x in zip(*np.nonzero(img[..., 3])):
        i = pal_index[tuple(int(v) for v in img[y, x, :3])]
        r = ramp_of[i]
        j = max(0, min(len(r) - 1, r.index(i) + n))
        out[y, x, :3] = PAL[r[j]]
    return out


# ---- (b) hand-painted kit ------------------------------------------------------------------------------------------
spark = [
    ["........W.......", "........W.......", ".......yWy......", ".......yWy......", "...yy.yyWyy.yy..", "WWWWWyyWWWyyWWWW",
     "...yy.yyWyy.yy..", ".......yWy......", ".......yWy......", "........W.......", "........W.......", "................"],
    ["................", "....o....o......", ".....y..y..o....", "......yWWy......", "o..yyWWWWWWyy..o", "..yyWWWWWWWWyy..",
     "..yyWWWWWWWWyy..", "......yWWy......", ".....y..y..o....", "....o....o......", "................", "................"],
    ["................", ".......o........", "..o...yyyy...o..", ".....yWWWWy.....", "....yWW..WWy....", "....yW....Wy....",
     "....yWW..WWy....", ".....yWWWWy.....", "..o...yyyy...o..", ".......o........", "................", "................"],
    ["..o.........o...", "......oooo......", "....oo....oo....", "...o........o...", "..o..........o..", "..o..........o..",
     "...o........o...", "....oo....oo....", "......oooo......", "..o.........o...", "................", "................"],
    ["o...........o...", "................", "......o..o......", "...o........o...", "................", "..o..........o..",
     "................", "...o........o...", "......o..o......", "................", "o...........o...", "................"],
]
fr = [place(paint(s), 24, 24, 12, 12) for s in spark]
save("hit_spark", "b_kit", np.array(fr))

# telegraph: corner brackets + inner chevrons that step inward, 32 x 32
def telegraph_frame(n):
    img = np.zeros((32, 32, 4), np.uint8)
    for (cx, sx), (cy, sy) in [((0, 1), (0, 1)), ((31, -1), (0, 1)), ((0, 1), (31, -1)), ((31, -1), (31, -1))]:
        off = [0, 1, 2, 1][n]
        for i in range(7):
            for t in range(2):
                img[cy + sy * (off + t), cx + sx * (off + i)] = NAMED["brick-8" if t else "ember-10"]
                img[cy + sy * (off + i), cx + sx * (off + t)] = NAMED["brick-8" if t else "ember-10"]
    if n in (1, 3):
        for x in range(8, 24, 2):
            for y in range(8 + (x // 2 % 2), 24, 2):
                img[y, x] = NAMED["ember-10"]
    return img
save("telegraph", "b_kit", np.array([telegraph_frame(n) for n in range(4)]))

# ---- (c) Ops from one painted frame -------------------------------------------------------------------------------------
# sound wave: one painted cone (arc bands) scrolled outward inside its own silhouette, then faded by palette steps
H, W = 64, 96
cone = np.zeros((H, W, 4), np.uint8)
region = np.zeros((H, W), bool)
yy, xx = np.mgrid[0:H, 0:W]
dist = np.hypot(xx + 6, yy - 32)
ang = np.degrees(np.arctan2(yy - 32, xx + 6))
region = (np.abs(ang) <= 34) & (xx < W)
band = (dist // 7).astype(int) % 3
for k, name in enumerate(["teal-2", "sky-4", None]):
    if name:
        cone[region & (band == k)] = NAMED[name]
cone[region & (band == 0) & (dist % 7 < 2)] = NAMED["paper-2"]
sc = frames.scroll(cone, cone[..., 3] > 0, dx=3, dy=0, frames=6)
seq = [sc[k] for k in range(6)]
seq += [step(sc[5], -2), step(sc[0], -4)]
save("sound_wave", "c_ops", np.array(seq))

# summon puff: one painted puff, integer scale 1x 2x 3x, fade by palette steps, shimmer at the end
puff = paint(["....sssss....", "..ssppppps s..".replace(" ", ""), ".sppppppppps.", "sppppWWWpppps", "spppWWWWWpppm", "sppppWWWppppm",
              ".spppppppppm.", "..sppppppmm..", "....mmmmm...."])
seq = []
for k, (scale, fade) in enumerate([(1, 0), (2, 0), (2, -1), (3, -1), (3, -2), (3, -3)]):
    img = place(up(step(puff, fade), scale), 48, 48, 24, 34)
    seq.append(img)
sh = frames.shimmer(seq[-1], seq[-1][..., 3] > 0, amplitude=1.0, wavelength=6.0, frames=4)
seq += [step(sh[1], -3), step(sh[2], -4)]
save("summon_puff", "c_ops", np.array(seq))

# buff glow: one painted ellipse ring, shimmer for the loop, pulse by palette steps
ring = np.zeros((14, 40, 4), np.uint8)
yy, xx = np.mgrid[0:14, 0:40]
e = ((xx - 19.5) / 19.5) ** 2 + ((yy - 6.5) / 6.5) ** 2
ring[(e <= 1) & (e > 0.62)] = NAMED["amber-9"]
ring[(e <= 0.62) & (e > 0.5)] = NAMED["amber-6"]
base = place(ring, 48, 64, 24, 54)
sh = frames.shimmer(base, base[..., 3] > 0, amplitude=1.0, wavelength=8.0, frames=8)
seq = []
for k in range(8):
    f = sh[k]
    seq.append(step(f, -1) if k % 4 in (2, 3) else f)
save("buff_glow", "c_ops", np.array(seq))
