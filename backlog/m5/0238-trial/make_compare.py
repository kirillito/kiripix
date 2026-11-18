"""Trial 0238 follow-up: comparison sheets (a) against (c), the cell rules, the colour options. Reuses the renders and the scratch
Project's finished frames; nothing is rendered. Usage: make_compare.py [ac|cells|layer|colours|all]"""
import json, math, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
proj = SC / "proj/assets/character"
R = SC / "render"
OUT = HERE / "sheets"
BG = (58, 62, 72, 255)
OL = (53, 38, 37, 255)  # the outline colour (palette 195)
THING = [13, 14, 15]


def fin(asset, clip, d, i):
    return Image.open(proj / asset / "work/finish/color" / clip / d / f"{i:03d}.png").convert("RGBA")


def place(im, side, offset):
    big = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    big.paste(im, offset)
    return big


def on_bg(im, scale, bg=BG):
    t = Image.new("RGBA", im.size, bg)
    t.alpha_composite(im)
    return t.resize((im.width * scale, im.height * scale), Image.NEAREST)


def label(img, text, xy, fill=(255, 255, 255, 255)):
    ImageDraw.Draw(img).text(xy, text, fill=fill)


def stacked(clip, d, i):
    """(c): the body's finished frame (its own inner lines and outline) with the layer's pixels pasted over it, and the outline once
    on the stack's silhouette. The layer pixels are the thing's own, taken from the finished frame of (a) where the material pass says
    thing. Returns (a, c, thing_only) as 86 cell RGBA images."""
    a = fin("held_a1rows", clip, d, i)
    body = place(fin("held_base", clip, d, i), 86, (4, 8))
    mat = np.array(Image.open(proj / "held_a1rows/work/render/material" / clip / d / f"{i:03d}.png"))
    thing = np.isin(mat, THING)
    arr_a, arr_b = np.array(a), np.array(body)
    # the layer holds only the thing's visible pixels (the body is a holdout)
    layer = np.zeros_like(arr_a); layer[thing] = arr_a[thing]
    c = arr_b.copy()
    c[thing] = arr_a[thing]
    # the outline once on the stack: a transparent pixel beside a thing pixel gets the outline colour (the body's own is there already)
    near = np.zeros_like(thing)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        near |= np.roll(np.roll(thing, dy, 0), dx, 1)
    c[near & (c[..., 3] == 0)] = OL
    return a, Image.fromarray(c), Image.fromarray(layer)


def ac_sheet(name, clip, picks, title):
    """rows = (direction, frame); columns: (a) | (c) stacked | where they differ | the layer alone"""
    S, side = 4, 86
    w = side * S
    img = Image.new("RGBA", (4 * w + 3 * 12, len(picks) * w + 40), (20, 20, 24, 255))
    label(img, title, (6, 4))
    for c, t in enumerate(["(a) attached, one finish pass", "(c) body frame + layer pasted, outline once on the stack",
                           "differences: red = (c) lacks/has other pixel (line pixels bright)", "the layer alone (body held out)"]):
        label(img, t, (c * (w + 12) + 4, 22))
    counts = []
    for r, (d, i) in enumerate(picks):
        a, c, layer = stacked(clip, d, i)
        aa, cc = np.array(a), np.array(c)
        diff = (aa != cc).any(-1)
        dim = np.array(a.convert("LA").convert("RGBA")); dim[..., :3] = dim[..., :3] // 3
        dim = dim.astype(np.uint8)
        dim[..., 3] = np.where(aa[..., 3] > 0, 255, 0)
        mark = dim.copy(); mark[diff] = (255, 40, 40, 255)
        counts.append(int(diff.sum()))
        y = 40 + r * w
        for col, im in enumerate([a, c, Image.fromarray(mark), layer]):
            img.alpha_composite(on_bg(im, S), (col * (w + 12), y))
        label(img, f"{d} frame {i}: {int(diff.sum())} px differ", (4, y + 4))
    img.convert("RGB").save(OUT / name)
    print(name, img.size, counts)


def ac_gif(name, clip, d, n, fps):
    frames = []
    S = 3
    for i in range(n):
        a, c, layer = stacked(clip, d, i)
        diff = (np.array(a) != np.array(c)).any(-1)
        dim = np.array(a); dim[..., :3] //= 3; dim[diff] = (255, 40, 40, 255)
        row = Image.new("RGBA", (3 * 86 * S + 24, 86 * S), BG)
        for k, im in enumerate([a, c, Image.fromarray(dim)]):
            row.alpha_composite(on_bg(im, S), (k * (86 * S + 12), 0))
        frames.append(row.convert("RGB"))
    frames[0].save(OUT / name, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0)
    print(name, frames[0].size)


def do_ac():
    ac_sheet("compare_a_vs_c_stick_attack_x4.png", "attack",
             [("s", 4), ("w", 8), ("n", 8), ("e", 4), ("e", 12), ("se", 10)],
             "stick in attack: (a) attached against (c) a layer over the body (red: where the stack differs)")
    ac_sheet("compare_a_vs_c_phone_phone_x4.png", "phone",
             [("s", 12), ("n", 12), ("e", 3), ("e", 12), ("se", 12), ("ne", 12)],
             "phone in phone: (a) against (c); n and ne: the phone is behind the body, the layer is empty")
    ac_gif("compare_a_vs_c_stick_attack_sw_x3.gif", "attack", "sw", 19, 12)
    ac_gif("compare_a_vs_c_phone_phone_s_x3.gif", "phone", "s", 27, 8)


# ---------------------------------------------------------------------------------------------------------------------------------
T = clip_table()
FR = {c["name"]: len(c["frames"]) for c in T}
KNOWN = {"idle", "walk", "attack", "phone_in", "phone", "phone_out"}
SRC = {"stick": {"attack": ("held_a1rows", 86, (43, 75))}, "rake": {"attack": ("held_rake", 138, (69, 113))}}
TINT = {}
for k, name in enumerate(FR):
    TINT[name] = tuple(int(x) for x in np.array([60, 60, 70]) + 30 * np.array([(k * 5) % 3, (k * 7) % 3, (k * 3) % 3]))


def cell_frame(thing, clip, d, i, side):
    """the real finished frame, placed in a cell of `side` by its pivot; None for a clip this trial didn't render"""
    if clip not in KNOWN:
        return None
    asset, s0, piv = SRC[thing].get(clip, ("held_a1rows", 86, (43, 75)))
    im = fin(asset, clip, d, i)
    # new cell's pivot: (side/2, side - below), below = 11 for attack with the weapon, 11 for the body (78: 67)
    pivots = {78: (39, 67), 86: (43, 75), 138: (69, 113)}
    nx, ny = pivots[side]
    big = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    big.paste(im, (nx - piv[0], ny - piv[1]))
    return big


def atlas(thing, rule, width, scale=1):
    """one image: every clip as a block of 8 direction rows x frames columns, each cell drawn with its grid, packed in shelves."""
    sides = {k: 78 for k in FR}
    if rule == "one":
        sides = {k: (86 if thing == "stick" else 138) for k in FR}
    else:
        sides["attack"] = 86 if thing == "stick" else 138
    blocks = []
    for name in FR:
        w, h = FR[name] * sides[name], 8 * sides[name]
        blocks.append((name, w, h))
    # shelf packing, widest first
    order = sorted(blocks, key=lambda b: -b[2])
    x = y = shelf = 0
    place_at = {}
    for name, w, h in order:
        if x + w > width:
            x, y, shelf = 0, y + shelf + 22, 0
        place_at[name] = (x, y + 14)
        x += w + 6; shelf = max(shelf, h + 14)
    total_h = y + shelf + 4
    img = Image.new("RGBA", (width, total_h + 40), (20, 20, 24, 255))
    dr = ImageDraw.Draw(img)
    cells = sum(FR[n] * 8 for n in FR)
    area = sum(FR[n] * 8 * sides[n] ** 2 for n in FR)
    base = sum(FR[n] * 8 * 78 ** 2 for n in FR)
    head = (f"{thing}, {'ONE cell for every clip' if rule == 'one' else 'a cell PER CLIP'}: {cells} cells, {area:,} px "
            f"= {100 * (area / base - 1):+.1f} % against all-78 ({base:,} px); colour atlas {area * 4 / 1e6:.1f} MB (RGBA)")
    dr.text((6, 4), head, fill=(255, 255, 255, 255))
    for name, (bx, by) in place_at.items():
        side = sides[name]
        by += 40
        dr.text((bx, by - 12), f"{name} {FR[name]}f x 8 dir, cell {side}", fill=(255, 220, 120, 255) if side != 78 else (200, 200, 200, 255))
        for d_i, d in enumerate(EIGHT):
            for i in range(FR[name]):
                cx, cy = bx + i * side, by + d_i * side
                fr = cell_frame(thing, name, d, i, side)
                dr.rectangle([cx, cy, cx + side - 1, cy + side - 1], fill=TINT[name] + (255,) if side == 78 else (90, 70, 40, 255))
                if fr is not None:
                    img.alpha_composite(fr, (cx, cy))
                dr.rectangle([cx, cy, cx + side - 1, cy + side - 1], outline=(255, 255, 255, 70))
    return img, area, base


def do_cells():
    for thing, width in (("stick", 3300), ("rake", 4000)):
        parts = [atlas(thing, rule, width)[0] for rule in ("one", "per_clip")]
        sheet = Image.new("RGBA", (width, sum(p.height for p in parts) + 10), (0, 0, 0, 255))
        y = 0
        for p in parts:
            sheet.alpha_composite(p, (0, y)); y += p.height + 10
        sheet.convert("RGB").save(OUT / f"cells_{thing}_one_cell_above_per_clip_below_x1.png")
        print(thing, sheet.size)


def do_layer():
    """(c)'s own layer cell: the body's 78 cell and the layer's own cell, pivots lined up, the widest frame of the layer."""
    S = 3
    pan = []
    for thing, scen, side, piv in (("stick", "c_stick", 86, (43, 75)), ("rake", "rake_c", 138, (69, 113))):
        best = None
        for d in EIGHT:
            for f in (R / scen / "color" / "attack" / d).glob("*.png"):
                a = np.array(Image.open(f).convert("RGBA"))[..., 3] > 0
                xs = np.where(a.any(0))[0]
                if len(xs) and (best is None or xs.max() - xs.min() > best[0]):
                    best = (xs.max() - xs.min(), d, f.name)
        _, d, name = best
        layer = Image.open(R / scen / "color" / "attack" / d / name).convert("RGBA")
        body = place(Image.open(R / "base" / "color" / "attack" / d / name).convert("RGBA"), side, (piv[0] - 39, piv[1] - 67))
        im = Image.new("RGBA", (side, side), BG)
        im.alpha_composite(body); im.alpha_composite(layer)
        big = im.resize((side * S, side * S), Image.NEAREST)
        dr = ImageDraw.Draw(big)
        ox, oy = (piv[0] - 39) * S, (piv[1] - 67) * S
        dr.rectangle([ox, oy, ox + 78 * S - 1, oy + 78 * S - 1], outline=(80, 220, 120, 255), width=2)   # the body's cell
        dr.rectangle([0, 0, side * S - 1, side * S - 1], outline=(255, 190, 60, 255), width=2)            # the layer's own cell
        dr.line([piv[0] * S - 8, piv[1] * S, piv[0] * S + 8, piv[1] * S], fill=(255, 60, 60, 255), width=2)
        dr.line([piv[0] * S, piv[1] * S - 8, piv[0] * S, piv[1] * S + 8], fill=(255, 60, 60, 255), width=2)
        txt = Image.new("RGBA", (side * S, 60), (20, 20, 24, 255))
        label(txt, f"{thing}: green = the body's cell 78, orange = the layer's own cell {side} (frame attack {d} {name[:3]})", (4, 4))
        label(txt, f"red cross = the pivot. As landed the Wearable must use the green cell (body's cell_margin grows it to the orange one).", (4, 20))
        label(txt, f"layer pivot ({piv[0]}, {piv[1]}) is ({piv[0]-39}, {piv[1]-67}) px from the body's ({39}, {67}) in its own cell", (4, 36))
        col = Image.new("RGBA", (side * S, side * S + 60), (20, 20, 24, 255))
        col.alpha_composite(txt); col.alpha_composite(big, (0, 60))
        pan.append(col)
    sheet = Image.new("RGBA", (sum(p.width for p in pan) + 20, max(p.height for p in pan)), (20, 20, 24, 255))
    x = 0
    for p in pan:
        sheet.alpha_composite(p, (x, 0)); x += p.width + 20
    sheet.convert("RGB").save(OUT / "cells_c_layer_own_cell_vs_body_cell_x3.png")
    print("layer", sheet.size)


def crop_at(asset, clip, d, i, box, zoom):
    rj = json.loads((proj / asset / "work/render/render.json").read_text())
    c = next(c for c in rj["clips"] if c["name"] == clip)
    pt = c["directions"][d][i]["points"]["hand_r"]
    cx, cy = int(pt["x"]), int(pt["y"])
    im = fin(asset, clip, d, i)
    im = im.crop((cx - box // 2, cy - box // 2, cx + box // 2, cy + box // 2))
    return on_bg(im, zoom)


def swatches(asset, other):
    pal = json.loads((proj / asset / "work/palette/palette.json").read_text())["colors"]
    ref = {c["hex"] for c in json.loads((proj / other / "work/palette/palette.json").read_text())["colors"]}
    return [(tuple(c["rgb"]), c["hex"] in ref) for c in pal]


def do_colours():
    Z, box = 10, 40
    cases = [("stick", "attack", "e", 4), ("stick", "attack", "s", 4), ("phone", "phone", "s", 12), ("phone", "phone", "se", 12)]
    w = box * Z
    # the body pixels that change under the fixed option, in the clips without a thing
    changed = []
    for clip in ("idle", "walk"):
        for d in EIGHT:
            n = len(list((proj / "held_base/work/finish/color" / clip / d).glob("*.png")))
            for i in range(n):
                b = np.array(place(fin("held_base", clip, d, i), 86, (4, 8))); f = np.array(fin("held_a1", clip, d, i))
                for y, x in zip(*np.where((b != f).any(-1))):
                    changed.append((clip, d, i, int(x), int(y), tuple(b[y, x]), tuple(f[y, x])))
    print("body px changed under fixed:", changed)
    rows = len(cases) + 2
    img = Image.new("RGBA", (2 * w + 12, rows * w + 330), (20, 20, 24, 255))
    label(img, "left: the thing in FIXED colours (in no part)      right: a RAMP ROW of its own (phone=phone+phone_screen, stick)      zoom 10x of the hand", (4, 4))
    for r, (thing, clip, d, i) in enumerate(cases):
        y = 20 + r * w
        for c, asset in enumerate(("held_a1", "held_a1rows")):
            img.alpha_composite(crop_at(asset, clip, d, i, box, Z), (c * (w + 12), y))
        label(img, f"{thing}: {clip} {d} frame {i}", (4, y + 4))
    y0 = 20 + len(cases) * w
    # the colours each option's palette holds for the fixed subset: a swatch not in the body-only palette is outlined white
    label(img, "fixed subset (16 colours) of: body only | things fixed | things with a row.  A white frame = a colour the body-only palette doesn't have; a cross = a body colour dropped.", (4, y0 + 6))
    base_pal = swatches("held_base", "held_base")
    for k, asset in enumerate(("held_base", "held_a1", "held_a1rows")):
        sw = swatches(asset, "held_base")
        dr = ImageDraw.Draw(img)
        for j, (rgb, shared) in enumerate(sw):
            x, y = 6 + j * 44, y0 + 24 + k * 62
            dr.rectangle([x, y, x + 40, y + 40], fill=rgb + (255,), outline=(255, 255, 255, 255) if not shared else (20, 20, 24, 255), width=3)
        names = ("body only", "things fixed", "things in rows")[k]
        label(img, names, (6, y0 + 24 + k * 62 + 42))
    dropped = [c for c, _ in base_pal if c not in [c2 for c2, _ in swatches("held_a1", "held_base")]]
    label(img, f"colours the body had that the fixed option dropped from its fixed subset: {len(dropped)} (they carried no pixel of idle or walk except {len(changed)} px)", (6, y0 + 216))
    # the changed body pixel(s), before and after
    yy = y0 + 240
    for k, (clip, d, i, x, y, before, after) in enumerate(changed[:3]):
        a = place(fin("held_base", clip, d, i), 86, (4, 8)).crop((x - 8, y - 8, x + 9, y + 9))
        b = fin("held_a1", clip, d, i).crop((x - 8, y - 8, x + 9, y + 9))
        for c, im in enumerate((a, b)):
            big = on_bg(im, 6)
            dr = ImageDraw.Draw(big); dr.rectangle([8 * 6 - 3, 8 * 6 - 3, 9 * 6 + 3, 9 * 6 + 3], outline=(255, 40, 40, 255), width=2)
            img.alpha_composite(big, (6 + c * 120, yy))
        label(img, f"{clip} {d} frame {i}: pixel ({x},{y}) {tuple(int(v) for v in before[:3])} -> {tuple(int(v) for v in after[:3])}", (250, yy + 30))
    img.crop((0, 0, img.width, yy + 120)).convert("RGB").save(OUT / "compare_colours_fixed_vs_row_x10.png")
    print("colours", img.size)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("ac", "all"):
        do_ac()
    if what in ("cells", "all"):
        do_cells()
    if what in ("colours", "all"):
        do_colours()
    if what in ("layer", "all"):
        do_layer()
