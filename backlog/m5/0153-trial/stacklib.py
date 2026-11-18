"""Trial 0153 helpers: loading frames, stacking, comparing."""
import itertools, json, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "C:/Homespace/kiripix")
from kiripix.ops import add_outline
from common import *

R = SC / "render"
CLIPS = {"idle": 1, "walk": 8, "attack": 19}
OUTLINE = (53, 38, 37)  # palette index 195 of the art repo's style/palette.gpl
STACKS = {"jacket": ["legs", "jacket", "hair", "pack"], "coat": ["legs", "coat", "hair", "pack"]}


def load(scen, kind, clip, d, i):
    img = np.array(Image.open(R / scen / kind / clip / d / f"{i:03d}.png"))
    return img


def frames():
    for clip, n in CLIPS.items():
        for d in EIGHT:
            for i in range(n):
                yield clip, d, i


def rgba(scen, clip, d, i):
    return load(scen, "color", clip, d, i)


def stack(base, layers):
    out = base.copy()
    for layer in layers:
        m = layer[..., 3] > 0
        out[m] = layer[m]
    return out


def zmerge(parts):  # parts: [(rgba, depth)] in order; nearest wins, ties go to the later one
    out = np.zeros_like(parts[0][0]); best = np.full(parts[0][1].shape, 70000, dtype=np.int64)
    for img, depth in parts:
        m = (img[..., 3] > 0) & (depth.astype(np.int64) <= best)
        out[m] = img[m]; best[m] = depth[m]
    return out


def differ(a, b):
    ma, mb = a[..., 3] > 0, b[..., 3] > 0
    return (ma != mb) | (ma & mb & (a[..., :3] != b[..., :3]).any(axis=-1))


def over_grey(img, bg=(120, 120, 128)):
    out = np.zeros(img.shape[:2] + (3,), dtype=np.uint8); out[:] = bg
    m = img[..., 3] > 0
    out[m] = img[m][..., :3]
    return out


def up(a, k=4):
    return np.kron(a, np.ones((k, k, 1), dtype=np.uint8)) if a.ndim == 3 else np.kron(a, np.ones((k, k), dtype=np.uint8))


def marked(img, diff):  # the frame on grey, the differing pixels red
    out = over_grey(img); out[diff] = (230, 30, 30)
    return out


