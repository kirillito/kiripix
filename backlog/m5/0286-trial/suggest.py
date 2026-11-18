"""Trial 0286 prototype: suggest a room's foreground Layers from `solid` and the painting.

Methods (each returns a list of {name, mask, box, why}):
  flood : colour region grown up from the foot of each solid component (kiripix.ops.masks.flood_region)
  click : SAM 2 positive click on the component
  box   : SAM 2 box over the component extended upward
  auto  : tall thin objects from SAM 2 point-grid automatic masks, with a foot in `solid`
Imports kiripix's Ops and Runner; changes neither.
"""
from __future__ import annotations

import numpy as np

from kiripix.ops.layers import connected_regions
from kiripix.ops.masks import flood_region

# parameters (the trial's, not Kiripix's)
MIN_COMPONENT = 20        # px of solid
MAX_ROOM_FRACTION = 0.10  # a component whose box is bigger than this share of the room is walls, not an object
RISE = 6                  # the painted object must reach this far above the foot to count
FLOOD_TOL = 0.04          # OKLab
BOX_UP = 2.0              # extra box height above the foot, in foot heights, plus 16 px


def components(solid: np.ndarray):
    h, w = solid.shape
    out = []
    for region in connected_regions(solid, eight=True):
        if len(region) < MIN_COMPONENT:
            continue
        y0, x0 = region.min(axis=0)
        y1, x1 = region.max(axis=0) + 1
        if x0 == 0 or y0 == 0 or x1 == w or y1 == h:
            continue
        if (y1 - y0) * (x1 - x0) > MAX_ROOM_FRACTION * h * w:
            continue
        m = np.zeros_like(solid)
        m[region[:, 0], region[:, 1]] = True
        out.append({"mask": m, "box": (int(x0), int(y0), int(x1), int(y1)), "area": len(region), "region": region})
    return out


def _largest_touching(mask: np.ndarray, anchor: np.ndarray) -> np.ndarray:
    """The 8-connected pieces of `mask` that touch `anchor`."""
    keep = np.zeros_like(mask)
    for region in connected_regions(mask | anchor, eight=True):
        if anchor[region[:, 0], region[:, 1]].any():
            keep[region[:, 0], region[:, 1]] = True
    return keep & (mask | anchor)


def _finish(comp, mask, name, why):
    mask = _largest_touching(mask, comp["mask"]) | comp["mask"]
    ys, xs = np.nonzero(mask)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    if comp["box"][1] - y0 < RISE:
        return None  # nothing painted above the foot: not a foreground object
    return {"name": name, "mask": mask, "box": (x0, y0, x1, y1), "why": why}


def flood_method(rgba, solid):
    h, w = solid.shape
    out = []
    for i, c in enumerate(components(solid)):
        x0, y0, x1, y1 = c["box"]
        top = c["region"][c["region"][:, 0] == y0]
        sx = int(np.median(top[:, 1]))
        # seed just above the foot's top row is unknown; seed on the foot's top pixel and grow
        grown = flood_region(rgba, sx, y0, FLOOD_TOL)
        # window: the foot's width +-6, up to 4 foot heights + 24 px
        win = np.zeros_like(solid)
        win[max(0, y0 - 4 * (y1 - y0) - 24): y1, max(0, x0 - 6): min(w, x1 + 6)] = True
        grown &= win
        r = _finish(c, grown, f"flood{i}", f"foot {c['box']}")
        if r:
            out.append(r)
    return out


def sam_methods(runner, rgba, solid, check=lambda: None):
    h, w = solid.shape
    emb = runner.embed(rgba, check)
    click, box = [], []
    for i, c in enumerate(components(solid)):
        x0, y0, x1, y1 = c["box"]
        cy, cx = c["region"].mean(axis=0)
        d = ((c["region"] - [cy, cx]) ** 2).sum(axis=1)
        py, px = c["region"][int(np.argmin(d))]
        m = runner.decode(emb, (h, w), {"points": [[int(px), int(py), 1]], "max_size": 99999}, check)
        r = _finish(c, m, f"click{i}", f"foot {c['box']}")
        if r:
            click.append(r)
        up = int(BOX_UP * (y1 - y0)) + 16
        bx = [max(0, x0 - 2), max(0, y0 - up), min(w, x1 + 2), y1]
        m = runner.decode(emb, (h, w), {"box": bx, "max_size": 99999}, check)
        r = _finish(c, m, f"box{i}", f"foot {c['box']} prompt {bx}")
        if r:
            box.append(r)
    return click, box


def _iou(a, b):
    u = (a | b).sum()
    return (a & b).sum() / u if u else 0.0


def auto_method(runner, rgba, solid, check=lambda: None, step=20):
    """SAM 2 automatic masks (a point grid), kept if tall and thin with a foot in `solid` and a top above it."""
    h, w = solid.shape
    emb = runner.embed(rgba, check)
    seen: list[np.ndarray] = []
    out = []
    for py in range(step // 2, h, step):
        for px in range(step // 2, w, step):
            if solid[py, px]:
                continue
            m = runner.decode(emb, (h, w), {"points": [[px, py, 1]], "max_size": 99999}, check)
            ys, xs = np.nonzero(m)
            if len(ys) < 40:
                continue
            bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            if bh < 36 or bw > 24 or bh < 3 * bw or len(ys) < 0.35 * bw * bh:
                continue
            # the foot: solid within 4 px below the mask's lowest rows, near its bottom columns
            yb = ys.max()
            foot = solid[max(0, yb - 3): min(h, yb + 5), max(0, xs.min() - 3): min(w, xs.max() + 4)]
            if not foot.any() or (m & solid).sum() > 0.5 * len(ys):
                continue
            if any(_iou(m, s) > 0.7 for s in seen):
                continue
            seen.append(m)
            out.append({"name": f"auto{len(out)}", "mask": m, "box": (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(yb) + 1),
                        "why": f"tall thin from point ({px},{py})"})
    return out


def standing_method(runner, rgba, solid, pit, check=lambda: None, step=16):
    """SAM 2 point-grid masks anywhere (also inside `solid`): keep a compact mask that stands on walkable floor
    (its lowest pixels in most columns have floor just below), lies mostly in `solid`, and isn't a wall or a decal.
    This is for rooms where `solid` is one blob joined to the walls, so no component is a foot."""
    h, w = solid.shape
    floor = ~solid & ~pit
    emb = runner.embed(rgba, check)
    seen: list[np.ndarray] = []
    out = []
    for py in range(step // 2, h, step):
        for px in range(step // 2, w, step):
            m = runner.decode(emb, (h, w), {"points": [[px, py, 1]], "max_size": 99999}, check)
            n = int(m.sum())
            if n < 150 or n > 0.12 * h * w:
                continue
            ys, xs = np.nonzero(m)
            x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
            if x0 == 0 or y0 == 0 or x1 == w or y1 == h:
                continue
            if (m & solid).sum() < 0.4 * n or n < 0.25 * (x1 - x0) * (y1 - y0):
                continue
            cols = np.unique(xs)
            low = np.array([ys[xs == c].max() for c in cols])
            ok = [floor[min(h - 1, yy + 1): min(h, yy + 4), c].any() for c, yy in zip(cols, low)]
            if np.mean(ok) < 0.4:
                continue
            if any(_iou(m, s) > 0.7 for s in seen):
                continue
            seen.append(m)
            out.append({"name": f"stand{len(out)}", "mask": m, "box": (x0, y0, x1, y1), "why": f"mask from point ({px},{py})"})
    return out
